# Video Multi-Person Fix — Iteration 2 Specification

## Problem Statement

A Iteração 1 eliminou a causa-raiz de falsos positivos (agrupamento por track_id + exclusão de pessoas deitadas + thresholds adaptativos). Porém, restam 5 melhorias estruturais e novos detectores:

1. **Salto de identidade no `select_ground_person`**: A função seleciona a pessoa com maior Y **por frame**, podendo alternar entre track_ids diferentes e gerar amplitude artificial no centro de massa — gatilho de falso positivo na classificação por janela (`classify_with_persistence`).

2. **Pipeline mono-pessoa**: Apesar de o sistema detetar até 3 pessoas (`num_poses=3`), só 1 (a "ground person") é analisada. Movimentos do paciente no leito são invisíveis se houver um acompanhante de pé.

3. **Sem detectores para movimentos anômalos não-queda**: Convulsões, agitação psicomotora e saída do leito não são detetados — o sistema só reconhece queda, desvio postural e inclinação de tronco.

4. **Visibilidade mínima muito restritiva**: O threshold de 0.5 derruba a detecção quando lençóis/cobertores ocluem parcialmente os quadris — comum em ambiente hospitalar.

5. **Filtro temporal agressivo**: O requisito de ≥3 frames consecutivos no `select_ground_person` descarta movimentos breves mas reais (espasmos, início de convulsão).

## Goals

- [ ] **G1**: Eliminar saltos de identidade no `select_ground_person` via persistência de track_id.
- [ ] **G2**: Analisar cada pessoa detetada independentemente, com o detector adequado ao seu papel (deitado/em pé/transição).
- [ ] **G3**: Detetar convulsões/espasmos, agitação e saída do leito com thresholds calibrados.
- [ ] **G4**: Reduzir falsos negativos por oclusão parcial (visibilidade 0.5 → 0.4).
- [ ] **G5**: Capturar eventos breves (streak mínimo 3 → 2 frames).

## Out of Scope

| Feature | Reason |
|---------|--------|
| Alteração do MediaPipe ou YOLO/NAS | Fora do escopo do pipeline de análise |
| Novo dataset ou re-treinamento | Usa os mesmos datasets existentes (URFD, vídeos enviados) |
| Interface de utilizador para novos alertas | O frontend já exibe achados genéricos; novos finding_types aparecem automaticamente |
| Deteção de "paciente ausente" (cama vazia) | Caso de uso não coberto pelos datasets atuais |

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
|------------------------|----------------|-----------|------------|
| Persistência de track_id: switch após N frames ausente | 30 frames (~1s a 30fps) | Tempo suficiente para tolerar oclusão breve sem perder a identidade | y |
| Classificação de papel: thresholds de Y | recumbent: Y>0.45 por 90 frames; standing: Y<0.35 por 30 frames; transitioning: otherwise | Consistente com is_recumbent() da Iteração 1; standing requer posição elevada sustentada | y |
| Convulsão: std da velocidade angular de cotovelos + joelhos | 4 articulações (13,14,25,26), janela de 60 frames (~2s) | Movimento rítmico multi-articular é assinatura de convulsão; janela de 2s captura 1-2 ciclos | y |
| Agitação: trocas de posição por minuto | threshold > 10 mudanças/min onde mudança = ΔY > 0.03 entre médias de janelas de 30 frames | Valor conservador; pacientes agitados tipicamente têm >15 mudanças/min | y |
| Saída do leito: Y sustentado subindo | ΔY < -0.10 (Y diminui = pessoa sobe na imagem) + ΔX > 0.05 por 60+ frames | Movimento lento e deliberado, não abrupto como queda | y |
| Visibilidade unificada: 0.4 | `_MIN_VISIBILITY = 0.4` em todo o pipeline | Já usado como `_MIN_OCCLUSION_VIS`; valor validado em AD-056 para lençóis | y |
| Streak mínimo: 2 frames | `_MIN_CONSECUTIVE_FRAMES = 2` | Metade do valor atual; ainda filtra ruído de 1 frame isolado | y |
| Novos detectores geram `PosturalFinding` com `finding_type` específico | "SEIZURE", "AGITATION", "BED_EXIT" | Mesmo contrato de evidência; frontend consome sem alteração | y |

**Open questions:** none — all resolved or logged above.

---

## User Stories

### P1: `select_ground_person` com persistência de track_id ⭐ MVP

**User Story**: Como pipeline de análise, ao selecionar a "ground person" (pessoa mais próxima do chão) em cada frame, quero manter o mesmo track_id ao longo da sequência, para que o centro de massa não salte entre pessoas diferentes e não produza amplitude artificial que dispare falsos positivos de queda.

**Why P1**: É a última causa-raiz restante de falso positivo na classificação por janela. Sem isto, a amplitude do centro de massa pode exceder 0.55 simplesmente porque o `select_ground_person` alternou entre o paciente (Y≈0.8) e um acompanhante (Y≈0.4).

**Acceptance Criteria**:

1. WHEN `select_ground_person` processa uma sequência com múltiplos track_ids THEN SHALL calcular o track_id dominante (mais frequente como ground person) nos primeiros 60 frames.

2. WHEN o track_id dominante está presente num frame THEN `select_ground_person` SHALL devolver esse track_id nesse frame, mesmo que outra pessoa tenha Y maior.

3. WHEN o track_id dominante está ausente por mais de 30 frames consecutivos THEN `select_ground_person` SHALL recalcular o track_id dominante na janela recente.

4. WHEN não há track_ids (todos None, fallback sem tracking) THEN `select_ground_person` SHALL manter o comportamento atual (seleção por Y máximo sem persistência).

5. WHEN a pessoa do track_id dominante tem visibilidade média < 0.4 num frame THEN esse frame SHALL ser None para essa pessoa (oclusão total), mas o track_id persistente não é abandonado.

**Independent Test**: Criar sequência sintética com 2 track_ids onde o Y alterna — verificar que o track_id devolvido é estável (sempre o mesmo) apesar da alternância de Y.

---

### P2: Pipeline multi-pessoa com classificação de papel ⭐ MVP

**User Story**: Como sistema de monitoramento, quero que cada pessoa detetada na cena seja analisada independentemente com o detector adequado ao seu papel (deitado → agitação/saída do leito; em pé → queda; transição → queda), para que nenhum evento clínico relevante passe despercebido independentemente da posição da pessoa na imagem.

**Why P1**: Fecha a lacuna do pipeline mono-pessoa. Um paciente tendo uma convulsão no leito precisa ser detetado mesmo com um acompanhante de pé ao lado.

**Acceptance Criteria**:

1. WHEN `classify_person_role(person_frames)` é chamada THEN SHALL classificar como "recumbent" se `is_recumbent(frames)` for True, "standing" se Y médio < 0.35 nos últimos 30 frames válidos, ou "transitioning" caso contrário.

2. WHEN uma pessoa é classificada como "recumbent" THEN o sistema SHALL executar apenas os detectores de agitação e saída do leito (não o detector de queda).

3. WHEN uma pessoa é classificada como "standing" ou "transitioning" THEN o sistema SHALL executar o detector de queda (`validate_fall_dynamic`).

4. WHEN múltiplas pessoas geram achados THEN todos os achados SHALL ser reportados (não apenas o primeiro ou o mais grave).

5. WHEN não há tracking ativo (todos track_id=None) THEN o sistema SHALL manter o comportamento atual (1 pessoa, ground person, detector de queda).

**Independent Test**: Criar cena com 1 pessoa deitada (convulsão simulada) + 1 pessoa de pé (estática). Verificar que o achado de convulsão é gerado para a pessoa deitada e nenhum falso positivo de queda para a pessoa de pé.

---

### P3: Detector de convulsão/espasmo

**User Story**: Como sistema de monitoramento, quero detetar episódios de convulsão ou espasmo muscular através da oscilação rápida e rítmica de múltiplas articulações, para alertar a equipa clínica sobre uma emergência neurológica.

**Why P2**: Convulsões são eventos clínicos graves que o sistema atual não reconhece. É o detector de movimento anômalo mais impactante.

**Acceptance Criteria**:

1. WHEN `detect_seizure(frames, fps)` analisa uma timeline THEN SHALL calcular o desvio padrão da velocidade angular (frame a frame) dos cotovelos (landmarks 13, 14) e joelhos (25, 26) numa janela deslizante de 60 frames (~2s a 30fps).

2. WHEN o desvio padrão médio das 4 articulações excede 0.05 por 30+ frames consecutivos THEN SHALL emitir um `PosturalFinding` com `finding_type="SEIZURE"`.

3. WHEN a visibilidade de qualquer uma das 4 articulações é < 0.4 THEN essa articulação SHALL ser excluída da média daquele frame (não invalida o frame inteiro).

4. WHEN há menos de 60 frames válidos na timeline THEN SHALL devolver lista vazia (sem dados suficientes).

**Independent Test**: Timeline sintética com oscilação rítmica (Y varia ±0.03 a 3 Hz) nos cotovelos e joelhos por 90 frames → 1 finding emitido. Timeline sem oscilação → 0 findings.

---

### P4: Detector de agitação psicomotora

**User Story**: Como sistema de monitoramento, quero detetar episódios de agitação psicomotora através de mudanças frequentes de posição, para alertar sobre desconforto, delirium ou necessidade de intervenção.

**Why P2**: Agitação é um sinal clínico relevante em UTI e enfermaria, especialmente em pacientes com sedação ou distúrbios neurológicos.

**Acceptance Criteria**:

1. WHEN `detect_agitation(frames, fps)` analisa uma timeline THEN SHALL dividir a sequência em janelas de 30 frames (~1s) e calcular a posição Y média dos quadris em cada janela.

2. WHEN a diferença absoluta de Y médio entre janelas consecutivas excede 0.03 THEN SHALL contar como uma "mudança de posição".

3. WHEN o número de mudanças de posição por minuto excede 10 THEN SHALL emitir um `PosturalFinding` com `finding_type="AGITATION"`.

4. WHEN a timeline tem menos de 120 frames (~4s) THEN SHALL devolver lista vazia (dados insuficientes para taxa por minuto).

**Independent Test**: Timeline com 20 mudanças de posição em 60s → 1 finding emitido. Timeline estável com 2 mudanças em 60s → 0 findings.

---

### P5: Detector de saída do leito

**User Story**: Como sistema de monitoramento, quero detetar quando um paciente previamente deitado começa a sair do leito (Y diminuindo sustentado + deslocamento lateral), para alertar sobre risco de queda ou fuga.

**Why P2**: A saída do leito é um precursor de queda — detetá-la permite intervenção antes do evento. Complementa o detector de queda (que só dispara depois).

**Acceptance Criteria**:

1. WHEN `detect_bed_exit(frames, fps)` analisa uma timeline de uma pessoa classificada como "recumbent" THEN SHALL procurar por uma tendência sustentada de Y diminuindo (pessoa sobe na imagem) ao longo de 60+ frames.

2. WHEN ΔY < -0.10 (Y médio dos últimos 30 frames vs. 30 frames anteriores) E deslocamento lateral total > 0.05 nos mesmos 60 frames THEN SHALL emitir um `PosturalFinding` com `finding_type="BED_EXIT"`.

3. WHEN a pessoa não está classificada como "recumbent" THEN SHALL devolver lista vazia (detector só se aplica a pessoas deitadas).

4. WHEN a timeline tem menos de 120 frames THEN SHALL devolver lista vazia (dados insuficientes).

**Independent Test**: Timeline de pessoa deitada (Y≈0.8) que sobe gradualmente (Y: 0.8→0.5) com deslocamento lateral ao longo de 90 frames → 1 finding. Pessoa de pé (Y≈0.3) → 0 findings.

---

### P6: Unificação de threshold de visibilidade

**User Story**: Como pipeline de análise, quero usar um threshold único de visibilidade (0.4) em todos os gates, para que lençóis e cobertores não derrubem a detecção de forma inconsistente.

**Why P3**: Hoje há dois thresholds diferentes (0.5 e 0.4) usados em pontos distintos, causando comportamento imprevisível com oclusão parcial.

**Acceptance Criteria**:

1. WHEN qualquer gate de visibilidade no pipeline verifica um landmark THEN SHALL usar `_MIN_VISIBILITY = 0.4` como threshold único.

2. WHEN `hip_center()` é chamado com visibilidade dos quadris entre 0.4 e 0.5 THEN SHALL devolver coordenadas (antes devolvia None com threshold 0.5).

3. Os testes existentes que usam visibility=0.9 NÃO SHALL ser alterados (continuam acima do novo threshold).

**Independent Test**: Criar PoseFrame com visibilidade 0.45 nos quadris. Verificar que `hip_center()` devolve coordenadas (antes devolvia None).

---

### P7: Redução do streak mínimo no filtro temporal

**User Story**: Como pipeline de análise, quero reduzir o requisito de frames consecutivos para validar uma deteção de 3 para 2, para capturar eventos motores breves como espasmos e sobressaltos.

**Why P3**: O threshold atual de 3 frames (~0.1s a 30fps) descarta eventos reais de curta duração. Com 2 frames, ainda se filtra ruído de 1 frame isolado.

**Acceptance Criteria**:

1. WHEN `select_ground_person` aplica o filtro de consistência temporal THEN SHALL exigir `_MIN_CONSECUTIVE_FRAMES = 2` (em vez de 3).

2. WHEN uma pessoa aparece em exatamente 2 frames consecutivos THEN SHALL ser considerada válida (antes era descartada).

3. WHEN uma pessoa aparece em apenas 1 frame isolado THEN SHALL continuar a ser descartada (ruído).

**Independent Test**: Timeline com pessoa presente em apenas 2 frames consecutivos → pessoa é incluída no resultado. Timeline com pessoa em 1 frame isolado → pessoa é descartada.

---

## Edge Cases

- WHEN duas pessoas têm o mesmo track_id (colisão de ID, raro) THEN o sistema SHALL tratar como a mesma pessoa (comportamento atual do ByteTrack).
- WHEN `classify_person_role` encontra uma timeline totalmente vazia (todos None) THEN SHALL devolver "unknown" e nenhum detector é executado.
- WHEN múltiplos detectores geram findings para a mesma pessoa THEN todos SHALL ser incluídos no resultado consolidado.
- WHEN `detect_seizure` e `detect_agitation` disparam simultaneamente THEN ambos os findings SHALL ser reportados (não são mutuamente exclusivos).
- WHEN um vídeo tem < 120 frames (~4s) THEN os detectores de agitação e saída do leito SHALL devolver listas vazias (dados insuficientes), mas o de convulsão (60 frames) e queda (30 frames) ainda podem operar.

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
|---------------|-------|-------|--------|
| ITER2-01 | P1: Persistência de track_id no select_ground_person | Specify | Pending |
| ITER2-02 | P2: classify_person_role() | Specify | Pending |
| ITER2-03 | P2: Pipeline multi-pessoa com detectores por papel | Specify | Pending |
| ITER2-04 | P3: detect_seizure() — oscilação multi-articular | Specify | Pending |
| ITER2-05 | P4: detect_agitation() — mudanças de posição/min | Specify | Pending |
| ITER2-06 | P5: detect_bed_exit() — Y subindo + ΔX | Specify | Pending |
| ITER2-07 | P6: Unificar threshold de visibilidade (0.5→0.4) | Specify | Pending |
| ITER2-08 | P7: Reduzir streak mínimo (3→2) | Specify | Pending |

**Coverage:** 8 total, 0 mapped to tasks, 8 unmapped ⚠️

## Success Criteria

- [ ] Cenário: 1 paciente deitado (convulsão simulada) + 1 acompanhante de pé estático → finding "SEIZURE" para o paciente, zero falsos positivos para o acompanhante
- [ ] Cenário: paciente deitado que sai do leito (Y sobe + desloca lateralmente) → finding "BED_EXIT"
- [ ] Cenário: pessoa com 15 mudanças de posição/min → finding "AGITATION"
- [ ] Cenário: pessoa com 5 mudanças de posição/min → sem finding (abaixo do threshold)
- [ ] `hip_center()` com visibilidade 0.45 → devolve coordenadas (antes devolvia None)
- [ ] Pessoa em 2 frames consecutivos → incluída no `select_ground_person`
- [ ] Dataset URFD single-person: resultados idênticos ao baseline (retrocompatibilidade)
- [ ] `make test` na suíte completa sem regressão
- [ ] `ruff check backend` limpo
