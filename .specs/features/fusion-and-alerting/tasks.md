# F5 (fusion-and-alerting) Tasks

## Execution Protocol (MANDATORY -- do not skip)

Implement these tasks with the `tlc-spec-driven` skill: **activate it by name and follow its Execute flow and Critical Rules.** Do not search for skill files by filesystem path. The skill is the source of truth for the full flow (per-task cycle, sub-agent delegation, adequacy review, Verifier, discrimination sensor).

**If the skill cannot be activated, STOP and tell the user — do not proceed without it.**

---

**Design**: `.specs/features/fusion-and-alerting/design.md`
**Status**: Done — T1-T18 completas, Verifier PASS após fix dos 2 gaps (ver `validation.md`)

---

## Test Coverage Matrix

> Generated from codebase sampling (`backend/tests/vitals/test_cli_events.py`, `backend/tests/integration/test_audio_pipeline.py`, `test_video_handler.py`, `test_prescription_history.py`) and spec ACs. No `AGENTS.md`/`CLAUDE.md`/`CONTRIBUTING.md` testing guideline found in the repo — strong defaults applied where no direct precedent existed (API routes, Streamlit frontend).

| Code Layer | Required Test Type | Coverage Expectation | Location Pattern | Run Command |
| --- | --- | --- | --- | --- |
| CLI driver (`pipelines/video/cli.py`) | integration | Roda `run()` ponta a ponta contra dado URFD real, produz evidência real; pula com skip claro se dataset ausente (mesmo padrão de `test_audio_pipeline.py`) | `backend/tests/integration/test_video_pipeline.py` | `pytest -q -m integration` |
| Domínio de fusão (`pipelines/fusion/{models,config,loader,risk_engine,hysteresis,transitions,alert}.py`) | unit | 1:1 com cada AC de FUSION-01/02/03/04/05/06/07/08/13/14; todo edge case listado (referência não resolvida, oscilação na banda de histerese, modalidade ausente do cenário inteiro) tem teste | `backend/tests/fusion/test_*.py` | `make test-unit` |
| AWS integration (`handler.py`, `infra.py`, `aws/provision.py::ensure_subscription`) | integration | Contra LocalStack real: publish+dedupe, falha de envio tratada sem gravar dedupe, provisionamento idempotente (2 execuções sem erro) — mesmo padrão de `test_video_handler.py`/`test_prescription_history.py` | `backend/tests/integration/test_fusion_handler.py`, `test_fusion_infra.py`, `backend/tests/aws/test_provision_subscription.py` | `make test` (requer `make localstack-up`) |
| Rotas da API (`app/routes.py`) | integration (FastAPI `TestClient`) | Todas as 4 rotas: happy path + edge (404 sem paciente-demo / evidência inexistente) — sem precedente de API neste repo, default forte aplicado | `backend/tests/app/test_routes.py` | `make test-unit` |
| Dashboard (`frontend/app.py`, Streamlit) | none (manual) | Sem harness de teste automatizado de Streamlit neste repo; verificado rodando `streamlit run frontend/app.py` no navegador contra a API real antes de fechar a tarefa | — | manual: `streamlit run frontend/app.py` |
| Config curada (`pipelines/fusion/configs/demo.yaml`) | integration (indireta) | Não é testável como "código" isoladamente — validada rodando `loader.load_events` contra ela e confirmando zero falhas de resolução | `backend/tests/fusion/test_loader.py` (mesmo arquivo de T4) | `make test-unit` |
| Dataclasses/schemas (`fusion/models.py`, `app/schemas.py`) | none | Camada de entidade/config — build gate apenas | — | build gate only |

## Gate Check Commands

| Gate Level | When to Use | Command |
| --- | --- | --- |
| Quick | Após tarefas só com testes unitários | `make test-unit` |
| Full | Após tarefas que tocam LocalStack (SNS/DynamoDB) ou integração ponta a ponta | `make localstack-up && make test` |
| Build | Camadas de entidade/config sem teste próprio, ou fechamento de fase | `make test && make lint` |
| Manual | Tarefas de `frontend/` (sem harness automatizado) | `streamlit run frontend/app.py` + inspeção visual |

---

## Execution Plan

Phases are ordered and run sequentially — each phase completes before the next begins, and tasks within a phase execute in order.

### Phase 1: Pré-requisito operacional + Fundação

```
T1
T2 → T3
```

### Phase 2: Motor de fusão (P1 — FUSION-01 a 06, 13, 14)

```
T4
T5 → T6
T7 → T8
```

### Phase 3: Alerta (P2 — FUSION-07, 08, 09)

```
T9
T10 → T11 → T12
```

### Phase 4: API fina (FUSION-10, 11, 12 — backend)

```
T13
T14 → T15
```

### Phase 5: Dashboard Streamlit (FUSION-10, 11, 12 — frontend)

```
T16 → T17
```

### Phase 6: Config curada do paciente-demo + verificação ponta a ponta

```
T18
```

---

## Task Breakdown

### T1: Driver CLI da raia pose de F1 (pré-requisito operacional)

**What**: Novo arquivo que orquestra a raia pose já verificada de F1 (`pose_loader`→`pose.py`→`pose_features.py`→`pose_detector.py`) ponta a ponta, gravando evidência real via `common.evidence.save_evidence` e métricas via `pose_evaluate.py`. Sem isso não existe `evidence_id` real de F1 para a config do paciente-demo referenciar.
**Where**: `backend/pipelines/video/cli.py`
**Depends on**: None
**Reuses**: `pipelines/video/{pose_loader,pose,pose_features,pose_detector,pose_evaluate}.py` (100%, nenhum modificado); mesmo esqueleto de `pipelines/vitals/cli.py`/`pipelines/audio/cli.py` (`run(config_path, run_id=None) -> int`, `argparse`, `if __name__ == "__main__"`)
**Requirement**: pré-requisito operacional (não é `FUSION-NN`) — necessário para popular `output/video/<run_id>/` antes de T18

**Tools**:
- MCP: NONE
- Skill: NONE

**Done when**:
- [x] `run()` carrega sequências URFD reais via `pose_loader`
- [x] roda `pose.py`→`pose_features.py`→`pose_detector.py` e grava evidência real via `common.evidence.save_evidence` (já implementado em F1, só orquestrado aqui)
- [x] grava `metrics.json` via `pose_evaluate.py`
- [x] `argparse` + `__main__` seguem o mesmo contrato de `vitals/cli.py`/`audio/cli.py` (`config_path`, `--run-id` opcional)
- [x] roda de fato contra pelo menos 1 sequência URFD real e produz `output/video/<run_id>/` com evidência + `metrics.json`
- [x] nenhum arquivo pré-existente de `pipelines/video/` é modificado (F1 permanece "FECHADA")
- [x] Gate check passes: `pytest -q -m integration backend/tests/integration/test_video_pipeline.py`

**Tests**: integration
**Gate**: full

**Commit**: `feat(video): adiciona driver cli.py da raia pose (pré-requisito de F5)`

**Status**: ✅ Complete — commit `9dd7d1d`

---

### T2: Dataclasses de domínio (`fusion/models.py`)

**What**: `CuratedEventRef`, `FusionEvent`, `RiskPoint`, `Transition`, `AlertPayload` — exatamente como especificado no design.md, todas `@dataclass(frozen=True)`.
**Where**: `backend/pipelines/fusion/models.py`
**Depends on**: None
**Reuses**: nenhum (domínio novo)
**Requirement**: fundação (suporta FUSION-01 a 14)

**Tools**:
- MCP: NONE
- Skill: NONE

**Done when**:
- [x] 5 dataclasses `frozen=True` definidas com os campos exatos do design.md
- [x] type hints completos, sem lógica além de estrutura de dados
- [x] Gate check passes: `make lint`

**Tests**: none
**Gate**: build

**Commit**: `feat(fusion): adiciona dataclasses de domínio (models.py)`

**Status**: ✅ Complete — commit `8dbec31`

---

### T3: Config declarativa do paciente-demo (`fusion/config.py`)

**What**: `load_patient_demo_config(path) -> PatientDemoConfig` — parser/validador YAML (campo desconhecido = erro), aplicando todos os defaults documentados no design (`weights` iguais 0.25, `decay_half_life_s=600.0`, `threshold_amarelo=0.3`, `threshold_vermelho=0.7`, `hysteresis=0.05`, `window_size_s=60.0`, `alert_level="vermelho"`, `sns_topic="mm-alerts"`).
**Where**: `backend/pipelines/fusion/config.py`
**Depends on**: T2 (usa `CuratedEventRef`)
**Reuses**: padrão de validação de `pipelines/audio/config.py` (campo desconhecido = erro), não uma classe compartilhada
**Requirement**: fundação (config referenciada por FUSION-01)

**Tools**:
- MCP: NONE
- Skill: NONE

**Done when**:
- [x] parseia YAML e valida campo desconhecido = erro (mesmo padrão de `audio/config.py`)
- [x] aplica todos os defaults documentados quando ausentes do YAML
- [x] `events` (lista, ≥1 item) vira `list[CuratedEventRef]`
- [x] erro claro se `events` vazio ou `modality` fora de `{video,audio,vitals,prescription}`
- [x] Gate check passes: `make test-unit`
- [x] Test count: cobre cada default (1:1) + os 2 casos de erro acima

**Tests**: unit
**Gate**: quick

**Commit**: `feat(fusion): adiciona parser/validador de config do paciente-demo`

**Status**: ✅ Complete — commit `fbaa78e`

---

### T4: Loader de eventos reais (`fusion/loader.py`) — FUSION-01

**What**: `load_events(config, output_root) -> tuple[list[FusionEvent], list[str]]` — resolve cada `CuratedEventRef` lendo o sidecar JSON real via `common.evidence`.
**Where**: `backend/pipelines/fusion/loader.py`
**Depends on**: T2, T3
**Reuses**: `backend/common/evidence.py` (leitura de sidecar); mesmo padrão de tolerância a falha de `pipelines/vitals/loader.load_dataset`
**Requirement**: FUSION-01

**Tools**:
- MCP: NONE
- Skill: NONE

**Done when**:
- [x] resolve `evidence_id` real → `FusionEvent` (modalidade, `demo_timestamp_s`, severidade, resumo extraído do `metadata`, evidência real)
- [x] referência que não resolve (arquivo ausente) cai na segunda lista de falhas, sem derrubar a carga inteira
- [x] testado com pelo menos 1 evidência real já em disco (`output/prescription/2026072{1,2}/` de F4 já existe)
- [x] Gate check passes: `make test-unit`

**Tests**: unit
**Gate**: quick

**Commit**: `feat(fusion): adiciona loader.py (resolve eventos curados em evidência real)`

**Status**: ✅ Complete — commit `a0ec474`

---

### T5: Reordenação cronológica e decaimento (`risk_engine.py` parte 1) — FUSION-02

**What**: `sort_events(events) -> list[FusionEvent]` (ordena por `demo_timestamp_s`); `decay(elapsed_s, half_life_s) -> float` (`2 ** (-elapsed_s / half_life_s)`).
**Where**: `backend/pipelines/fusion/risk_engine.py`
**Depends on**: T2
**Reuses**: nenhum
**Requirement**: FUSION-02 (`sort_events`); fundação de FUSION-03 (`decay`)

**Tools**:
- MCP: NONE
- Skill: NONE

**Done when**:
- [x] `sort_events` reordena lista entregue fora de ordem cronológica corretamente (AC FUSION-02 direto)
- [x] `decay(0, h) == 1.0`; `decay(h, h) == 0.5`; monotonicamente decrescente
- [x] teste com eventos de múltiplas modalidades fora de ordem
- [x] Gate check passes: `make test-unit`

**Tests**: unit
**Gate**: quick

**Commit**: `feat(fusion): adiciona reordenação cronológica e decaimento temporal (risk_engine)`

**Status**: ✅ Complete — commit `df174d9`

---

### T6: Risk score ponderado (`risk_engine.py` parte 2) — FUSION-03, FUSION-04, FUSION-14

**What**: `score_at(t, events, weights, half_life_s) -> RiskPoint`; `compute_timeline(events, cfg) -> list[RiskPoint]`.
**Where**: `backend/pipelines/fusion/risk_engine.py` (mesmo arquivo de T5)
**Depends on**: T5
**Reuses**: `sort_events`/`decay` de T5
**Requirement**: FUSION-03, FUSION-04, FUSION-14

**Tools**:
- MCP: NONE
- Skill: NONE

**Done when**:
- [x] `score_at` soma `peso * severidade * decay` do evento mais recente de cada modalidade com `demo_timestamp_s <= t`
- [x] modalidade sem evento até `t` entra em `missing_modalities`, nunca contribui como 0 silencioso (AC FUSION-04)
- [x] `compute_timeline` varre de `t=0` até o último `demo_timestamp_s` + cauda, em passos de `window_size_s`
- [x] teste com paciente-demo sem 1 das 4 modalidades confirma `missing_modalities` correto desde `t=0` (edge case FUSION-14)
- [x] Gate check passes: `make test-unit`

**Tests**: unit
**Gate**: quick

**Commit**: `feat(fusion): adiciona cálculo de risk score ponderado com decaimento (risk_engine)`

**Status**: ✅ Complete — commit `bb63c5d`

---

### T7: Classificador com histerese (`hysteresis.py`) — FUSION-05, FUSION-13

**What**: `class HysteresisClassifier` com `.update(score: float) -> str` — mantém nível atual internamente, só muda ao cruzar `limiar ± histerese` a partir do nível atual.
**Where**: `backend/pipelines/fusion/hysteresis.py`
**Depends on**: T2
**Reuses**: nenhum
**Requirement**: FUSION-05, FUSION-13

**Tools**:
- MCP: NONE
- Skill: NONE

**Done when**:
- [x] classifica verde/amarelo/vermelho pelos limiares configurados
- [x] histerese evita oscilação: score variando dentro da banda `±hysteresis` ao redor de um limiar não muda de nível (edge case da spec)
- [x] mantém o último nível quando chamado sem sinal novo suficiente pra cruzar a banda (FUSION-13)
- [x] teste de sequência conhecida batendo com cálculo manual (Independent Test de P1 da spec)
- [x] Gate check passes: `make test-unit`

**Tests**: unit
**Gate**: quick

**Commit**: `feat(fusion): adiciona classificador de nível com histerese (hysteresis.py)`

**Status**: ✅ Complete — commit `78d12bd`

---

### T8: Log de auditoria de transição (`transitions.py`) — FUSION-06

**What**: `record_transition(previous, new, point) -> Transition`; `save_transitions(transitions, path) -> None` (JSON).
**Where**: `backend/pipelines/fusion/transitions.py`
**Depends on**: T2, T7
**Reuses**: princípio de persistência de `common/metrics.py` (não o código)
**Requirement**: FUSION-06

**Tools**:
- MCP: NONE
- Skill: NONE

**Done when**:
- [x] `record_transition` grava nível anterior, novo nível, sinais contribuintes (`RiskPoint.contributions`), timestamp
- [x] `save_transitions` grava JSON legível
- [x] teste cobrindo sequência de `RiskPoint` com mudança de nível gera log de transição correto
- [x] Gate check passes: `make test-unit`

**Tests**: unit
**Gate**: quick

**Commit**: `feat(fusion): adiciona log de auditoria de transição de nível (transitions.py)`

**Status**: ✅ Complete — commit `b44e52b`

---

### T9: `ensure_subscription` idempotente (`aws/provision.py`, aditivo)

**What**: Nova função `ensure_subscription(topic_arn, email) -> None`, idempotente (não reenvia confirmação se já inscrito).
**Where**: `backend/aws/provision.py` (modifica — só adiciona função nova, nenhuma existente alterada)
**Depends on**: None
**Reuses**: mesmo padrão idempotente de `ensure_bucket`/`ensure_topic`/`ensure_table` (mesmo arquivo)
**Requirement**: fundação de FUSION-07 (infra do alerta)

**Tools**:
- MCP: NONE
- Skill: NONE

**Done when**:
- [x] `ensure_subscription` inscreve e-mail no tópico SNS via `boto3`
- [x] idempotente — chamar duas vezes com o mesmo e-mail não gera erro nem reenvio duplicado de confirmação
- [x] nenhuma função existente de `provision.py` é modificada
- [x] Gate check passes: `make localstack-up && make test && make lint` (gate completo do repo, não só de F5 — reabre arquivo de feature já fechada, aws-foundation)

**Tests**: integration
**Gate**: full

**Commit**: `feat(aws): adiciona ensure_subscription idempotente (suporte a alerta de F5)`

**Status**: ✅ Complete — commit `57e122c`

---

### T10: Payload de alerta e dedupe (`fusion/alert.py`) — FUSION-07, FUSION-08

**What**: `build_payload(point, patient_demo_id) -> AlertPayload`; `dedup_key(point) -> str` (determinístico a partir dos `evidence_id` dos eventos contribuintes).
**Where**: `backend/pipelines/fusion/alert.py`
**Depends on**: T2, T6
**Reuses**: nenhum
**Requirement**: FUSION-07, FUSION-08

**Tools**:
- MCP: NONE
- Skill: NONE

**Done when**:
- [x] `build_payload` monta ID do paciente-demo, nível, lista `(modalidade, resumo, link_s3)` a partir de `RiskPoint.contributing_events`
- [x] `dedup_key` é determinístico a partir dos `evidence_id` (não do timestamp da chamada) — mesmo conjunto de eventos sempre gera a mesma chave
- [x] teste confirma que reenviar o mesmo `RiskPoint` gera o mesmo `dedup_key`
- [x] Gate check passes: `make test-unit`

**Tests**: unit
**Gate**: quick

**Commit**: `feat(fusion): adiciona montagem de payload de alerta e chave de dedupe (alert.py)`

**Status**: ✅ Complete — commit `d2af7c0`. SPEC_DEVIATION: link de evidência aponta para `/evidence/{id}` (API de F5) em vez de uma URL `s3://` literal — evidência do paciente-demo nunca é upada ao S3 (loader.py lê sidecars locais, AD-045); ver docstring de `alert.py::build_payload`.

---

### T11: Handler Lambda de alerta (`fusion/handler.py`) — FUSION-07, FUSION-08, FUSION-09

**What**: `lambda_handler(event, context)` — publica no SNS via `alert.build_payload`, grava dedupe no DynamoDB (prefixo `ALERT#`) só em caso de sucesso, trata falha sem propagar.
**Where**: `backend/pipelines/fusion/handler.py`
**Depends on**: T9, T10
**Reuses**: esqueleto fino de `pipelines/video/handler.py`; padrão de dedupe condicional (`ConditionExpression="attribute_not_exists(...)"`) de `pipelines/prescription/history.py`, mesma tabela genérica com prefixo `ALERT#`
**Requirement**: FUSION-07, FUSION-08, FUSION-09

**Tools**:
- MCP: NONE
- Skill: NONE

**Done when**:
- [x] publica no tópico SNS com o payload de `alert.build_payload`
- [x] grava `ALERT#<dedup_key>` no DynamoDB só em caso de sucesso
- [x] segunda tentativa com o mesmo `dedup_key` é rejeitada pelo `ConditionExpression`, sem duplicar e-mail (AC FUSION-08 ponta a ponta)
- [x] `except Exception` loga no CloudWatch e não propaga, e NÃO grava dedupe em caso de falha — permite nova tentativa (AC FUSION-09)
- [x] Gate check passes: `make localstack-up && make test`

**Tests**: integration
**Gate**: full

**Commit**: `feat(fusion): adiciona handler Lambda de alerta com dedupe e tratamento de falha`

**Status**: ✅ Complete — commit `695be6f`. Decisão de design: reserva o `dedup_key` no DynamoDB ANTES de publicar (não depois) e desfaz a reserva (`delete_item`) se o publish falhar — satisfaz "grava só em caso de sucesso" (estado final) E "segunda tentativa é rejeitada pelo ConditionExpression" (mecanismo literal) simultaneamente; publish-then-write sem reserva não bloquearia duas tentativas em sequência rápida antes da 1ª terminar de gravar.

---

### T12: Provisionamento idempotente (`fusion/infra.py`)

**What**: `provision(...)` idempotente — garante tópico/tabela (reuso da fundação) + `ensure_subscription` para os e-mails do grupo; zip do handler.
**Where**: `backend/pipelines/fusion/infra.py`
**Depends on**: T9, T11
**Reuses**: mesmo padrão idempotente de `pipelines/video/infra.py` e `pipelines/prescription/infra.py` (zip do handler + deps mínimas)
**Requirement**: suporte operacional de FUSION-07

**Tools**:
- MCP: NONE
- Skill: NONE

**Done when**:
- [x] provisiona (idempotente) o que o handler precisa, reusando `ensure_bucket`/`ensure_topic`/`ensure_table` já existentes
- [x] chama `ensure_subscription` para os e-mails configurados
- [x] roda 2x seguidas sem erro (idempotência)
- [x] documenta no docstring/README que a confirmação de e-mail é manual (clique), não automatizável
- [x] Gate check passes: `make localstack-up && make test`

**Tests**: integration
**Gate**: full

**Commit**: `feat(fusion): adiciona provisionamento idempotente de infra do alerta (infra.py)`

**Status**: ✅ Complete — commit `729d69b`. Decisão de escopo: `ensure_bucket` NÃO é chamado (documentado no docstring) — o handler de alerta não lê/grava nada no S3 (não é disparado por evento S3, ao contrário de video/prescription), então provisionar um bucket aqui seria um recurso morto; `ensure_topic`/`ensure_table`/`ensure_subscription` são os 3 efetivamente usados.

---

### T13: Esqueleto FastAPI e schemas (`app/main.py`, `app/schemas.py`)

**What**: Schemas Pydantic de resposta (ponto de timeline, análise, alerta, evidência) + app FastAPI mínimo instanciado (sem rotas ainda).
**Where**: `backend/app/schemas.py`, `backend/app/main.py`
**Depends on**: T2
**Reuses**: nenhum (novo)
**Requirement**: fundação de FUSION-10/11/12 (AD-044)

**Tools**:
- MCP: NONE
- Skill: NONE

**Done when**:
- [x] schemas Pydantic espelham os campos de `RiskPoint`/`Transition`/`AlertPayload` relevantes para a API
- [x] `app = FastAPI()` instanciado em `main.py`, sem middleware de auth (fora de escopo, spec)
- [x] Gate check passes: `make lint`

**Tests**: none
**Gate**: build

**Commit**: `feat(app): adiciona esqueleto FastAPI e schemas de resposta`

**Status**: ✅ Complete — commit `7515dd0`. `routes.py` (T14) importará `app` de `main.py` e decorará as rotas diretamente nele (sem `APIRouter`) — padrão simples o bastante para as 4 rotas da AD-029, sem cerimônia extra.

---

### T14: Rotas de timeline e análise (`app/routes.py` parte 1) — FUSION-10 (parte)

**What**: `GET /patients/{id}/timeline` roda `loader`+`risk_engine`+`hysteresis` para o paciente-demo `{id}` (config de `pipelines/fusion/configs/<id>.yaml`); `GET /analyze` devolve o ponto mais recente.
**Where**: `backend/app/routes.py`
**Depends on**: T4, T6, T7, T13
**Reuses**: `pipelines/fusion/*` inteiro
**Requirement**: FUSION-10 (parte), fundação de FUSION-12

**Tools**:
- MCP: NONE
- Skill: NONE

**Done when**:
- [x] `GET /patients/{id}/timeline` devolve a lista de `RiskPoint` serializada, rodando o motor de ponta a ponta contra a config real
- [x] `GET /analyze` devolve nível/score/modalidades ausentes do ponto mais recente
- [x] paciente-demo inexistente devolve 404 claro (nunca erro genérico)
- [x] happy path + edge (id inexistente) testados via `TestClient`
- [x] Gate check passes: `make test-unit`

**Tests**: integration (FastAPI `TestClient`)
**Gate**: quick

**Commit**: `feat(app): adiciona rotas de timeline e análise do paciente-demo`

**Status**: ✅ Complete — commit `631a29c`. `/analyze` recebe `patient_demo_id` como query param (design.md lista a rota sem `{id}` no path; único jeito funcional de apontar qual paciente-demo sem contradizer o path literal do design). `_classified_timeline` aplica `HysteresisClassifier` sobre a timeline bruta do `risk_engine` (que sai com `level=""`) — é o ponto de integração citado no brief do lote.

---

### T15: Rotas de alertas e evidência (`app/routes.py` parte 2) — FUSION-09 (parte), FUSION-12

**What**: `GET /alerts` lista transições que cruzaram o nível de disparo com status de confirmação (lidas de `transitions.py`); `GET /evidence/{id}` serve artefato+metadados via `common/evidence.py`.
**Where**: `backend/app/routes.py` (mesmo arquivo de T14)
**Depends on**: T8, T14
**Reuses**: `common/evidence.py` (proxy fino)
**Requirement**: FUSION-09 (parte), FUSION-12

**Tools**:
- MCP: NONE
- Skill: NONE

**Done when**:
- [x] `GET /alerts` lista transições que cruzaram `alert_level`, com status enviado/não confirmado (AC FUSION-09 exposto via API)
- [x] `GET /evidence/{id}` serve o artefato real + metadados pelo `evidence_id` curado
- [x] `evidence_id` inexistente devolve 404 claro
- [x] happy path + edge (evidence_id inexistente) testados via `TestClient`
- [x] Gate check passes: `make test-unit`

**Tests**: integration (FastAPI `TestClient`)
**Gate**: quick

**Commit**: `feat(app): adiciona rotas de alertas e drill-down de evidência`

**Status**: ✅ Complete — commit `7019f91`. Duas decisões de design não totalmente literais no design.md (registradas aqui, não SPEC_DEVIATION de AC — nenhum AC de spec.md é violado): (1) `GET /evidence/{id}` serve os BYTES reais do artefato via `FileResponse` (content-type inferido da extensão, consumível direto por `st.image(url)`/`st.text` no dashboard), com os metadados do sidecar embutidos como headers HTTP (`X-Evidence-Feature`/`X-Evidence-Run-Id`/`X-Evidence-Source-Record-Id`) em vez de um corpo JSON com `EvidenceSchema` (T13) — a frase do design "renderiza conforme o content-type/extensão devolvido" só faz sentido se a própria rota devolve o artefato bruto; `EvidenceSchema` fica sem uso (não é erro, só não se aplicou ao formato escolhido). (2) `GET /alerts` deriva as `Transition` comparando níveis consecutivos na timeline já classificada (não persiste/lê um arquivo de log via `transitions.py::save_transitions` — a rota roda o motor a cada requisição, então gerar as transições em memória é equivalente e mais simples que persistir+reler um arquivo).

---

### T16: Dashboard — timeline unificada e replay (`frontend/app.py` parte 1) — FUSION-10, FUSION-11

**What**: Carrega `GET /patients/{id}/timeline` uma vez (`st.session_state`), exibe timeline unificada (score + nível ao longo do tempo), replay controlado (velocidade configurável, nunca espera duração real, nunca re-chama a API a cada passo).
**Where**: `frontend/app.py`
**Depends on**: T14
**Reuses**: nenhum código de `backend/` importado direto — só `requests` (HTTP)
**Requirement**: FUSION-10, FUSION-11

**Tools**:
- MCP: NONE
- Skill: NONE

**Done when**:
- [x] timeline unificada renderizada (score, nível, eventos das 4 modalidades) a partir de 1 chamada HTTP
- [x] replay percorre os pontos já carregados sem nova chamada HTTP por passo
- [x] verificado manualmente rodando `streamlit run frontend/app.py` no navegador contra a API real (T14/T15 já servindo)

**Tests**: none (manual — ver Test Coverage Matrix)
**Gate**: manual

**Commit**: `feat(frontend): adiciona dashboard com timeline unificada e replay`

**Status**: ✅ Complete — commit `22a5808`. Ressalva: o sub-agente que implementou não tinha ferramenta de navegador disponível — a verificação real foi `streamlit run` + checagem de processo (sem exceção) e `streamlit.testing.v1.AppTest` headless (happy path, replay, sem exceções). **Inspeção visual real num navegador (layout, legibilidade) ainda não foi feita por um humano** — pendente antes de gravar o vídeo de demonstração.

---

### T17: Dashboard — drill-down de evidência e estado vazio (`frontend/app.py` parte 2) — FUSION-12

**What**: Seleção de evento → `GET /evidence/{id}` → renderiza artefato conforme tipo (imagem/texto); sem paciente-demo configurado → mensagem clara, nunca tela em branco.
**Where**: `frontend/app.py` (mesmo arquivo de T16)
**Depends on**: T15, T16
**Reuses**: nenhum
**Requirement**: FUSION-12; edge case "dashboard sem paciente-demo configurado"

**Tools**:
- MCP: NONE
- Skill: NONE

**Done when**:
- [x] evento selecionado renderiza a evidência correta pelo tipo (frame anotado/transcript/gráfico/prescrição anotada)
- [x] dashboard sem paciente-demo configurado mostra mensagem clara de configuração pendente, não tela vazia
- [x] verificado manualmente no navegador (mesma ressalva de T16)

**Tests**: none (manual)
**Gate**: manual

**Commit**: `feat(frontend): adiciona drill-down de evidência e estado de configuração pendente`

**Status**: ✅ Complete — commit `86c7f2e`. Mesma ressalva de verificação visual de T16 (sem navegador disponível ao sub-agente; verificado via `AppTest` headless cobrindo os 4 tipos reais de evidência — imagem/imagem/PDF/imagem — e o estado vazio, 0 exceções).

---

### T18: Config curada do paciente-demo + verificação ponta a ponta

**What**: Roda de fato `pipelines/video/cli.py` (T1), `pipelines/audio/cli.py` (F2, já existe) e `make demo` (F3, já existe) para produzir evidência real em `output/video/`, `output/audio/`, `output/vitals/` (F4 já tem evidência real em `output/prescription/2026072{1,2}/`). Depois cura manualmente o YAML do paciente-demo referenciando `evidence_id`s reais dessas execuções, com `demo_timestamp_s` formando uma narrativa coerente (ex.: queda detectada → deterioração de vitais → prescrição → observação de áudio).
**Where**: `backend/pipelines/fusion/configs/demo.yaml`
**Depends on**: T1, T3, T4, T14
**Reuses**: evidência real já em disco (F4); F1/F2/F3 rodados nesta tarefa
**Requirement**: AD-045a (config curada); pré-requisito para demonstrar P1/P2/P3 ponta a ponta

**Tools**:
- MCP: NONE
- Skill: NONE

**Done when**:
- [x] `pipelines/video/cli.py` rodado com sucesso contra ≥1 sequência URFD real, gerando evidência real
- [x] `pipelines/audio/cli.py` rodado contra o subconjunto ICBHI real (223 evidências)
- [x] `make demo` rodado — **decisão de curadoria confirmada com o usuário**: caso CTG (CTU-UHB, FHR via `pipelines/vitals/configs/demo.yaml`), não o caso UTI (BIDMC, HR/SpO2). BIDMC foi descartado para esta tarefa porque `pipelines/vitals/{loader,features,detectors}.py` são inteiramente específicos de CTU-UHB/CTG (rótulo por pH fetal) — não processam HR/SpO2/PULSE do BIDMC; adicionar esse suporte seria um segundo caso de F3 inteiro, fora do escopo de T18. O desencaixe narrativo (monitoramento fetal ao lado de uma queda de paciente adulto) é aceito e deve ser explicado no relatório/vídeo, consistente com AD-024 (paciente-demo é composição didática, não correlação clínica real)
- [x] `demo.yaml` referencia 1+ `evidence_id` real de cada uma das 4 modalidades, com `demo_timestamp_s` formando narrativa coerente e documentada (queda → deterioração FHR → prescrição → sibilo/wheeze)
- [x] `loader.load_events(demo.yaml)` resolve 100% das referências sem nenhuma na lista de falhas (prova de que a curadoria aponta para evidência real, não fixture)
- [x] `GET /patients/demo/timeline` (T14) devolve a timeline completa das 4 modalidades
- [x] Gate check passes: `make test-unit`

**Tests**: integration
**Gate**: full

**Commit**: `feat(fusion): adiciona config curada do paciente-demo com evidência real das 4 modalidades`

**Status**: ✅ Complete — commit `cf613d0`. **Última tarefa da feature (T1-T18 completas)** — Verifier standalone rodado em seguida (o sub-agente não tinha ferramenta de spawn de sub-agente; seguiu o "Standalone fallback" de `sub-agents.md`, deixando isso explícito em vez de apresentar como equivalente a um Verifier realmente independente): **FAIL**, `validation.md` (commit `bd273ab`) — 16/16 critérios cobertos, mas sensor de mutação achou 2 sobreviventes (gaps de teste em código já correto): `hysteresis.py` sem teste da fronteira exata verde→vermelho, `app/routes.py::_is_confirmed` sem teste de integração real contra DynamoDB. **Ambos corrigidos e re-verificados** (commit `6466e46`): `make test` 489 passando, 0 falhas.

---

## Phase Execution Map

```
Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5 → Phase 6

Phase 1:  T1
          T2 ──→ T3
Phase 2:  T4
          T5 ──→ T6
          T7 ──→ T8
Phase 3:  T9
          T10 ──→ T11 ──→ T12
Phase 4:  T13
          T14 ──→ T15
Phase 5:  T16 ──→ T17
Phase 6:  T18
```

Execution is strictly sequential — there is no intra-phase parallelism. A single agent (or batch worker) works one task at a time, in order. Cross-phase dependencies (e.g., T4 depends on T2/T3 from Phase 1) are satisfied automatically by phase ordering — phases never start before the previous one finishes.

**Batch packing** (~7 tasks/worker, whole phases, 18 tasks total):

- **Batch 1**: Phase 1 (3) + Phase 2 (5) = 8 tasks
- **Batch 2**: Phase 3 (4) + Phase 4 (3) = 7 tasks
- **Batch 3**: Phase 5 (2) + Phase 6 (1) = 3 tasks

---

## Task Granularity Check

| Task | Scope | Status |
| --- | --- | --- |
| T1: Driver CLI da raia pose | 1 arquivo novo, orquestração | ✅ Granular |
| T2: Dataclasses de domínio | 1 arquivo, 5 tipos coesos (mesmo módulo `models.py` no design) | ✅ Granular |
| T3: Config do paciente-demo | 1 função pública + validação | ✅ Granular |
| T4: Loader de eventos | 1 função pública | ✅ Granular |
| T5: Reordenação + decaimento | 2 funções coesas no mesmo arquivo | ✅ Granular |
| T6: Risk score ponderado | 2 funções coesas, mesmo arquivo de T5 | ✅ Granular |
| T7: Classificador com histerese | 1 classe | ✅ Granular |
| T8: Log de transição | 2 funções coesas | ✅ Granular |
| T9: `ensure_subscription` | 1 função nova | ✅ Granular |
| T10: Payload + dedupe key | 2 funções coesas | ✅ Granular |
| T11: Handler Lambda | 1 função (`lambda_handler`) | ✅ Granular |
| T12: Provisionamento | 1 função (`provision`) | ✅ Granular |
| T13: Esqueleto FastAPI + schemas | 2 arquivos pequenos, sem rotas ainda | ✅ Granular |
| T14: Rotas timeline/analyze | 2 rotas coesas (mesmo recurso: estado atual do motor) | ✅ Granular |
| T15: Rotas alerts/evidence | 2 rotas coesas (mesmo recurso: auditoria/drill-down) | ✅ Granular |
| T16: Dashboard timeline+replay | 1 tela, 1 preocupação (visualização temporal) | ✅ Granular |
| T17: Dashboard drill-down+vazio | 1 tela, 1 preocupação (detalhe de evento) | ✅ Granular |
| T18: Config curada + verificação | 1 artefato (YAML) + verificação de resolução | ✅ Granular |

---

## Diagram-Definition Cross-Check

| Task | Depends On (task body) | Diagram Shows | Status |
| --- | --- | --- | --- |
| T1 | None | (nenhuma seta, fase 1) | ✅ Match |
| T2 | None | (nenhuma seta, fase 1) | ✅ Match |
| T3 | T2 | T2 → T3 | ✅ Match |
| T4 | T2, T3 (fase 1, cross-phase) | (sem seta — satisfeito por ordem de fase) | ✅ Match |
| T5 | T2 (fase 1, cross-phase) | (sem seta — satisfeito por ordem de fase) | ✅ Match |
| T6 | T5 | T5 → T6 | ✅ Match |
| T7 | T2 (fase 1, cross-phase) | (sem seta — satisfeito por ordem de fase) | ✅ Match |
| T8 | T2 (fase 1, cross-phase), T7 (mesma fase) | T7 → T8 | ✅ Match |
| T9 | None | (nenhuma seta, fase 3) | ✅ Match |
| T10 | T2, T6 (fases 1/2, cross-phase) | (sem seta — satisfeito por ordem de fase) | ✅ Match |
| T11 | T9 (mesma fase), T10 (mesma fase) | T10 → T11 (T9 satisfeito por ordem dentro da fase, roda antes) | ✅ Match |
| T12 | T9 (mesma fase), T11 (mesma fase) | T11 → T12 | ✅ Match |
| T13 | T2 (fase 1, cross-phase) | (sem seta — satisfeito por ordem de fase) | ✅ Match |
| T14 | T4, T6, T7 (fases 1/2, cross-phase), T13 (mesma fase) | T13 → T14 | ✅ Match |
| T15 | T8 (fase 2, cross-phase), T14 (mesma fase) | T14 → T15 | ✅ Match |
| T16 | T14 (fase 4, cross-phase) | (sem seta — satisfeito por ordem de fase) | ✅ Match |
| T17 | T15 (fase 4, cross-phase), T16 (mesma fase) | T16 → T17 | ✅ Match |
| T18 | T1, T3 (fase 1, cross-phase), T4 (fase 2, cross-phase), T14 (fase 4, cross-phase) | (sem seta — satisfeito por ordem de fase) | ✅ Match |

**Regra confirmada**: nenhuma tarefa depende de uma tarefa de fase posterior — todas as dependências apontam para trás (mesma fase ou fase anterior).

---

## Test Co-location Validation

| Task | Code Layer Created/Modified | Matrix Requires | Task Says | Status |
| --- | --- | --- | --- | --- |
| T1 | CLI driver | integration | integration | ✅ OK |
| T2 | Dataclasses/schemas | none | none | ✅ OK |
| T3 | Domínio de fusão (config) | unit | unit | ✅ OK |
| T4 | Domínio de fusão (loader) | unit | unit | ✅ OK |
| T5 | Domínio de fusão (risk_engine pt.1) | unit | unit | ✅ OK |
| T6 | Domínio de fusão (risk_engine pt.2) | unit | unit | ✅ OK |
| T7 | Domínio de fusão (hysteresis) | unit | unit | ✅ OK |
| T8 | Domínio de fusão (transitions) | unit | unit | ✅ OK |
| T9 | AWS integration (`ensure_subscription`) | integration | integration | ✅ OK |
| T10 | Domínio de fusão (alert, sem I/O externo) | unit | unit | ✅ OK |
| T11 | AWS integration (handler) | integration | integration | ✅ OK |
| T12 | AWS integration (infra) | integration | integration | ✅ OK |
| T13 | Dataclasses/schemas | none | none | ✅ OK |
| T14 | Rotas da API | integration (TestClient) | integration | ✅ OK |
| T15 | Rotas da API | integration (TestClient) | integration | ✅ OK |
| T16 | Dashboard Streamlit | none (manual) | none (manual) | ✅ OK |
| T17 | Dashboard Streamlit | none (manual) | none (manual) | ✅ OK |
| T18 | Config curada | integration (indireta) | integration | ✅ OK |

Todas as 18 tarefas passam na validação — nenhuma violação encontrada.
