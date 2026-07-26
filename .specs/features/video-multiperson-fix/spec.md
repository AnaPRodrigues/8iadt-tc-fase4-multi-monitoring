# Video Multi-Person Fall Detection Fix — Specification

## Problem Statement

O pipeline de detecção de queda em vídeo apresenta três falhas estruturais em cenas com múltiplas pessoas (paciente no leito + acompanhantes):

1. **Falso positivo**: Acompanhantes que se sentam ou se inclinam são incorretamente classificados como queda. O `validate_fall_dynamic` itera por índice posicional (`p_idx`) em vez de agrupar por `track_id`, misturando dados de pessoas diferentes numa mesma timeline. Além disso, o filtro `started_low` só examina os primeiros 30 frames, ignorando pessoas que entram depois ou que estavam de pé nos frames iniciais.

2. **Pessoa errada marcada na evidência**: Quando há múltiplas pessoas e uma queda real ocorre, o `track_id` extraído para a evidência visual pertence à pessoa errada — consequência do agrupamento por índice posicional que não corresponde a identidades reais.

3. **Movimentos anômalos não detectados**: O pipeline só analisa 1 pessoa por frame (`select_ground_person`). Movimentos do paciente no leito (agitação, espasmos) são invisíveis se houver um acompanhante de pé na cena.

**Iteração 1** (este spec) ataca as causas-raiz com três intervenções estruturais. A Iteração 2 (detectores de convulsão/agitação/saída do leito + análise multi-pessoa completa) será especificada separadamente.

## Goals

- [ ] **G1**: Eliminar falsos positivos de queda em cenas com paciente no leito + acompanhantes, mantendo a sensibilidade para quedas reais.
- [ ] **G2**: Garantir que o `track_id` reportado na evidência de queda corresponde exatamente à pessoa que caiu.
- [ ] **G3**: Reduzir falsos positivos em cenas multi-pessoa através de thresholds adaptativos.

## Out of Scope

| Feature | Reason |
|---------|--------|
| Detectores de convulsão/agitação/saída do leito | Iteração 2 |
| Análise simultânea de todas as pessoas (não só ground person) | Iteração 2 |
| `select_ground_person` com persistência de track_id | Iteração 2 |
| Unificação de thresholds de visibilidade (0.5 → 0.4) | Iteração 2 |
| Redução do streak mínimo de 3 para 2 frames | Iteração 2 |
| Alteração do MediaPipe ou do detector YOLO/NAS | Fora do escopo — o problema está na lógica de análise, não na detecção de keypoints |

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
|------------------------|----------------|-----------|------------|
| Track_id do ByteTrack é confiável para agrupamento | Sim, usar como chave primária | ByteTrack é mantido pelo Ultralytics e já é usado com sucesso no projeto; o IoU tracker manual é fallback | y |
| Janela deslizante de 90 frames para `is_recumbent` | 90 frames (~3s a 30fps) | Tempo suficiente para estabelecer baseline de posição sem ser tão longo que perca a entrada recente de uma pessoa | y |
| Threshold de Y para "recumbent" | Y > 0.45 | Mesmo valor já usado em `started_low`; validado empiricamente contra o URFD | y |
| Thresholds multi-pessoa aplicam-se quando `n_pessoas > 1` | Sim | Cenas single-person mantêm os thresholds originais (otimizados para URFD); só cenas multi-pessoa sobem a barra | y |
| `_MIN_TILT_FOR_FALL` multi-pessoa | 35° | Sentar naturalmente envolve ~25-30°; queda real > 45°; 35° é um meio-termo conservador | y |

**Open questions:** none — all resolved or logged above.

---

## User Stories

### P1: Detecção de queda usa identidade real (track_id) em vez de índice posicional ⭐ MVP

**User Story**: Como sistema de monitoramento, ao analisar um vídeo com múltiplas pessoas, quero que a velocidade vertical, deslocamento e tilt de cada pessoa sejam calculados sobre a sua própria timeline (agrupada por `track_id`), para que os movimentos de pessoas diferentes nunca se misturem e a pessoa correta seja identificada na evidência.

**Why P1**: É a causa-raiz dos Problemas 1b (falso positivo por mistura de identidades) e 2a/2b (pessoa errada marcada). Sem esta correção, qualquer ajuste de threshold é paliativo.

**Acceptance Criteria**:

1. WHEN `validate_fall_dynamic` recebe `all_poses_per_frame` com múltiplas pessoas THEN as poses SHALL ser agrupadas por `track_id` (não por índice posicional), construindo uma timeline independente para cada identidade.

2. WHEN uma pessoa com `track_id=X` satisfaz todas as condições de queda THEN o `track_id` devolvido SHALL ser `X` (não o track_id de outra pessoa que por acaso apareceu primeiro na timeline).

3. WHEN duas pessoas diferentes aparecem em índices posicionais trocados entre frames consecutivos THEN as métricas de Vy, deslocamento e tilt de cada uma SHALL ser computadas apenas sobre os frames em que a sua identidade (`track_id`) está presente, sem contaminação cruzada.

4. WHEN `track_id` é `None` (fallback sem tracking) THEN o comportamento SHALL ser equivalente ao atual (índice posicional), garantindo retrocompatibilidade com cenários single-person e datasets sem ByteTrack.

**Independent Test**: Criar um cenário sintético com 2 pessoas onde os índices posicionais trocam entre frames — verificar que `validate_fall_dynamic` produz métricas independentes para cada `track_id` e que a pessoa com maior Vy é corretamente identificada pelo seu `track_id`.

---

### P2: Detecção de posição reclinada adaptativa (substitui `_INITIAL_FRAMES`) ⭐ MVP

**User Story**: Como sistema de monitoramento, quero determinar se uma pessoa já está deitada com base numa janela deslizante dos últimos N frames (não apenas os primeiros 30), para que um acompanhante que entra depois do frame 30 e se senta naturalmente não seja confundido com uma queda, e um paciente que já está no leito desde o início também não dispare alarme.

**Why P1**: É a causa-raiz do Problema 1c. O filtro atual de 30 frames iniciais é cego a pessoas que entram depois e não estabelece baseline para o paciente que já está deitado.

**Acceptance Criteria**:

1. WHEN a função `is_recumbent(person_frames)` é chamada THEN SHALL examinar os últimos 90 frames válidos (não-None) da timeline daquela pessoa, calculando a posição Y média dos quadris.

2. WHEN a posição Y média dos quadris nos últimos 90 frames válidos for > 0.45 THEN `is_recumbent` SHALL devolver `True` (pessoa já está deitada).

3. WHEN `is_recumbent` devolve `True` para uma pessoa THEN `validate_fall_dynamic` SHALL excluir essa pessoa da detecção de queda (não disparar falso positivo para pessoa que já estava deitada).

4. WHEN uma pessoa tem menos de 10 frames válidos na janela deslizante THEN `is_recumbent` SHALL devolver `False` (dados insuficientes para classificar — não assumir que está deitada).

5. WHEN uma pessoa estava deitada (`is_recumbent=True`) mas depois se levanta (Y médio < 0.45 por 90+ frames) THEN `is_recumbent` SHALL passar a devolver `False`, permitindo que uma queda real dessa pessoa seja detectada.

**Independent Test**: Criar timeline sintética onde uma pessoa começa com Y=0.5 (deitada) por 90 frames, depois levanta (Y=0.3) por 90 frames, depois cai (Y=0.3→0.8 em 5 frames). Verificar que `is_recumbent` devolve True→False→False e a queda é detectada apenas na fase final.

---

### P3: Thresholds adaptativos para cenas multi-pessoa

**User Story**: Como sistema de monitoramento, quando detecto mais de uma pessoa na cena, quero aplicar thresholds mais conservadores para classificação de queda, porque cenas multi-pessoa têm mais fontes de ruído (movimentação de acompanhantes, oclusões parciais) que podem gerar falsos positivos.

**Why P2**: Complementa P1 e P2 reduzindo falsos positivos residuais. Cenas multi-pessoa são intrinsecamente mais ruidosas que o dataset URFD single-person para o qual os thresholds originais foram calibrados.

**Acceptance Criteria**:

1. WHEN `n_pessoas > 1` THEN o threshold de tilt mínimo para queda (`_MIN_TILT_FOR_FALL`) SHALL ser 35° (em vez de 25°).

2. WHEN `n_pessoas > 1` THEN o deslocamento total mínimo (`_MIN_TOTAL_DISPLACEMENT`) SHALL ser 0.30 (em vez de 0.20).

3. WHEN `n_pessoas > 1` THEN a velocidade vertical mínima (`min_vertical_velocity`) SHALL ser 0.20 (em vez de 0.15).

4. WHEN `n_pessoas > 1` THEN `persistence_frames` em `classify_with_persistence` SHALL ser 3 (em vez de 1).

5. WHEN `n_pessoas == 1` ou `n_pessoas == 0` THEN todos os thresholds SHALL manter os valores originais (25°, 0.20, 0.15, 1), preservando o comportamento calibrado para o dataset URFD.

**Independent Test**: Executar o pipeline sobre uma sequência URFD single-person (ex: `fall-01`) e verificar que o resultado é idêntico ao baseline pré-fix. Executar sobre uma cena multi-pessoa sintética e verificar que os thresholds elevados são aplicados.

---

## Edge Cases

- WHEN `track_id` é `None` para todas as pessoas (fallback sem tracking ativo) THEN `validate_fall_dynamic` SHALL usar agrupamento por índice posicional (comportamento atual), mantendo retrocompatibilidade.
- WHEN uma pessoa aparece apenas em 1-2 frames isolados THEN `is_recumbent` SHALL devolver `False` (dados insuficientes) e a pessoa SHALL ser avaliada para queda normalmente.
- WHEN `all_poses_per_frame` está vazio ou é `None` THEN `validate_fall_dynamic` SHALL comportar-se como atualmente (sem dados multi-pessoa).
- WHEN o vídeo tem menos de 90 frames THEN `is_recumbent` SHALL usar todos os frames disponíveis, com o mínimo de 10 para produzir uma classificação.
- WHEN dois track_ids diferentes têm o mesmo pico de Vy THEN o primeiro encontrado (ordem de iteração do dicionário) SHALL ser o reportado.

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
|---------------|-------|-------|--------|
| MULTI-01 | P1: Agrupamento por track_id em validate_fall_dynamic | Execute | Verified |
| MULTI-02 | P1: track_id correto no resultado da validação | Execute | Verified |
| MULTI-03 | P1: Retrocompatibilidade quando track_id é None | Execute | Verified |
| MULTI-04 | P2: is_recumbent() com janela deslizante de 90 frames | Execute | Verified |
| MULTI-05 | P2: Exclusão de pessoas recumbent da detecção de queda | Execute | Verified |
| MULTI-06 | P2: Transição recumbent→levantada permite detecção futura | Execute | Verified |
| MULTI-07 | P3: Thresholds elevados em cenas multi-pessoa | Execute | Verified |
| MULTI-08 | P3: Thresholds originais preservados em single-person | Execute | Verified |

**Coverage:** 8 total, 8 verified, 0 unmapped ✅

## Success Criteria

- [ ] Cenário sintético: 1 paciente deitado (Y>0.45 estável) + 1 acompanhante que entra e senta → **zero falsos positivos** de queda
- [ ] Cenário sintético: 1 pessoa de pé que cai (Vy>0.25, tilt>45°) enquanto outra pessoa está deitada → queda detectada com **track_id correto** da pessoa que caiu
- [ ] Dataset URFD (`fall-01`, `adl-01`): resultados **idênticos** ao baseline pré-fix (single-person, thresholds originais)
- [ ] `make test` na suíte completa sem regressão (533+ testes verdes)
- [ ] `ruff check backend` limpo
