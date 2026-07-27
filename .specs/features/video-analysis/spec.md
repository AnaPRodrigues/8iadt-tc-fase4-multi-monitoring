# F1 — Video Analysis Specification

> **Nota de reconciliação (2026-07-21).** Esta spec foi reescrita para refletir a estrutura de
> **duas raias reais e abertas** (AD-033, AD-035, AD-039), substituindo a versão antiga
> (Cholec80-CVS / sequência de fases, AD-023 — abandonada porque não permitia pose estimation nem
> uma regra de "desvio de fase" com ground truth confiável). Verificado empiricamente nos dados já
> baixados por F0 antes de escrever as User Stories abaixo (Knowledge Verification Chain, Passo 1):
> URFD só fornece os RGB por sequência — o rótulo real é o **nome do diretório** (`fall-NN` = queda,
> `adl-NN` = ADL), não há anotação por frame do instante exato da queda; Endoscapes-BBox201 tem
> **anotação COCO real** (`annotation_coco.json`) com 6 classes (`cystic_plate`, `calot_triangle`,
> `cystic_artery`, `cystic_duct`, `gallbladder`, `tool`), o que torna a raia de objeto uma detecção
> real contra bounding boxes conhecidas — não mais "desvio de fase" (que exigiria uma anotação de
> fase cirúrgica que a spec antiga presumia sem verificar).

## Problem Statement

O enunciado exige duas coisas de vídeo: **análise postural** (Req.1) e **detecção de objeto/área
crítica** (Req.1), além de **padrões de movimentação do paciente** (Req.3). A F1 atende isso com
**duas raias, ambas com dado real aberto** (sem gravação do grupo, sem credenciamento):

- **Raia pose/movimento** (AD-039): **URFD** (UR Fall Detection) → **MediaPipe Pose** extrai
  keypoints por frame → assimetria, amplitude de movimento, velocidade e detecção de queda
  (variação brusca do centro de massa). Classificação **queda vs ADL** com métricas de
  precision/recall contra o rótulo real. Fecha Req.1 (postura) e Req.3 (movimentação).
- **Raia objeto/área crítica** (AD-033/035): frames cirúrgicos do **Endoscapes2023** →
  **YOLOv8 local** para instrumentos/objetos; na nuvem, keyframes → S3 → Lambda → `ImageAnalyzer`
  (adapter: Rekognition no cloud, YOLOv8 no local). Fecha Req.1 (detecção de objeto).

Cholec80-CVS (anotações XLSX, sem vídeo) permanece como enriquecimento opcional.

## Goals

- [ ] **Raia pose**: carregar sequências RGB do URFD (queda + ADL), extrair keypoints com MediaPipe Pose, calcular assimetria/amplitude/velocidade/queda e classificar queda vs ADL, com precision/recall/F1 contra o rótulo real.
- [ ] **Raia objeto**: rodar YOLOv8 sobre frames do Endoscapes para instrumentos/objetos; na nuvem, keyframes via `ImageAnalyzer` (Rekognition/YOLOv8 por `ENV`).
- [ ] Produzir evidência reproduzível das duas raias (frame anotado + JSON de eventos) no contrato único (AD-026), consumível pela fusão (F5).
- [ ] Gerar relatório automático por vídeo/sequência indicando desvios (Req.1).

## Out of Scope

| Feature | Reason |
| --- | --- |
| Anotação/reconstrução do instante exato da queda dentro da sequência (frame preciso) | URFD não fornece isso nos arquivos RGB baixados (só o nome do diretório como rótulo); a demo classifica a **sequência inteira** como queda/ADL, não o frame exato do evento |
| Treinamento de modelo de pose do zero (MediaPipe) | MediaPipe Pose é usado pré-treinado (Google); não há dataset/tempo para treinar um modelo de pose próprio |
| Treinamento de YOLOv8 do zero (sem pesos pré-treinados) | Fora do prazo de 7 dias; qualquer fine-tuning é leve, sobre pesos COCO pré-treinados, e sua viabilidade em CPU é confirmada no Design antes de comprometer o cronograma |
| Streaming de vídeo em tempo real | Abordagem é por frames amostrados/sequências em micro-batch, não frame-a-frame em baixa latência (consistente com AD-011 aplicado a vídeo) |
| Segmentação semântica (Endoscapes-Seg50) | O dataset também oferece máscaras de segmentação; a demo usa só a raia de detecção por bounding box (Endoscapes-BBox201), suficiente para "detecção de objeto/área crítica" |
| Reconhecimento do fluxo cirúrgico completo (fases/CVS) | Cholec80-CVS/Endoscapes-CVS201 (rótulo de Critical View of Safety) não são usados; o roteiro da demo (AD-008) cobre detecção de objeto/estrutura, não a avaliação completa de CVS |

---

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --- | --- | --- | --- |
| Ground truth de queda/ADL do URFD | Rótulo por **sequência inteira** (nome do diretório: `fall-NN`=queda, `adl-NN`=ADL), não por frame | Verificado nos dados já baixados: só há RGB por sequência, sem arquivo de anotação de instante exato | y |
| Ground truth de objeto/estrutura crítica do Endoscapes | `annotation_coco.json` de Endoscapes-BBox201 (formato COCO, 6 classes: `cystic_plate`, `calot_triangle`, `cystic_artery`, `cystic_duct`, `gallbladder`, `tool`) | Verificado no `README.md` e no arquivo real já baixado por F0 | y |
| Modelo YOLOv8 usado | Variante leve pré-treinada em COCO (YOLOv8n) como ponto de partida; fine-tuning leve sobre as 6 classes do Endoscapes-BBox201 (nenhuma delas existe em COCO) | AD-012 (CPU-only) — COCO não tem classes anatômicas cirúrgicas, então o modelo genérico não detectaria nada relevante sem fine-tuning; viabilidade em CPU (tempo de treino) a confirmar empiricamente no Design antes de comprometer o cronograma | n — a confirmar no Design |
| Seleção de keyframes para a nuvem (raia objeto) | Amostragem periódica de frames do subconjunto curado do Endoscapes, combinada com frames onde a raia local (YOLOv8) já detectou uma estrutura crítica | Reduz custo/volume de chamadas ao Rekognition (limite de 1000 detecções, AD-007) mantendo cobertura dos momentos relevantes | n — parâmetro de amostragem a calibrar no Design |
| Subconjunto de dados usado na demo | URFD: amostra curada das 70 sequências (não todas); Endoscapes-BBox201: amostra curada dos frames anotados (não os 1933 completos) | Processar o conjunto completo é desproporcional ao valor demonstrativo dentro do prazo | y |

**Open questions:** none — todas resolvidas ou registradas acima. Itens marcados "confirmed: n" exigem uma etapa de verificação técnica no Design (viabilidade do fine-tuning em CPU, parâmetro de amostragem), não uma decisão de produto em aberto.

---

## Implicit-Requirement Dimensions Sweep

| Dimensão | Cobertura |
| --- | --- |
| Input validation & bounds | Frame sem pessoa detectável (raia pose) ou fora do formato esperado é descartado sem travar o restante — ver VIDEO-13; anotação COCO ausente/malformada (raia objeto) é tratada como dado insuficiente daquele frame |
| Failure / partial-failure states | Sequência curta demais para uma janela é reportada como "dados insuficientes" — ver VIDEO-14; falha/limite do Rekognition não derruba o pipeline local — ver VIDEO-10 |
| Idempotency / retry / duplicate handling | Reenvio do mesmo keyframe ao S3 não deve duplicar o label anexado ao evento (dedupe por nome/hash do arquivo) — ver VIDEO-16 |
| Auth boundaries & rate limits | Lambda executa somente com a role `LabRole`; respeita limite de 10 execuções concorrentes e de 1000 detecções do Rekognition (AD-007) — ver VIDEO-10 |
| Concurrency / ordering | Sequências/vídeos processados no mesmo lote não misturam eventos/IDs entre si — ver VIDEO-15 |
| Data lifecycle / expiry | N/A because artefatos de evidência são gerados por execução de demo acadêmica sem requisito de retenção/expiração |
| Observability | Cada frame/sequência processado registra se a etapa de nuvem (Rekognition) foi bem-sucedida, pulada ou falhou, consumível por F5 |
| External-dependency failure | Falha/timeout ou limite do Rekognition tratado sem interromper o pipeline local — ver VIDEO-10 |
| State-transition integrity | N/A because F1 não possui máquina de estados própria; a classificação verde/amarelo/vermelho pertence a F5 |

---

## User Stories

### P1: Raia pose — detecção de queda vs. ADL (URFD + MediaPipe Pose) ⭐ MVP

**User Story**: Como integrante do grupo validando o pipeline, quero extrair keypoints de pose por
frame com MediaPipe e classificar uma sequência como queda ou atividade normal (ADL) a partir do
movimento do centro de massa, para provar detecção de evento com ground truth real antes de
integrar às demais fontes multimodais.

**Why P1**: Cobre a exigência obrigatória de "análise postural" (Req.1) e "padrões de movimentação
do paciente" (Req.3) com dado real rotulado, sendo a fatia que sustenta o relatório e o vídeo de
demo.

**Acceptance Criteria**:

1. WHEN uma sequência do URFD (`fall-NN` ou `adl-NN`) é carregada THEN o sistema SHALL extrair os keypoints de pose por frame via MediaPipe Pose.
2. WHEN os keypoints de uma sequência são processados THEN o sistema SHALL calcular, por janela, métricas de movimento derivadas do centro de massa (amplitude, velocidade) e assimetria postural.
3. WHEN a variação do centro de massa em alguma janela da sequência excede o limiar configurado (descida abrupta) THEN o sistema SHALL classificar a sequência inteira como "queda"; caso nenhuma janela exceda o limiar, classificar como "ADL".
4. WHEN a classificação da sequência é comparada ao rótulo real (nome do diretório: `fall-NN` = queda, `adl-NN` = ADL) THEN o sistema SHALL calcular precision, recall e F1, salvos em relatório de métricas.
5. WHEN uma sequência é classificada como queda THEN o sistema SHALL gerar evidência reproduzível: frame anotado (keypoints desenhados) no momento do evento + metadados (sequência, frame, score) no contrato único (AD-026).

**Independent Test**: Rodar o pipeline sobre um subconjunto curado de sequências do URFD (queda + ADL) e verificar que (a) o relatório de precision/recall/F1 contra o rótulo real (nome do diretório) é gerado, e (b) existe evidência (frame anotado + metadados) para cada sequência classificada como queda.

---

### P2: Raia objeto — detecção de estruturas críticas (Endoscapes + YOLOv8 local / Rekognition cloud)

**User Story**: Como integrante do grupo, quero detectar estruturas anatômicas críticas e
instrumentos em frames cirúrgicos com YOLOv8 (local) ou Rekognition (nuvem), comparando contra a
anotação COCO real do Endoscapes-BBox201, para provar detecção de objeto/área crítica com ground
truth real e demonstrar a integração com serviços gerenciados de IA exigida pelo desafio.

**Why P2**: Cobre a exigência obrigatória de "detecção de objeto/área crítica" (Req.1, YOLOv8) e
"integração com serviços gerenciados em nuvem"; a raia local (YOLOv8) já demonstra o pipeline
inteiro sem depender da nuvem, que é um complemento (Rekognition via `ImageAnalyzer`, AD-035).

**Acceptance Criteria**:

1. WHEN um frame do Endoscapes-BBox201 é carregado com sua anotação (`annotation_coco.json`) THEN o sistema SHALL extrair as caixas delimitadoras reais das 6 classes (`cystic_plate`, `calot_triangle`, `cystic_artery`, `cystic_duct`, `gallbladder`, `tool`) como ground truth.
2. WHEN o frame é processado por `ImageAnalyzer` (YOLOv8 local via `env=local`; Rekognition via `env=cloud`) THEN o sistema SHALL obter os objetos/labels detectados no frame.
3. WHEN os objetos detectados são comparados às caixas reais da anotação THEN o sistema SHALL calcular precision, recall e F1 por classe, salvos em relatório de métricas.
4. WHEN uma estrutura crítica (`cystic_artery`, `cystic_duct` ou `cystic_plate`) é detectada num frame THEN o sistema SHALL gerar evidência reproduzível: frame anotado (caixas desenhadas) + metadados (classe, confiança, frame) no contrato único (AD-026).
5. WHEN o Rekognition falha, expira por timeout, ou o limite de 1000 detecções (AD-007) é atingido THEN o sistema SHALL registrar o erro/limite no CloudWatch e continuar o restante do pipeline local sem depender da nuvem para funcionar.

**Independent Test**: Rodar o pipeline local (YOLOv8) sobre um subconjunto curado de frames anotados do Endoscapes-BBox201 e verificar que (a) o relatório de precision/recall/F1 por classe contra a anotação COCO real é gerado, e (b) existe evidência para cada estrutura crítica detectada; enviar um pequeno lote de frames ao Rekognition (via S3→Lambda) e confirmar que os labels aparecem como evidência complementar, e que uma falha simulada do Rekognition não interrompe a raia local.

---

### P3: Relatório automático consolidado (ambas as raias)

**User Story**: Como equipe médica, quero um relatório automático por sequência/vídeo resumindo os
eventos detectados (pose e/ou objeto), para revisão rápida sem abrir o JSON bruto de eventos.

**Why P3**: Cobre a exigência de "gerar relatórios automáticos indicando desvios ou falhas no
procedimento"; é uma camada de apresentação sobre os eventos já produzidos por P1/P2.

**Acceptance Criteria**:

1. WHEN o processamento de uma sequência/vídeo é concluído (raia pose e/ou raia objeto, conforme aplicável) THEN o sistema SHALL gerar um relatório legível (Markdown/HTML), listando cada evento detectado com timestamp/frame, tipo (queda, estrutura crítica) e link para a evidência.
2. WHEN nenhum evento é detectado numa sequência/vídeo THEN o sistema SHALL gerar o relatório indicando explicitamente "nenhum evento detectado", em vez de omitir o relatório.

**Independent Test**: Processar uma sequência/vídeo com eventos conhecidos e outra sem eventos; confirmar que ambas geram relatório, uma listando os eventos e a outra declarando ausência de eventos.

---

## Edge Cases

- WHEN o MediaPipe Pose não detecta nenhuma pessoa com confiança suficiente num frame THEN o sistema SHALL descartar esse frame da janela de movimento, sem interromper o restante da sequência.
- WHEN uma sequência do URFD é curta demais para formar uma janela completa THEN o sistema SHALL reportar "dados insuficientes" para aquela sequência em vez de falhar silenciosamente ou lançar exceção não tratada.
- WHEN o YOLOv8/Rekognition não detecta nenhuma estrutura/instrumento num frame THEN o sistema SHALL classificá-lo como "nenhuma estrutura visível", distinto de uma falha de processamento.
- WHEN o limite de detecções do Rekognition (1000, AD-007) é atingido durante o processamento de um lote THEN o sistema SHALL interromper apenas o envio à nuvem (raia objeto, complemento), preservando os resultados locais já obtidos.
- WHEN duas ou mais sequências/vídeos são processados no mesmo lote THEN o sistema SHALL manter os eventos/evidências de cada um isolados, sem mistura de IDs ou timestamps entre si.
- WHEN o mesmo keyframe é reenviado ao S3 (reprocessamento) THEN o sistema SHALL evitar duplicar o label anexado ao evento correspondente.

---

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
| --- | --- | --- | --- |
| VIDEO-01 | P1: Carga de sequência URFD + extração de keypoints (MediaPipe Pose) | Tasks | ✅ Verified |
| VIDEO-02 | P1: Métricas de movimento por janela (centro de massa, assimetria) | Tasks | ✅ Verified |
| VIDEO-03 | P1: Classificação da sequência como queda ou ADL | Tasks | ✅ Verified |
| VIDEO-04 | P1: Métricas precision/recall/F1 da raia pose contra o rótulo real | Tasks | ✅ Verified |
| VIDEO-05 | P1: Evidência da raia pose (frame anotado + metadados) | Tasks | ✅ Verified |
| VIDEO-06 | P2: Carga de frame Endoscapes-BBox201 + anotação COCO real | Tasks | ✅ Verified |
| VIDEO-07 | P2: Detecção via `ImageAnalyzer` (YOLOv8 local / Rekognition cloud) | Tasks | ✅ Verified |
| VIDEO-08 | P2: Métricas precision/recall/F1 por classe contra anotação COCO | Tasks | ✅ Verified |
| VIDEO-09 | P2: Evidência da raia objeto (frame anotado + metadados) | Tasks | ✅ Verified |
| VIDEO-10 | P2: Tratamento de falha/limite do Rekognition | Tasks | ⚠️ Verified with gap (CloudWatch-observability assertion missing) |
| VIDEO-11 | P3: Relatório automático consolidado (ambas as raias) | Tasks | ✅ Verified |
| VIDEO-12 | P3: Relatório mesmo sem eventos detectados | Tasks | ✅ Verified |
| VIDEO-13 | Edge: frame sem pessoa detectável descartado da janela (raia pose) | Tasks | ✅ Verified |
| VIDEO-14 | Edge: sequência curta demais para uma janela ("dados insuficientes") | Tasks | ✅ Verified |
| VIDEO-15 | Edge: isolamento de eventos entre sequências/vídeos no mesmo lote | Tasks | ✅ Verified |
| VIDEO-16 | Dimensão: dedupe de keyframe reenviado ao S3 | Tasks | ✅ Verified |

**ID format:** `VIDEO-NN`

**Status values:** Pending → In Design → In Tasks → Implementing → Verified

**Coverage:** 16 total, 16 mapped to tasks, 0 unmapped — 15/16 Verified, 1 Verified with gap (VIDEO-10, minor, non-blocking; ver validation.md)

---

## Success Criteria

- [ ] Raia pose (MediaPipe) roda ponta a ponta sobre um subconjunto do URFD com um único comando, produzindo precision/recall/F1 de queda-vs-ADL contra o rótulo real sem intervenção manual.
- [ ] Raia objeto (YOLOv8) roda ponta a ponta sobre um subconjunto do Endoscapes-BBox201, produzindo precision/recall/F1 por classe contra a anotação COCO real sem intervenção manual.
- [ ] Ao menos um lote de frames processado com sucesso pelo Rekognition, com labels anexados como evidência complementar.
- [ ] Relatório automático gerado para cada sequência/vídeo processado (com ou sem eventos).
- [ ] Toda anomalia detectada tem evidência visual/textual correspondente na saída (critério de aceite global do projeto).

---
## Amendment 1 — Suporte a ficheiros de vídeo (2026-07-25)

**Contexto:** O enunciado exige "Processar vídeos clínicos (ex: sessões de fisioterapia
ou cirurgias gravadas)". Até esta emenda, o sistema só aceitava sequências de PNGs
(formato URFD, raia pose) e JPEGs únicos (formato Endoscapes, raia objeto). Com esta
emenda, ficheiros de vídeo reais (.mp4, .avi, .mov, .mkv, .webm) são aceites em ambas
as raias via upload pelo frontend. A extração de frames usa `cv2.VideoCapture`
(`opencv-python>=4.9` já presente no projeto). Nenhuma dependência nova.

**AD relacionada:** AD-054 (STATE.md)

### P4: Upload de ficheiro de vídeo → análise de postura/movimentação ⭐

**User Story**: Como utilizador do painel, quero fazer upload de um ficheiro de vídeo
(.mp4, .avi, etc.) com modalidade "Vídeo — movimentação", e que o sistema extraia os
frames, aplique o MediaPipe Pose e classifique queda/ADL, sem eu precisar converter o
vídeo para PNGs manualmente.

**Why P4**: Remove a barreira artificial de "só diretórios de PNGs" que contradizia o
enunciado. Um ficheiro .mp4 é o formato natural de vídeo; o sistema deve aceitá-lo.

**Acceptance Criteria**:

1. WHEN um ficheiro com extensão de vídeo (.mp4, .avi, .mov, .mkv, .webm) é enviado
   com modalidade "video" THEN o sistema SHALL extrair frames com `cv2.VideoCapture`
   e encaminhá-los para o pipeline de pose/movimentação.
2. WHEN o vídeo tem menos frames que o tamanho mínimo da janela de movimento (30
   frames) THEN o sistema SHALL devolver "Vídeo muito curto para análise" com
   `pontuacao=None`.
3. WHEN o vídeo não contém pessoas em nenhum frame THEN o sistema SHALL devolver "Sem
   queda detectada" com a nota "Nenhuma pessoa identificada" e `pontuacao=0.0`.
4. WHEN o vídeo é corrompido ou ilegível THEN o sistema SHALL devolver `ErroDeAnalise`
   com mensagem clara, sem crash.
5. WHEN uma queda é detectada THEN o sistema SHALL gerar evidência no mesmo contrato
   da raia pose (frame anotado + JSON), com `formato: video` nos detalhes.

**Independent Test**: Gerar um .mp4 sintético com `cv2.VideoWriter`, enviar via
`_analisar_video()`, verificar que o dispatch roteia para o pipeline de pose e devolve
`ResultadoAnalise` com `detalhes.formato == "video"`. Testar vídeo corrompido,
curto, e regressão de JPEG (continua no ramo cirúrgico).

### P5: Upload de vídeo cirúrgico → YOLOv8 por keyframe

**User Story**: Como utilizador do painel, quero fazer upload de um vídeo cirúrgico
com a nova modalidade "Vídeo — cirurgia", e que o sistema extraia keyframes a cada 2
segundos e rode o YOLOv8 (ou Rekognition, conforme `ENV`) em cada um, agregando as
estruturas críticas encontradas.

**Why P5**: O enunciado exemplifica "vídeos de cirurgias" para detecção de objeto/área
crítica. Antes desta emenda, a raia objeto só aceitava um JPEG único — o que não é um
vídeo.

**Acceptance Criteria**:

1. WHEN um ficheiro de vídeo é enviado com a nova modalidade "video_cirurgico" THEN o
   sistema SHALL extrair um keyframe a cada 2 segundos e analisar cada um com o
   `ImageAnalyzer` (YOLOv8 local ou Rekognition cloud, conforme `ENV`).
2. WHEN uma estrutura crítica (`cystic_artery`, `cystic_duct`, `cystic_plate`) é
   detectada em pelo menos um keyframe THEN o sistema SHALL devolver um resumo
   agregado com os nomes clínicos (ex.: "artéria cística, ducto cístico") e o
   instante da primeira detecção, com `pontuacao=1.0`.
3. WHEN nenhuma estrutura crítica é detectada em nenhum keyframe THEN o sistema SHALL
   devolver "Nenhuma estrutura crítica identificada no vídeo cirúrgico" com
   `pontuacao=0.0`.
4. WHEN o ficheiro enviado em "video_cirurgico" é uma imagem (.jpg, .png) THEN o
   sistema SHALL analisá-lo como quadro único (comportamento idêntico ao antigo
   `_analisar_quadro_cirurgico`), mantendo compatibilidade.
5. WHEN o vídeo não pode ser aberto THEN o sistema SHALL devolver `ErroDeAnalise`.

**Independent Test**: Gerar .mp4 sintético, dublar o `ImageAnalyzer` para devolver
`cystic_duct`, verificar `pontuacao=1.0`, resumo com "ducto cístico", e
`detalhes.formato == "video"`. Testar vídeo sem estruturas críticas → pontuação 0.
Testar JPEG → dispatch para quadro único.

---
## Requirement Traceability (atualizada)

| Requirement ID | Story | Phase | Status |
| --- | --- | --- | --- |
| VIDEO-01 | P1: Carga de sequência URFD + extração de keypoints (MediaPipe Pose) | Tasks | ✅ Verified |
| VIDEO-02 | P1: Métricas de movimento por janela (centro de massa, assimetria) | Tasks | ✅ Verified |
| VIDEO-03 | P1: Classificação da sequência como queda ou ADL | Tasks | ✅ Verified |
| VIDEO-04 | P1: Métricas precision/recall/F1 da raia pose contra o rótulo real | Tasks | ✅ Verified |
| VIDEO-05 | P1: Evidência da raia pose (frame anotado + metadados) | Tasks | ✅ Verified |
| VIDEO-06 | P2: Carga de frame Endoscapes-BBox201 + anotação COCO real | Tasks | ✅ Verified |
| VIDEO-07 | P2: Detecção via `ImageAnalyzer` (YOLOv8 local / Rekognition cloud) | Tasks | ✅ Verified |
| VIDEO-08 | P2: Métricas precision/recall/F1 por classe contra anotação COCO | Tasks | ✅ Verified |
| VIDEO-09 | P2: Evidência da raia objeto (frame anotado + metadados) | Tasks | ✅ Verified |
| VIDEO-10 | P2: Tratamento de falha/limite do Rekognition | Tasks | ⚠️ Verified with gap |
| VIDEO-11 | P3: Relatório automático consolidado (ambas as raias) | Tasks | ✅ Verified |
| VIDEO-12 | P3: Relatório mesmo sem eventos detectados | Tasks | ✅ Verified |
| VIDEO-13 | Edge: frame sem pessoa detectável descartado da janela (raia pose) | Tasks | ✅ Verified |
| VIDEO-14 | Edge: sequência curta demais para uma janela ("dados insuficientes") | Tasks | ✅ Verified |
| VIDEO-15 | Edge: isolamento de eventos entre sequências/vídeos no mesmo lote | Tasks | ✅ Verified |
| VIDEO-16 | Dimensão: dedupe de keyframe reenviado ao S3 | Tasks | ✅ Verified |
| **VIDEO-17** | **P4**: Dispatch de .mp4 para pipeline de pose no upload | **Done** | 🟡 Implemented |
| **VIDEO-18** | **P4**: Vídeo curto demais (< 30 frames) → mensagem clara | **Done** | 🟡 Implemented |
| **VIDEO-19** | **P4**: Vídeo sem pessoas → "Nenhuma pessoa identificada" | **Done** | 🟡 Implemented |
| **VIDEO-20** | **P4**: Vídeo corrompido → ErroDeAnalise | **Done** | 🟡 Implemented |
| **VIDEO-21** | **P4**: Evidência de queda com `formato: video` | **Done** | 🟡 Implemented |
| **VIDEO-22** | **P5**: Keyframes a cada 2 s → YOLOv8 em cada um | **Done** | 🟡 Implemented |
| **VIDEO-23** | **P5**: Estrutura crítica detectada → resumo clínico agregado | **Done** | 🟡 Implemented |
| **VIDEO-24** | **P5**: Nenhuma estrutura → pontuação 0, sem evidência | **Done** | 🟡 Implemented |
| **VIDEO-25** | **P5**: Imagem JPEG em video_cirurgico → quadro único | **Done** | 🟡 Implemented |
| **VIDEO-26** | **P5**: Vídeo ilegível → ErroDeAnalise | **Done** | 🟡 Implemented |
| **VIDEO-27** | **P4**: Regressão — JPEG continua no ramo cirúrgico | **Done** | 🟡 Implemented |
| **VIDEO-28** | **P4**: Regressão — diretório URFD continua no ramo pose | **Done** | 🟡 Implemented |
