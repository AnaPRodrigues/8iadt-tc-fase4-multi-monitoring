# F1-Pose — Video Pose Analysis Expansion Specification

> **Contexto.** Esta spec expande a raia pose do pipeline de vídeo (F1, AD-039).
> A spec original em `video-analysis/spec.md` cobre as duas raias (pose + objeto) e o
> Amendment 1 cobre suporte a ficheiros de vídeo. Esta spec foca-se exclusivamente nas
> melhorias e no novo modo de fisioterapia da raia pose.

## Problem Statement

O pipeline de postura atual tem três limitações concretas: (1) o detector de quedas
produz falsos positivos em inclinações de tronco e agachamentos — a classificação é
instantânea (basta 1 janela exceder o limiar), sem persistência temporal; (2) o
MediaPipe está configurado para `num_poses=1`, ignorando pessoas adicionais na cena
(ex.: enfermeiro de pé ao lado do paciente no chão); (3) não existe modo de análise
postural para fisioterapia — o sistema só sabe dizer "queda" ou "não queda", sem
avaliar amplitude articular, ângulos ou compensações posturais.

O utilizador quer **análise unificada**: cada vídeo de movimentação passa pelos dois
detetores (queda + fisioterapia) e produz achados de ambos os tipos, com o contrato
de evidência mantido (`output/video_pose/<run_id>/`).

## Goals

- [ ] **Filtro temporal de persistência** no detector de quedas: o alerta só dispara após
  $N$ frames consecutivos acima do limiar (default 30 frames / ~1 segundo).
- [ ] **Limiar de queda elevado** de `0.3` para `0.55` (score de amplitude do centro de massa).
- [ ] **Seleção multi-pessoa**: quando o MediaPipe deteta múltiplos esqueletos, selecionar
  a pessoa com menor posição Y média (nível do solo) — tipicamente o paciente caído.
- [ ] **Novo modo `physiotherapy`**: cálculo de ângulos articulares (joelho, cotovelo) e
  inclinação de tronco, com deteção de desvios posturais (`POSTURAL_DEVIATION`,
  `TRUNK_TILT`).
- [ ] Evidência unificada em `output/video_pose/<run_id>/` — artefato anotado (esqueleto
  com articulações destacadas + ângulos) + sidecar `evidence.json` com tipo de achado,
  score e descrição em linguagem clínica.
- [ ] Configuração declarativa YAML com limiares de queda, fisioterapia e
  parâmetros de persistência temporal.

## Out of Scope

| Feature | Reason |
| --- | --- |
| Avaliação automática de progressão fisioterapêutica (séries, repetições) | Exigiria tracking de estado entre sessões; a análise é por vídeo individual |
| Deteção de quedas em vídeo multi-câmara (fusão de vistas) | Uma câmara por análise; o pipeline opera sobre uma sequência/ficheiro de cada vez |
| Classificação do tipo de queda (tropeção, desmaio, escorregamento) | Fora do escopo da demonstração; a classificação é binária (queda vs. não queda) |
| Suporte a vídeo com mais de 5 pessoas simultâneas | `num_poses` máximo prático em CPU para o modelo lite é ~3-5; documentado como limitação |
| Integração com a raia objeto/cirúrgica (Endoscapes/YOLOv8) | Responsabilidade da raia objeto — esta spec é só da raia pose |

---

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --- | --- | --- | --- |
| Número máximo de poses detetadas (`num_poses`) | `3` | Valor prático para cenas de quarto/sala de fisioterapia (paciente + 1-2 profissionais); acima disso o modelo lite degrada em CPU | n |
| FPS de referência para "1 segundo = 30 frames" | 30 fps | Default comum de câmaras; o parâmetro `persistence_frames` é configurável, não hardcoded a 30 | n |
| Ângulo articular de referência para fisioterapia | Configurável por articulação no YAML (ex.: `knee_flexion_target: 90`) | Cada exercício tem metas diferentes; valores padrão documentados como referência, não como diagnóstico | n |
| Comportamento quando não há pessoa detetável num frame | Frame é descartado da janela (comportamento atual, preservado) | Consistente com VIDEO-13 (edge case já coberto) | y |
| O modo `physiotherapy` não usa o dataset URFD | Aceita qualquer vídeo — não requer estrutura de diretório específica | URFD é exclusivo de queda; fisioterapia opera sobre vídeos genéricos | n |
| Baseline de assimetria no modo physiotherapy | A primeira janela do vídeo serve como referência de postura "neutra" | Sem baseline não há como determinar o que é desvio vs. postura natural do paciente | n |

**Open questions:** none — todas resolvidas ou registadas acima. Itens marcados "confirmed: n" são defaults propostos, abertos a ajuste sem bloquear o avanço para Design.

---

## Implicit-Requirement Dimensions Sweep

| Dimensão | Cobertura |
| --- | --- |
| Input validation & bounds | Frames sem pessoa detetável descartados da janela (POSE-13); vídeo corrompido/ilegível → `ErroDeAnalise` (POSE-16); `num_poses` ∈ [1,5], `persistence_frames` ≥ 1, `fall_threshold` ∈ [0,1] |
| Failure / partial-failure states | Falha do MediaPipe num frame não interrompe a sequência (POSE-13); `analysis_mode` inválido → `ValueError` na carga da config (POSE-12) |
| Idempotency / retry / duplicate handling | Mesmo vídeo + mesma config + mesma seed → mesmo resultado determinístico (POSE-14) |
| Auth boundaries & rate limits | N/A — processamento 100% local, sem chamada externa autenticada |
| Concurrency / ordering | Cada run tem o seu `run_id` isolado; duas análises concorrentes não misturam artefatos (POSE-15) |
| Data lifecycle / expiry | N/A — artefatos de evidência em `output/video_pose/<run_id>/`, sem requisito de retenção/expiração |
| Observability | Log de `analysis_mode` ativo, nº de pessoas detetadas por frame, nº de findings gerados, duração da análise (POSE-17) |
| External-dependency failure | Download do modelo MediaPipe `.task` é idempotente e tolerante a falha de rede (comportamento existente em `ensure_pose_model`, preservado) |
| State-transition integrity | Contador de persistência de queda reseta quando condição deixa de ser satisfeita (POSE-06); contador de inclinação de tronco reseta quando ângulo volta abaixo do limiar (POSE-10) |

---

## User Stories

### P1: Detector de quedas robusto (filtro temporal + limiar + multi-pessoa) ⭐ MVP

**User Story**: Como utilizador do sistema de monitoramento, quero que o detector de
quedas não dispare falsos positivos quando o paciente se agacha ou se inclina, e que
reconheça corretamente o paciente no chão mesmo com outras pessoas de pé na cena.

**Why P1**: Os falsos positivos atuais tornam o detector não confiável para uso real.
O filtro temporal e o ajuste de limiar resolvem a causa raiz; a seleção multi-pessoa
fecha um gap de cenários reais (quarto de hospital com equipa).

**Acceptance Criteria**:

1. WHEN uma janela excede o limiar de queda (`fall_threshold`, default `0.55`) THEN o
   sistema SHALL incrementar um contador de persistência; o alerta `FALL_DETECTED` só
   é emitido se o contador atingir `persistence_frames` (default 30) consecutivos.
2. WHEN o score de amplitude do centro de massa volta abaixo do limiar antes de atingir
   `persistence_frames` THEN o sistema SHALL resetar o contador a zero.
3. WHEN o MediaPipe deteta múltiplos esqueletos (`num_poses > 1`) THEN o sistema SHALL
   selecionar a pose cuja média dos landmarks no eixo Y for maior (pessoa mais abaixo
   na imagem — nível do solo) para a avaliação de queda.
4. WHEN o limiar configurado é `0.55` e o paciente se agacha (amplitude ≈ 0.35–0.50)
   THEN o sistema NÃO SHALL emitir alerta de queda.
5. WHEN uma queda é confirmada THEN o sistema SHALL gerar evidência com tipo
   `FALL_DETECTED`, score normalizado e frame anotado com o esqueleto da pessoa
   selecionada.

**Independent Test**: Gerar um vídeo sintético com uma pessoa a agachar-se (amplitude
< 0.55) durante 20 frames e outra a cair (amplitude > 0.55) durante 35 frames;
verificar que o agachamento não dispara alerta e a queda dispara.

---

### P2: Modo fisioterapia — ângulos articulares e inclinação de tronco

**User Story**: Como fisioterapeuta, quero analisar um vídeo de sessão de fisioterapia
e receber achados sobre amplitude articular insuficiente e inclinações anómalas do
tronco, com o esqueleto anotado e os ângulos sobrepostos no frame.

**Why P2**: É o novo modo de análise que expande o sistema de "só queda" para
"análise postural genérica", cobrindo o requisito de "padrões de movimentação do
paciente" (Req.3 do enunciado) com mais profundidade.

**Acceptance Criteria**:

1. WHEN o modo `physiotherapy` está ativo THEN o sistema SHALL calcular, por frame, os
   ângulos articulares configurados (joelho: quadril-joelho-tornozelo; cotovelo:
   ombro-cotovelo-pulso) usando o produto escalar dos vetores de keypoints.
2. WHEN o modo `physiotherapy` está ativo THEN o sistema SHALL calcular o ângulo de
   inclinação do tronco (eixo ombros-quadril vs. vertical Y) por frame.
3. WHEN um ângulo articular está abaixo do limiar configurado (ex.: `knee_flexion_min:
   70`) por mais de `persistence_frames` consecutivos THEN o sistema SHALL emitir um
   achado `POSTURAL_DEVIATION` com descrição clínica do ângulo alcançado vs. esperado.
4. WHEN a inclinação do tronco excede o limiar configurado (`trunk_tilt_max`, default
   `30`°) por mais de `tilt_persistence_frames` (default 90, ~3 segundos a 30 fps)
   consecutivos THEN o sistema SHALL emitir um achado `TRUNK_TILT` com o ângulo medido
   e a duração.
5. WHEN um achado é emitido THEN o sistema SHALL gerar evidência: frame anotado com o
   esqueleto completo, articulações anómalas destacadas a amarelo/vermelho, ângulos
   calculados sobrepostos no frame, e sidecar JSON com tipo, score e descrição clínica.

**Independent Test**: Gerar um vídeo sintético com uma pessoa a fazer flexão de joelho
até 62° (abaixo do mínimo de 70°) durante 40 frames consecutivos; verificar que o
sistema emite `POSTURAL_DEVIATION` com a descrição "Amplitude articular reduzida em
flexão de joelho (alcançado: 62°, esperado: >70°)".

---

### P3: Evidência unificada multi-finding

**User Story**: Como operador do sistema, quero que um vídeo de movimentação produza
todos os tipos de achado aplicáveis (queda + desvios posturais + inclinação de tronco)
numa única execução, sem ter de escolher um modo.

**Why P3**: A análise unificada garante que nenhum achado é perdido — o mesmo vídeo
pode conter uma queda e uma compensação postural, e o sistema deve reportar ambos.

**Acceptance Criteria**:

1. WHEN um vídeo é processado THEN o sistema SHALL executar ambos os detetores
   (queda e fisioterapia) sobre os mesmos frames extraídos.
2. WHEN múltiplos achados são gerados na mesma run THEN cada um SHALL ter o seu
   próprio artefato de evidência (PNG + sidecar JSON) com `evidence_id` único.
3. WHEN a config YAML é carregada THEN o sistema SHALL validar todos os campos
   (queda + fisioterapia) com defaults documentados; campo desconhecido → `ValueError`.
4. WHEN nenhum achado é gerado THEN o sistema SHALL devolver pontuação 0.0 com
   resumo "Nenhuma alteração detectada no período monitorado."

**Independent Test**: Processar um vídeo sintético com queda + flexão de joelho
insuficiente; verificar que o diretório de evidência contém 2 PNGs + 2 sidecars
JSON (um para `FALL_DETECTED`, outro para `POSTURAL_DEVIATION`).

---

## Edge Cases

- WHEN nenhuma pessoa é detetada em todos os frames da janela THEN o sistema SHALL
  descartar essa janela, sem gerar achado falso (POSE-13).
- WHEN o vídeo tem menos frames que `window_size` THEN o sistema SHALL reportar
  "dados insuficientes" com `pontuacao=None` (POSE-14, comportamento existente
  preservado).
- WHEN duas análises concorrentes usam o mesmo `run_id` THEN os artefatos SHALL ser
  escritos no mesmo diretório sem corromper o sidecar JSON (POSE-15).
- WHEN o ficheiro de vídeo está corrompido ou é ilegível THEN o sistema SHALL lançar
  `ErroDeAnalise` com mensagem clara (POSE-16).
- WHEN `num_poses > 1` mas só uma pessoa é detetada THEN o sistema SHALL usar essa
  única pose sem erro (POSE-18).
- WHEN o ângulo articular calculado é NaN (landmarks colineares ou visibilidade
  insuficiente) THEN o sistema SHALL descartar esse frame do contador de persistência
  (POSE-19).

---

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
| --- | --- | --- | --- |
| POSE-01 | P1: Persistência temporal — contador de frames consecutivos | Specify | Pending |
| POSE-02 | P1: Reset do contador quando score volta abaixo do limiar | Specify | Pending |
| POSE-03 | P1: Seleção multi-pessoa (menor Y = nível do solo) | Specify | Pending |
| POSE-04 | P1: Limiar de queda elevado para 0.55 (default) | Specify | Pending |
| POSE-05 | P1: Evidência FALL_DETECTED com frame anotado + score | Specify | Pending |
| POSE-06 | P2: Cálculo de ângulo articular (joelho, cotovelo) por frame | Specify | Pending |
| POSE-07 | P2: Cálculo de inclinação de tronco vs. eixo Y | Specify | Pending |
| POSE-08 | P2: Achado POSTURAL_DEVIATION com persistência temporal | Specify | Pending |
| POSE-09 | P2: Achado TRUNK_TILT com persistência temporal (3s default) | Specify | Pending |
| POSE-10 | P2: Evidência com esqueleto anotado + ângulos sobrepostos | Specify | Pending |
| POSE-11 | P3: Ambos os detetores executados sobre os mesmos frames | Specify | Pending |
| POSE-12 | P3: Múltiplos achados → múltiplos artefatos de evidência | Specify | Pending |
| POSE-13 | Edge: Frame sem pessoa → descartado da janela | Specify | Pending |
| POSE-14 | Edge: Vídeo curto demais → dados insuficientes | Specify | Pending |
| POSE-15 | Edge: Concorrência de runs não corrompe sidecar | Specify | Pending |
| POSE-16 | Edge: Vídeo corrompido → ErroDeAnalise | Specify | Pending |
| POSE-17 | Dimensão: Observabilidade (pessoas, findings, duração) | Specify | Pending |
| POSE-18 | Edge: num_poses > 1 mas só 1 pessoa → usa a única pose | Specify | Pending |
| POSE-19 | Edge: Ângulo NaN → frame descartado do contador | Specify | Pending |

**ID format:** `POSE-NN`

**Status values:** Pending → In Design → In Tasks → Implementing → Verified

**Coverage:** 19 total, 19 mapped, 0 unmapped

---

## Success Criteria

- [ ] Detector de quedas não dispara em agachamentos/inclinações (falso positivo zero
  no teste sintético com amplitude 0.35–0.50 durante 20 frames).
- [ ] Detector de quedas dispara corretamente em queda sustentada (>0.55 por ≥30
  frames consecutivos).
- [ ] Detetor de fisioterapia produz achados `POSTURAL_DEVIATION` e `TRUNK_TILT` com
  descrições em linguagem clínica e ângulos medidos.
- [ ] Ambos os detetores executados na mesma run sobre os mesmos frames extraídos.
- [ ] Evidência gerada em `output/video_pose/<run_id>/` com artefato anotado (esqueleto
  + articulações destacadas + ângulos) e sidecar JSON no contrato AD-026.
- [ ] Config YAML com todos os limiares (queda + fisioterapia) validados com defaults.
- [ ] Testes existentes da raia pose (VIDEO-01 a VIDEO-05, VIDEO-13, VIDEO-14)
  mantêm-se verdes (sem regressão).
