# F1 — Video Analysis Tasks

## Execution Protocol (MANDATORY -- do not skip)

Implement these tasks with the `tlc-spec-driven` skill: **activate it by name and follow its Execute flow and Critical Rules.** Do not search for skill files by filesystem path.

**If the skill cannot be activated, STOP and tell the user.**

**Sub-agent trigger**: 13 tasks — exceeds the ~8 single-batch budget. Per the skill's Sub-Agent Delegation rule, **the offer-then-confirm step is mandatory before Execute starts**: present 2 batches (T1-T7, T8-T13) for the user to accept before dispatching any worker.

---

**Design**: `.specs/features/video-analysis/design.md`
**Status**: Draft

---

## Test Coverage Matrix

> Mesmo princípio de F0/F3/F4: domínio puro (mesmo que use MediaPipe/YOLOv8 localmente, sem AWS)
> vira unit; qualquer coisa que toque um cliente AWS real (S3, Lambda) vira integration contra
> **LocalStack real**.

| Code Layer | Required Test Type | Coverage Expectation | Location Pattern | Run Command |
| --- | --- | --- | --- | --- |
| Raia pose (`pose_loader`, `pose`, `pose_features`, `pose_detector`, `pose_evaluate`) | unit | Todos os ramos; ACs VIDEO-01..05, 13, 14; usa dado real do URFD (não mock) | `backend/tests/video/test_pose_*.py` | `pytest -q -m "not integration"` |
| Raia objeto (`object_loader`, `object_finetune`, `object_detector`, `object_evaluate`, `adapters.YoloImageAnalyzer`) | unit | ACs VIDEO-06..09; usa dado real do Endoscapes-BBox201 (não mock) | `backend/tests/video/test_object_*.py` | `pytest -q -m "not integration"` |
| `report.py` (consolidação) | unit | ACs VIDEO-11, 12, 15 | `backend/tests/video/test_report.py` | `pytest -q -m "not integration"` |
| `handler.py` + `infra.py` (Lambda real, gatilho S3) | integration | ACs VIDEO-07 (raia cloud), 10, 16; deploy real no LocalStack, evento S3 real | `backend/tests/integration/test_video_*.py` | `pytest -q` (requer `make localstack-up`) |

## Gate Check Commands

| Gate Level | When to Use | Command |
| --- | --- | --- |
| Quick | Após tarefas só com testes unitários | `pytest -q -m "not integration"` |
| Full | Após tarefas com testes de integração | `pytest -q` |
| Build | Fim de fase | `make lint && pytest -q -m "not integration"` (integração exige LocalStack de pé, roda separado) |

---

## Execution Plan

13 tarefas em 13 fases (uma tarefa por fase). Excede o budget de ~8 tarefas de um único batch →
**oferecer sub-agentes** antes do Execute, em 2 batches consecutivos (nunca dividir uma fase):

```
Batch 1 (T1-T7): raia pose completa + início da raia objeto (loader + fine-tuning)
Batch 2 (T8-T13): raia objeto (detector + evaluate + adapter) + complemento cloud + relatório
```

### Phase 1: `pose_loader.py`
```
T1
```
### Phase 2: `pose.py` (MediaPipe)
```
T2
```
### Phase 3: `pose_features.py`
```
T3
```
### Phase 4: `pose_detector.py` + evidência
```
T4
```
### Phase 5: `pose_evaluate.py`
```
T5
```
### Phase 6: `object_loader.py`
```
T6
```
### Phase 7: `object_finetune.py`
```
T7
```
### Phase 8: `object_detector.py` + evidência
```
T8
```
### Phase 9: `object_evaluate.py`
```
T9
```
### Phase 10: `adapters.py`
```
T10
```
### Phase 11: `handler.py`
```
T11
```
### Phase 12: `infra.py`
```
T12
```
### Phase 13: `report.py`
```
T13
```

---

## Task Breakdown

### T1: `pose_loader.py` — carga de sequência URFD

**What**: Carrega uma sequência do URFD (lista ordenada de frames + rótulo real derivado do nome do diretório).
**Where**: `backend/pipelines/video/pose_loader.py`, `backend/pipelines/video/models.py` (dataclasses `Sequence`, `PoseFrame`, `MovementWindow`, `SequenceVerdict`), `backend/tests/video/test_pose_loader.py`
**Depends on**: None
**Reuses**: —
**Requirement**: VIDEO-01 (carga)

**Tools**: MCP: NONE · Skill: NONE

**Done when**:
- [ ] `load_sequence(seq_dir: Path) -> Sequence` lê os PNGs em ordem numérica (não ordem alfabética ingênua — `frame-9` antes de `frame-10` seria um bug clássico) e deriva `label` de `"fall-NN"`→`"fall"`/`"adl-NN"`→`"adl"`
> Diretório desconhecido (nem `fall-` nem `adl-`) → `ValueError` explícito, nunca um rótulo adivinhado.
- [ ] Testado com uma sequência **real** já baixada por F0 (`data/urfd/fall-01/` ou `adl-01/`), não um diretório fabricado
- [ ] Gate: `pytest -q -m "not integration"` · Test count: ≥ 4

**Tests**: unit · **Gate**: quick
**Commit**: `feat(f1): carga de sequencia URFD com rotulo real`

---

### T2: `pose.py` — extração de keypoints via MediaPipe (Task API)

**What**: `ensure_pose_model` (baixa o modelo `.task` sob demanda, idempotente) + `extract_keypoints` (roda o `PoseLandmarker` num frame real).
**Where**: `backend/pipelines/video/pose.py`, `backend/tests/video/test_pose.py`
**Depends on**: T1
**Reuses**: `pose_loader.load_sequence` (para obter um frame real de teste)
**Requirement**: VIDEO-01 (extração), VIDEO-13 (frame sem pessoa)

**Tools**: MCP: NONE · Skill: NONE

**Done when**:
- [ ] `ensure_pose_model(cache_dir)` baixa `pose_landmarker_lite.task` de `storage.googleapis.com/mediapipe-models/...` se ausente; segunda chamada não rebaixa (checar antes de baixar, mesmo padrão idempotente do projeto)
- [ ] `extract_keypoints(frame_path, landmarker)` usa a **Task API** (`mediapipe.tasks.python.vision.PoseLandmarker`, não `mp.solutions.pose` — confirmado ausente na versão instalada) e devolve `PoseFrame` com 33 landmarks
- [ ] Frame sem pessoa detectável (ex.: fundo vazio/patch preto) devolve `None`, nunca lança exceção nem inventa landmarks
- [ ] Testado com um frame **real** de `data/urfd/` (mesmo frame já usado no REPL desta sessão: `fall-01-cam0-rgb-050.png`), confirmando 33 landmarks
- [ ] Gate: `pytest -q -m "not integration"` · Test count: ≥ 4

**Tests**: unit · **Gate**: quick
**Commit**: `feat(f1): extracao de keypoints via MediaPipe PoseLandmarker`

---

### T3: `pose_features.py` — métricas de movimento por janela

**What**: Calcula, por janela de frames, amplitude/velocidade do centro de massa (derivado dos landmarks de quadril) e assimetria postural.
**Where**: `backend/pipelines/video/pose_features.py`, `backend/tests/video/test_pose_features.py`
**Depends on**: T2
**Reuses**: `models.PoseFrame`/`MovementWindow`
**Requirement**: VIDEO-02

**Tools**: MCP: NONE · Skill: NONE

**Done when**:
- [ ] `windowed_features(frames: list[PoseFrame | None], window_size) -> list[MovementWindow]` computa centro de massa como a média dos landmarks de quadril (índices 23/24 do MediaPipe Pose)
- [ ] Frame `None` (sem pessoa) dentro de uma janela é excluído do cálculo daquela janela, sem quebrar o restante; janela sem nenhum frame válido não é gerada (não um `MovementWindow` com valores zerados/inventados)
- [ ] Testes: janela com movimento estável (baixa amplitude); janela com queda simulada (variação abrupta sintética conhecida, para isolar a métrica); janela com frames `None` intercalados
- [ ] Gate: `pytest -q -m "not integration"` · Test count: ≥ 4

**Tests**: unit · **Gate**: quick
**Commit**: `feat(f1): metricas de movimento por janela (centro de massa, assimetria)`

---

### T4: `pose_detector.py` — classificação da sequência + evidência

**What**: Classifica a sequência inteira como `"queda"`/`"adl"`/`"dados_insuficientes"`, e gera evidência (frame com keypoints desenhados) quando `"queda"`.
**Where**: `backend/pipelines/video/pose_detector.py`, `backend/tests/video/test_pose_detector.py`
**Depends on**: T3
**Reuses**: `pose_features.windowed_features`, `common.evidence.save_evidence`
**Requirement**: VIDEO-03, VIDEO-05, VIDEO-14

**Tools**: MCP: NONE · Skill: NONE

**Done when**:
- [ ] `classify_sequence(windows, threshold)` → `"queda"` se **qualquer** janela exceder o threshold de amplitude do centro de massa; `"adl"` se nenhuma exceder; `"dados_insuficientes"` se `windows` estiver vazio (sequência curta demais) — nunca `"adl"` por omissão nesse caso
- [ ] Quando o veredito é `"queda"`, gera evidência via `common.evidence.save_evidence` (frame com keypoints desenhados via OpenCV + metadados: sequência, frame do evento, score) no contrato único (AD-026)
- [ ] Testes: sequência com salto real de amplitude (queda); sequência estável (adl); sequência vazia (dados insuficientes); evidência gerada de fato no disco para o caso de queda
- [ ] Gate: `pytest -q -m "not integration"` · Test count: ≥ 4

**Tests**: unit · **Gate**: quick
**Commit**: `feat(f1): classificacao de sequencia queda-vs-adl e evidencia`

---

### T5: `pose_evaluate.py` — precision/recall/F1 da raia pose

**What**: Compara os veredictos preditos com o rótulo real do URFD.
**Where**: `backend/pipelines/video/pose_evaluate.py`, `backend/tests/video/test_pose_evaluate.py`
**Depends on**: T1, T4
**Reuses**: `common.metrics.binary_metrics`/`save_report`, `models.SequenceVerdict`
**Requirement**: VIDEO-04

**Tools**: MCP: NONE · Skill: NONE

**Done when**:
- [ ] `evaluate(verdicts: list[SequenceVerdict]) -> MetricsReport` compara `predicted` (`"queda"`) contra `label` (`"fall"`) — mapeamento explícito, não comparação de string frouxa
- [ ] Veredictos `"dados_insuficientes"` são **excluídos** do cálculo (não contam como TP/FP/FN), mesmo princípio de VITALS-10/PRESC-14
- [ ] Testes: conjunto misto queda/adl bate com o rótulo; veredito "dados_insuficientes" excluído do cálculo (teste que discrimina de verdade, não um `support==0` que seria 0 de qualquer jeito); nenhuma queda no conjunto → recall indefinido (`None`, não `0.0`)
- [ ] Gate: `pytest -q -m "not integration"` · Test count: ≥ 3

**Tests**: unit · **Gate**: quick
**Commit**: `feat(f1): avaliacao precision-recall da raia pose`

---

### T6: `object_loader.py` — carga de frame + anotação COCO real

**What**: Carrega frames do Endoscapes-BBox201 com sua anotação COCO real (`annotation_coco.json`).
**Where**: `backend/pipelines/video/object_loader.py`, `backend/tests/video/test_object_loader.py`
**Depends on**: None
**Reuses**: `models.BoundingBox`/`AnnotatedFrame`
**Requirement**: VIDEO-06

**Tools**: MCP: NONE · Skill: NONE

**Done when**:
- [ ] `load_annotated_frames(coco_json, images_dir) -> list[AnnotatedFrame]` parseia o COCO real (categorias `cystic_plate`/`calot_triangle`/`cystic_artery`/`cystic_duct`/`gallbladder`/`tool`), mapeando `category_id`→nome via a seção `categories` do JSON (nunca hardcoded a partir do índice)
- [ ] Frame listado em `images` sem nenhuma anotação em `annotations` → `AnnotatedFrame(boxes=[])`, não descartado (frame legitimamente sem estrutura anotada)
- [ ] Testado contra o `annotation_coco.json` **real** já baixado por F0 (`data/endoscapes/endoscapes/train/`)
- [ ] Gate: `pytest -q -m "not integration"` · Test count: ≥ 3

**Tests**: unit · **Gate**: quick
**Commit**: `feat(f1): carga de frames e anotacao COCO real do Endoscapes`

---

### T7: `object_finetune.py` — fine-tuning leve do YOLOv8n

**What**: Converte a anotação COCO para o formato YOLO e roda um fine-tuning leve do YOLOv8n sobre as 6 classes.
**Where**: `backend/pipelines/video/object_finetune.py`, `backend/tests/video/test_object_finetune.py`
**Depends on**: T6
**Reuses**: `object_loader.load_annotated_frames`

**Achado já verificado (não repetir)**: conversão COCO→YOLO (`ultralytics.data.converter.convert_coco`) e uma época real de treino sobre 20 imagens reais do Endoscapes rodaram em ~9s em CPU nesta sessão — confirma viabilidade.

**Requirement**: Suporte a VIDEO-07/08 (o modelo fine-tuned é o que `object_detector.py` usa)

**Tools**: MCP: NONE · Skill: NONE

**Done when**:
- [ ] `finetune(coco_json, images_dir, output_dir, epochs, imgsz) -> Path` converte a anotação real para formato YOLO e treina, devolvendo o caminho dos pesos resultantes (`best.pt`)
- [ ] Teste executa um fine-tuning **real** (poucas imagens/poucas épocas, não mockado) e confirma que o arquivo de pesos resultante existe e é carregável por `ultralytics.YOLO(...)`
- [ ] Diretório de saída (`runs/`, pesos) não polui a raiz do repo — usa `tmp_path`/diretório configurável, nunca o cwd padrão do ultralytics
- [ ] Gate: `pytest -q -m "not integration"` · Test count: ≥ 2 (execução real é lenta; poucos testes, mas reais)

**Tests**: unit · **Gate**: quick
**Commit**: `feat(f1): fine-tuning leve do YOLOv8n sobre as classes do Endoscapes`

---

### T8: `object_detector.py` — detecção via YOLOv8 + evidência

**What**: `YoloDetector` (pesos fine-tuned) devolve `Detection(class_name, confidence, bbox)`; gera evidência quando uma estrutura crítica é detectada.
**Where**: `backend/pipelines/video/object_detector.py`, `backend/tests/video/test_object_detector.py`
**Depends on**: T6, T7
**Reuses**: `object_finetune.finetune` (para obter pesos de teste), `common.evidence.save_evidence`
**Requirement**: VIDEO-07 (raia local), VIDEO-09

**Tools**: MCP: NONE · Skill: NONE

**Done when**:
- [ ] `class YoloDetector: def detect(self, image_path) -> list[Detection]` carrega os pesos fine-tuned e devolve bbox+classe+confiança reais
- [ ] Frame sem nenhuma detecção → lista vazia, distinto de uma falha (edge case da spec)
- [ ] Quando uma estrutura crítica (`cystic_artery`/`cystic_duct`/`cystic_plate`) é detectada, gera evidência (frame com caixas desenhadas via OpenCV + metadados) no contrato único (AD-026)
- [ ] Testado com pesos reais (fine-tuned em T7) sobre um frame real do Endoscapes
- [ ] Gate: `pytest -q -m "not integration"` · Test count: ≥ 3

**Tests**: unit · **Gate**: quick
**Commit**: `feat(f1): deteccao via YOLOv8 fine-tuned e evidencia de estrutura critica`

---

### T9: `object_evaluate.py` — precision/recall/F1 por classe vs COCO

**What**: Casa as detecções com as caixas reais (IoU) e calcula precision/recall/F1 por classe.
**Where**: `backend/pipelines/video/object_evaluate.py`, `backend/tests/video/test_object_evaluate.py`
**Depends on**: T6, T8
**Reuses**: `common.metrics.binary_metrics`/`save_report`

**Achado a verificar nesta tarefa (não presumir)**: limiar de IoU para considerar uma detecção como "acerto" (convenção comum é 0.5 — confirmar se faz sentido para bboxes do Endoscapes, cujas estruturas anatômicas podem ser maiores/mais difusas que objetos COCO típicos).

**Requirement**: VIDEO-08

**Tools**: MCP: NONE · Skill: NONE

**Done when**:
- [ ] `evaluate(annotated_frames, detections_by_frame) -> dict[str, MetricsReport]` casa detecção↔caixa real por IoU ≥ limiar, um relatório por classe
- [ ] Classe sem nenhuma instância real no subconjunto avaliado → `support=0`, métricas `None` (indefinido, não zero)
- [ ] Testes: detecção correta bate com a caixa real (IoU alto); detecção com IoU baixo não conta como acerto; classe ausente do subconjunto tem `support=0`
- [ ] Gate: `pytest -q -m "not integration"` · Test count: ≥ 3

**Tests**: unit · **Gate**: quick
**Commit**: `feat(f1): avaliacao precision-recall por classe da raia objeto`

---

### T10: `adapters.py` — `YoloImageAnalyzer` (ImageAnalyzer local)

**What**: Implementação local de `ImageAnalyzer` (AD-035) que envolve `YoloDetector`, para o complemento cloud (Lambda).
**Where**: `backend/pipelines/video/adapters.py`, `backend/tests/video/test_adapters.py`
**Depends on**: T8
**Reuses**: `aws.adapters.ImageAnalysis`/`ImageLabel`/`register_image_analyzer`, `object_detector.YoloDetector`
**Requirement**: VIDEO-07 (raia local via adapter)

**Tools**: MCP: NONE · Skill: NONE

**Done when**:
- [ ] `YoloImageAnalyzer.analyze(image_bytes) -> ImageAnalysis` usa `YoloDetector` internamente, expõe `ImageLabel(name, confidence)` por detecção (o contrato existente da fundação não tem bbox — só a raia local via `object_detector.py` expõe bbox)
- [ ] `register_local_adapters()` registra para `env="local"`; após o registro, `get_image_analyzer("local")` devolve uma instância de `YoloImageAnalyzer`
- [ ] Testado com um frame real do Endoscapes, confirmando que os labels batem com o que `YoloDetector.detect` devolveria
- [ ] Gate: `pytest -q -m "not integration"` · Test count: ≥ 3

**Tests**: unit · **Gate**: quick
**Commit**: `feat(f1): YoloImageAnalyzer e registro do adapter local`

---

### T11: `handler.py` — Lambda fino do complemento cloud

**What**: Lê o evento S3, chama `get_image_analyzer().analyze()`, anexa labels como evidência complementar.
**Where**: `backend/pipelines/video/handler.py`, `backend/tests/integration/test_video_handler.py`
**Depends on**: T10
**Reuses**: `aws.clients.get_client`, `aws.adapters.get_image_analyzer`, `common.evidence.save_evidence`, padrão de `pipelines/prescription/handler.py`
**Requirement**: VIDEO-10, VIDEO-16

**Tools**: MCP: NONE · Skill: NONE

**Done when**:
- [ ] `lambda_handler(event, context)` lê o evento S3 (bucket/key/etag), baixa o objeto via `get_client("s3")`, chama `get_image_analyzer().analyze()`, salva evidência complementar
- [ ] Falha/timeout do `ImageAnalyzer` é logada e o processamento segue sem propagar exceção (não trava o lote) — mesmo padrão de PRESC-07
- [ ] Reenvio do mesmo objeto S3 (mesma chave/ETag) não duplica a evidência anexada — nome do artefato de evidência derivado deterministicamente de bucket+key, então reprocessar sobrescreve em vez de duplicar (idempotência por nome, sem precisar de tabela de histórico nova)
- [ ] Testes (LocalStack real): keyframe real processado com sucesso, evidência complementar gerada; falha simulada do analyzer não derruba o handler; reenvio do mesmo objeto não duplica evidência
- [ ] Gate: `pytest -q` · Test count: ≥ 3

**Tests**: integration · **Gate**: full
**Commit**: `feat(f1): handler Lambda fino do complemento cloud`

---

### T12: `infra.py` — deploy real da Lambda + gatilho S3

**What**: Empacota e implanta o Lambda de verdade no LocalStack, configura o gatilho S3→Lambda.
**Where**: `backend/pipelines/video/infra.py`, `backend/tests/integration/test_video_infra.py`, `Makefile` (novo alvo)
**Depends on**: T11
**Reuses**: `aws.clients.get_client`, padrão idêntico a `pipelines/prescription/infra.py` (já testado e funcionando de ponta a ponta em F4)
**Requirement**: VIDEO-07 (infra), VIDEO-10 (suporte)

**Tools**: MCP: NONE · Skill: NONE

**Done when**:
- [ ] `package_lambda()`/`ensure_lambda()`/`ensure_s3_trigger()` seguem exatamente o padrão já validado em `pipelines/prescription/infra.py` (mesmo fallback de `LOCALSTACK_HOSTNAME` da fundação, sem precisar de novo achado a verificar)
- [ ] Alvo `make infra-video-local`/`infra-video-cloud` roda `infra.py` de ponta a ponta
- [ ] Nenhum `boto3.client` direto (guarda da fundação cobre `pipelines/video/` automaticamente)
- [ ] Testes: upload real de um keyframe no bucket S3 dispara o Lambda de verdade; segunda execução de `infra.py` é idempotente (não recria a função)
- [ ] Gate: `pytest -q` · Test count: ≥ 2

**Tests**: integration · **Gate**: full
**Commit**: `feat(f1): provisionamento e deploy real do Lambda do complemento cloud`

---

### T13: `report.py` — relatório consolidado (P3)

**What**: Gera um relatório Markdown por sequência/vídeo, consolidando os eventos das duas raias.
**Where**: `backend/pipelines/video/report.py`, `backend/tests/video/test_report.py`
**Depends on**: T5, T9
**Reuses**: —
**Requirement**: VIDEO-11, VIDEO-12, VIDEO-15

**Tools**: MCP: NONE · Skill: NONE

**Done when**:
- [ ] `generate_report(pose_result, object_result=None) -> str` lista cada evento com timestamp/frame, tipo e link para a evidência
- [ ] Nenhum evento detectado → relatório indica explicitamente "nenhum evento detectado", nunca omitido
- [ ] Duas sequências/vídeos processados no mesmo lote geram relatórios com IDs/evidências isolados, sem mistura entre si
- [ ] Testes: sequência com eventos conhecidos; sequência sem eventos; duas sequências processadas em sequência não misturam dados
- [ ] Gate: `pytest -q -m "not integration"` · Test count: ≥ 3

**Tests**: unit · **Gate**: quick
**Commit**: `feat(f1): relatorio automatico consolidado por sequencia/video`

---

## Phase Execution Map

```
Batch 1: T1 → T2 → T3 → T4 → T5 → T6 → T7
Batch 2: T8 → T9 → T10 → T11 → T12 → T13
```

13 tarefas, 2 batches (excede o budget de ~8 de um único batch) → **oferecer sub-agentes antes do Execute**. Verifier independente ao final, após o último commit de T13.

---

## Task Granularity Check

| Task | Scope | Status |
| --- | --- | --- |
| T1 | 1 módulo (loader) + models compartilhados | ✅ Granular |
| T2 | 1 módulo (extração de pose) | ✅ Granular |
| T3 | 1 módulo (features de movimento) | ✅ Granular |
| T4 | 1 módulo (classificação + evidência, mesmo tema: veredito da sequência) | ✅ Granular |
| T5 | 1 módulo (avaliação) | ✅ Granular |
| T6 | 1 módulo (loader COCO) | ✅ Granular |
| T7 | 1 módulo (fine-tuning) | ✅ Granular |
| T8 | 1 módulo (detector + evidência, mesmo tema) | ✅ Granular |
| T9 | 1 módulo (avaliação) | ✅ Granular |
| T10 | 1 classe + 1 função de registro | ✅ Granular |
| T11 | 1 módulo (handler fino) | ✅ Granular |
| T12 | 3 funções coesas (mesmo tema: provisionar a Lambda) | ✅ Granular |
| T13 | 1 módulo (relatório) | ✅ Granular |

---

## Diagram-Definition Cross-Check

| Task | Depends On (corpo) | Diagrama | Status |
| --- | --- | --- | --- |
| T1 | None | Batch 1 início | ✅ |
| T2 | T1 | após T1 | ✅ |
| T3 | T2 | após T2 | ✅ |
| T4 | T3 | após T3 | ✅ |
| T5 | T1, T4 | após T4 (T1 já concluída antes) | ✅ |
| T6 | None | Batch 1, paralelo em tema (raia objeto começa) | ✅ |
| T7 | T6 | após T6 | ✅ |
| T8 | T6, T7 | Batch 2 início (ambas já concluídas no Batch 1) | ✅ |
| T9 | T6, T8 | após T8 | ✅ |
| T10 | T8 | após T9 (T8 já concluída antes) | ✅ |
| T11 | T10 | após T10 | ✅ |
| T12 | T11 | após T11 | ✅ |
| T13 | T5, T9 | fim do Batch 2 (ambas já concluídas antes) | ✅ |

Nenhuma dependência aponta para uma tarefa posterior nem cruza batch incorretamente (T8 depende de T7, que é a última tarefa do Batch 1 — a dependência cruza o limite do batch mas na direção correta, batches rodam sequencialmente).

---

## Test Co-location Validation

| Task | Camada | Matriz exige | Tarefa diz | Status |
| --- | --- | --- | --- | --- |
| T1 | Domínio puro | unit | unit | ✅ |
| T2 | Domínio puro (MediaPipe local) | unit | unit | ✅ |
| T3 | Domínio puro | unit | unit | ✅ |
| T4 | Domínio puro | unit | unit | ✅ |
| T5 | Domínio puro | unit | unit | ✅ |
| T6 | Domínio puro | unit | unit | ✅ |
| T7 | Domínio puro (YOLOv8 local) | unit | unit | ✅ |
| T8 | Domínio puro | unit | unit | ✅ |
| T9 | Domínio puro | unit | unit | ✅ |
| T10 | Domínio puro (sem cliente AWS) | unit | unit | ✅ |
| T11 | `handler.py` (S3/Lambda reais) | integration | integration | ✅ |
| T12 | `infra.py` (deploy real) | integration | integration | ✅ |
| T13 | Domínio puro | unit | unit | ✅ |

Nenhuma violação.

---

## Requirement Traceability

| Requirement | Tarefas | Status |
| --- | --- | --- |
| VIDEO-01 | T1, T2 | Mapeado |
| VIDEO-02 | T3 | Mapeado |
| VIDEO-03 | T4 | Mapeado |
| VIDEO-04 | T5 | Mapeado |
| VIDEO-05 | T4 | Mapeado |
| VIDEO-06 | T6 | Mapeado |
| VIDEO-07 | T8, T10, T12 | Mapeado |
| VIDEO-08 | T9 | Mapeado |
| VIDEO-09 | T8 | Mapeado |
| VIDEO-10 | T11, T12 | Mapeado |
| VIDEO-11 | T13 | Mapeado |
| VIDEO-12 | T13 | Mapeado |
| VIDEO-13 | T2 | Mapeado |
| VIDEO-14 | T4 | Mapeado |
| VIDEO-15 | T13 | Mapeado |
| VIDEO-16 | T11 | Mapeado |

**Coverage:** 16 de 16 requisitos mapeados, nenhum diferido.
