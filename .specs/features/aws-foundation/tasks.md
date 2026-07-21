# aws-foundation Tasks

## Execution Protocol (MANDATORY -- do not skip)

Implement these tasks with the `tlc-spec-driven` skill: **activate it by name and follow its Execute flow and Critical Rules.** Do not search for skill files by filesystem path.

**If the skill cannot be activated, STOP and tell the user.**

---

**Design**: `.specs/features/aws-foundation/design.md`
**Status**: Done — 8/8 tarefas, **Verifier PASS**. aws-foundation FECHADA.

## Progresso

| Fase | Tarefas | Status |
| --- | --- | --- |
| 1 — Config e factory | T1–T2 | ✅ (`75f421f`, `76f7c44`) |
| 2 — Interfaces e registry | T3–T4 | ✅ (`ab8ecf5`, `80d0dfa`) |
| 3 — Adapters cloud | T5–T6 | ✅ (`1e7936b`, `0f2d8a4`) |
| 4 — IaC idempotente | T7–T8 | ✅ (`b303225`, `9d3ce5c`) |

Suíte: 254 testes verdes (**47 de aws-foundation** — contagem corrigida; 36 unit + 11 integração
contra LocalStack real), lint limpo. Verifier: PASS (10/12 mutantes mortos; 2 sobreviventes
aceitos como dívida de teste — ver validation.md).

---

## Test Coverage Matrix

> Gerada do design + stack já confirmada em F0/F3 (pytest + ruff; guidelines: nenhuma além de `pyproject.toml`/`ruff.toml` — defaults fortes aplicados). Textract/Rekognition não existem no LocalStack Community (AD-035): os wrappers cloud são testados com um **cliente boto3 fake por duck-typing** (objeto Python com os métodos certos, sem `moto`, sem rede). Já `provision.py` é testado contra **LocalStack real** (Docker, AD-038) — a fixture de integração checa se o LocalStack responde e pula com mensagem clara se não estiver de pé (`make localstack-up`), em vez de falhar toda a suíte em máquinas sem Docker rodando.

| Code Layer | Required Test Type | Coverage Expectation | Location Pattern | Run Command |
| --- | --- | --- | --- | --- |
| Domínio (`AwsConfig`/`load_aws_config`, `get_client`, registry de adapters, wrappers `TextractExtractor`/`RekognitionAnalyzer`) | unit | Todos os ramos; 1:1 com os ACs da spec; edge cases (`ENV` inválido, variável ausente, adapter não registrado, resposta do provedor sem campos esperados) | `backend/tests/aws/test_*.py` | `pytest -q -m "not integration"` |
| Guarda "sem `boto3.client` direto" (grep repo-wide) | unit | Verifica todo `backend/` exceto `clients.py` | `backend/tests/aws/test_no_direct_boto3_client.py` | `pytest -q -m "not integration"` |
| `provision.py` (`ensure_bucket`/`ensure_topic`/`ensure_table`/`main`) | integration | Happy path (cria) + idempotência (roda 2x, segunda não recria) + os 3 recursos, contra LocalStack real; skip com mensagem clara se LocalStack não responder | `backend/tests/integration/test_aws_provision.py` | `pytest -q` (requer `make localstack-up`) |

## Gate Check Commands

| Gate Level | When to Use | Command |
| --- | --- | --- |
| Quick | Após tarefas só com testes unitários | `pytest -q -m "not integration"` |
| Full | Após tarefas com testes de integração | `pytest -q` |
| Build | Fim de fase | `make lint && pytest -q -m "not integration"` (integração exige LocalStack de pé; roda separado) |

---

## Execution Plan

8 tarefas em 4 fases; cabe num único batch (≤ ~8) → execução inline, sem sub-agentes. Verifier independente ao final.

### Phase 1: Config e factory

```
T1 → T2
```

### Phase 2: Interfaces e registry de adapters

```
T3 → T4
```

### Phase 3: Adapters cloud (Textract/Rekognition)

```
T5 → T6
```

### Phase 4: IaC idempotente

```
T7 → T8
```

---

## Task Breakdown

### T1: `AwsConfig` + `load_aws_config()`

**What**: Dataclass `AwsConfig` e função que lê `ENV`/`AWS_REGION`/`LOCALSTACK_ENDPOINT` do ambiente, valida e resolve a config — sem fazer nenhuma chamada AWS.
**Where**: `backend/aws/clients.py`, `backend/tests/aws/test_clients_config.py`
**Depends on**: None
**Reuses**: `common/logging.py`
**Requirement**: AWSF-01, AWSF-02

**Tools**: MCP: NONE · Skill: NONE

**Done when**:
- [ ] `AwsConfig(env, region, endpoint_url)` — `endpoint_url` só preenchido quando `env == "local"`
- [ ] `load_aws_config()` lê `ENV`; `ENV` fora de `{local, cloud}` levanta `ValueError` nomeando o valor recebido
- [ ] `ENV=local` sem `LOCALSTACK_ENDPOINT` levanta erro nomeando a variável ausente
- [ ] `ENV=cloud` não exige `LOCALSTACK_ENDPOINT`; `endpoint_url` resolvido é `None`
- [ ] Nenhum segredo hardcoded — credenciais dummy (`test`/`test`) só aparecem como constante de teste/doc, nunca lidas de arquivo versionado
- [ ] Testes: `ENV=local` completo, `ENV=cloud` completo, `ENV` inválido, `ENV=local` sem endpoint, `AWS_REGION` ausente
- [ ] Gate: `pytest -q -m "not integration"` · Test count: ≥ 5

**Tests**: unit · **Gate**: quick
**Commit**: `feat(aws-foundation): AwsConfig e load_aws_config por ENV`

---

### T2: `get_client()` + guarda "sem boto3.client direto"

**What**: `get_client(service, config=None)` que devolve o cliente boto3 configurado (endpoint só se `local`); teste de guarda que falha se qualquer arquivo fora de `clients.py` chamar `boto3.client(` diretamente.
**Where**: `backend/aws/clients.py` (modificar), `backend/tests/aws/test_clients_get_client.py`, `backend/tests/aws/test_no_direct_boto3_client.py`
**Depends on**: T1
**Reuses**: `load_aws_config` (T1)
**Requirement**: AWSF-01, AWSF-03, AWSF-07

**Tools**: MCP: NONE · Skill: NONE

**Done when**:
- [ ] `get_client("s3")` com `ENV=local` resolve `endpoint_url=http://localhost:4566`, credenciais dummy, região `us-east-1`
- [ ] `get_client("s3")` com `ENV=cloud` resolve sem `endpoint_url` (verificado inspecionando `client.meta.endpoint_url` ou config resolvida, sem chamada de rede)
- [ ] Teste de guarda: varre `backend/` (exceto `clients.py` e os próprios testes) procurando `boto3.client(`; falha citando o arquivo se encontrar
- [ ] Mensagem de erro quando o serviço/endpoint não responde é acionável (documentada; verificação funcional fica para T8, que já usa LocalStack de pé)
- [ ] Testes: config local resolve endpoint certo; config cloud resolve sem endpoint; guarda passa no estado atual do repo; guarda pega uma violação injetada num arquivo temporário de teste
- [ ] Gate: `pytest -q -m "not integration"` · Test count: ≥ 4

**Tests**: unit · **Gate**: quick
**Commit**: `feat(aws-foundation): factory get_client e guarda contra boto3.client direto`

---

### T3: Modelos de dados + interfaces `TextExtractor`/`ImageAnalyzer`

**What**: Dataclasses (`ExtractedText`, `ImageLabel`, `ImageAnalysis`) e os `Protocol` das duas interfaces.
**Where**: `backend/aws/adapters/__init__.py`, `backend/tests/aws/test_adapters_types.py`
**Depends on**: T2
**Reuses**: —
**Requirement**: AWSF-04

**Tools**: MCP: NONE · Skill: NONE

**Done when**:
- [ ] `ExtractedText(lines: list[str], raw: dict)`, `ImageLabel(name: str, confidence: float)`, `ImageAnalysis(labels: list[ImageLabel], raw: dict)` — todos `frozen=True`
- [ ] `TextExtractor`/`ImageAnalyzer` como `Protocol` com o método correto (`extract`/`analyze`)
- [ ] Um objeto duck-typed com o método certo satisfaz o `Protocol` (`isinstance` com `runtime_checkable`, ou verificação estrutural equivalente)
- [ ] Testes: construção dos dataclasses, imutabilidade (`frozen`), conformidade estrutural ao Protocol
- [ ] Gate: `pytest -q -m "not integration"` · Test count: ≥ 3

**Tests**: unit · **Gate**: quick
**Commit**: `feat(aws-foundation): modelos de dados e interfaces TextExtractor/ImageAnalyzer`

---

### T4: Registro e resolução de adapters por `ENV`

**What**: `register_text_extractor`/`register_image_analyzer` e `get_text_extractor`/`get_image_analyzer`, com erro claro quando nada está registrado para o `ENV` ativo.
**Where**: `backend/aws/adapters/__init__.py` (modificar), `backend/tests/aws/test_adapters_registry.py`
**Depends on**: T3
**Reuses**: `AwsConfig`/`load_aws_config` (T1) para resolver o `ENV` ativo
**Requirement**: AWSF-05

**Tools**: MCP: NONE · Skill: NONE

**Done when**:
- [ ] `register_text_extractor(env, factory)` guarda a factory por ambiente; `get_text_extractor(env)` chama a factory registrada e devolve a instância
- [ ] `ENV` sem nada registrado levanta erro nomeando o `ENV` (nunca devolve `None`)
- [ ] Mesmo mecanismo para `ImageAnalyzer`
- [ ] Registro é isolável entre testes (fixture que limpa o registro antes/depois de cada teste, evitando vazamento de estado global)
- [ ] Testes: registrar fake para `local` e `cloud`, resolver cada um corretamente; `ENV` sem registro levanta erro; registro de um não interfere no do outro tipo (`TextExtractor` vs `ImageAnalyzer`)
- [ ] Gate: `pytest -q -m "not integration"` · Test count: ≥ 5

**Tests**: unit · **Gate**: quick
**Commit**: `feat(aws-foundation): registro e resolucao de adapters por ENV`

---

### T5: `TextractExtractor` (wrapper cloud)

**What**: Implementação de `TextExtractor` que chama `detect_document_text` via o cliente injetado, extrai linhas de `Blocks` tipo `LINE`, preserva a resposta bruta.
**Where**: `backend/aws/adapters/cloud.py`, `backend/tests/aws/test_cloud_textract.py`
**Depends on**: T4
**Reuses**: `ExtractedText` (T3), interface `TextExtractor` (T3)
**Requirement**: AWSF-04, AWSF-05

**Tools**: MCP: NONE · Skill: NONE

**Done when**:
- [ ] `TextractExtractor(client).extract(pdf_bytes)` chama `client.detect_document_text(Document={"Bytes": pdf_bytes})`
- [ ] Extrai `.lines` só dos blocos com `BlockType == "LINE"`, na ordem em que aparecem na resposta
- [ ] `.raw` preserva a resposta completa do cliente, sem transformação
- [ ] Resposta sem nenhum bloco `LINE` produz `lines=[]`, não erro
- [ ] Testes: cliente fake (duck-typed) com resposta canônica de 2+ linhas e blocos de outros tipos misturados (`PAGE`, `WORD`) — confirma que só `LINE` é extraído e na ordem certa; resposta sem `LINE` nenhum
- [ ] Gate: `pytest -q -m "not integration"` · Test count: ≥ 3

**Tests**: unit · **Gate**: quick
**Commit**: `feat(aws-foundation): TextractExtractor (wrapper cloud)`

---

### T6: `RekognitionAnalyzer` (wrapper cloud) + registro dos dois adapters cloud

**What**: Implementação de `ImageAnalyzer` via `detect_labels`; registra `TextractExtractor` e `RekognitionAnalyzer` para `env="cloud"`.
**Where**: `backend/aws/adapters/cloud.py` (modificar), `backend/tests/aws/test_cloud_rekognition.py`
**Depends on**: T5
**Reuses**: `ImageAnalysis`/`ImageLabel` (T3), `register_*` (T4), `get_client` (T2)
**Requirement**: AWSF-04, AWSF-05

**Tools**: MCP: NONE · Skill: NONE

**Done when**:
- [ ] `RekognitionAnalyzer(client).analyze(image_bytes)` chama `client.detect_labels(Image={"Bytes": image_bytes})`
- [ ] Mapeia cada label da resposta para `ImageLabel(name, confidence)`; `.raw` preserva a resposta completa
- [ ] Uma função/registro (ex. `register_cloud_adapters()`) registra as duas implementações para `env="cloud"`, usando `get_client` para construir o cliente real
- [ ] Após o registro, `get_text_extractor("cloud")`/`get_image_analyzer("cloud")` devolvem instâncias de `TextractExtractor`/`RekognitionAnalyzer`
- [ ] Testes: cliente fake com 2+ labels de confiança variada; resposta sem labels; registro efetivamente resolve pelo `get_*` do T4
- [ ] Gate: `pytest -q -m "not integration"` · Test count: ≥ 3

**Tests**: unit · **Gate**: quick
**Commit**: `feat(aws-foundation): RekognitionAnalyzer e registro dos adapters cloud`

---

### T7: `provision.py` — `ensure_bucket`/`ensure_topic`/`ensure_table`

**What**: As três funções idempotentes de IaC, cada uma checando existência antes de criar.
**Where**: `backend/aws/provision.py`, `backend/tests/integration/test_aws_provision.py`
**Depends on**: T6
**Reuses**: `get_client` (T2)
**Requirement**: AWSF-06

**Tools**: MCP: NONE · Skill: NONE

**Done when**:
- [ ] `ensure_bucket(name)` — `head_bucket` para checar; cria com `create_bucket` só se ausente; devolve `ProvisionResult(created=True/False)`
- [ ] `ensure_topic(name)` — SNS não tem "check" direto por nome; usar `create_topic` (que é idempotente por natureza no SNS — mesmo nome devolve o mesmo ARN) e reportar `created` com base em se o tópico já tinha mensagens/atributos prévios, OU documentar essa particularidade se o SNS não permitir diferenciar "criado agora" de "já existia" (ver Nota abaixo)
- [ ] `ensure_table(name)` — `describe_table` para checar; cria com `create_table` só se ausente
- [ ] Rodar cada `ensure_*` duas vezes seguidas é idempotente (segunda não falha, não duplica)
- [ ] Testes (integration, **LocalStack real**, pula com mensagem clara se `:4566` não responder): cada recurso criado do zero; cada recurso já existente não recriado; `ProvisionResult.created` reflete corretamente cada caso
- [ ] Gate: `pytest -q` (com LocalStack de pé) · Test count: ≥ 4

**Tests**: integration · **Gate**: full
**Commit**: `feat(aws-foundation): provisionamento idempotente de S3/SNS/DynamoDB`

> **Nota de implementação**: SNS `create_topic` é naturalmente idempotente (mesmo nome → mesmo ARN, sem erro), mas a API não expõe diretamente "já existia antes desta chamada" — a tarefa deve verificar isso no LocalStack real antes de decidir como popular `ProvisionResult.created` para o tópico (ex.: usar `list_topics` antes de criar, similar ao padrão de bucket/tabela) em vez de presumir.

---

### T8: `main()` de `provision.py` + `make infra-local`/`infra-cloud`

**What**: `main()` lê os nomes do `.env` (`S3_BUCKET`, `SNS_TOPIC`, `DYNAMODB_TABLE`), chama os três `ensure_*`, loga o resultado; confirma que os alvos do Makefile (já commitados) funcionam de ponta a ponta contra o LocalStack.
**Where**: `backend/aws/provision.py` (modificar), `backend/tests/integration/test_aws_provision.py` (modificar)
**Depends on**: T7
**Reuses**: `ensure_*` (T7)
**Requirement**: AWSF-06, AWSF-07

**Tools**: MCP: NONE · Skill: NONE

**Done when**:
- [ ] `main()` lê `S3_BUCKET`/`SNS_TOPIC`/`DYNAMODB_TABLE` do ambiente, chama os três `ensure_*`, loga resultado por recurso
- [ ] `make infra-local` (já existente no Makefile) executa `main()` com `ENV=local` de ponta a ponta contra o LocalStack real e cria os três recursos
- [ ] Rodar `make infra-local` duas vezes seguidas é idempotente (verificado de verdade, não só por unidade)
- [ ] LocalStack fora do ar → erro acionável mencionando `make localstack-up` (AWSF-07), não traceback cru
- [ ] Testes: `main()` end-to-end cria os três recursos; segunda execução idempotente; simulação de LocalStack inativo produz mensagem clara (via endpoint incorreto/porta fechada, sem exigir derrubar o LocalStack de verdade)
- [ ] Gate: `pytest -q` (com LocalStack de pé) · Test count: ≥ 3

**Tests**: integration · **Gate**: full
**Commit**: `feat(aws-foundation): main() de provisionamento e integracao com make infra-*`

---

## Phase Execution Map

```
Phase 1:  T1 → T2
Phase 2:  T3 → T4
Phase 3:  T5 → T6
Phase 4:  T7 → T8
```

8 tarefas, um único batch (≤ ~8) → execução inline, sem sub-agentes. Verifier independente ao final.

---

## Task Granularity Check

| Task | Scope | Status |
| --- | --- | --- |
| T1 | 1 dataclass + 1 função | ✅ Granular |
| T2 | 1 função + 1 teste de guarda (mesmo tema: isolamento de boto3) | ✅ Granular |
| T3 | 3 dataclasses + 2 Protocols (mesmo tema: tipos) | ✅ Granular |
| T4 | 2 pares register/get (mesmo mecanismo, 2 tipos) | ✅ Granular |
| T5 | 1 classe (wrapper Textract) | ✅ Granular |
| T6 | 1 classe + 1 função de registro (cohesos: "ativar o cloud") | ✅ Granular |
| T7 | 3 funções idempotentes (mesmo padrão check-then-create) | ✅ Granular |
| T8 | 1 função de orquestração + wiring | ✅ Granular |

---

## Diagram-Definition Cross-Check

| Task | Depends On (corpo) | Diagrama | Status |
| --- | --- | --- | --- |
| T1 | None | início Phase 1 | ✅ |
| T2 | T1 | T1 → T2 | ✅ |
| T3 | T2 | Phase 2 após Phase 1 | ✅ |
| T4 | T3 | T3 → T4 | ✅ |
| T5 | T4 | Phase 3 após Phase 2 | ✅ |
| T6 | T5 | T5 → T6 | ✅ |
| T7 | T6 | Phase 4 após Phase 3 | ✅ |
| T8 | T7 | T7 → T8 | ✅ |

---

## Test Co-location Validation

| Task | Camada | Matriz exige | Tarefa diz | Status |
| --- | --- | --- | --- | --- |
| T1 | Domínio | unit | unit | ✅ |
| T2 | Domínio + guarda | unit | unit | ✅ |
| T3 | Domínio | unit | unit | ✅ |
| T4 | Domínio | unit | unit | ✅ |
| T5 | Domínio | unit | unit | ✅ |
| T6 | Domínio | unit | unit | ✅ |
| T7 | `provision.py` | integration | integration | ✅ |
| T8 | `provision.py` | integration | integration | ✅ |

Nenhuma violação.

---

## Requirement Traceability

| Requirement | Tarefas | Status |
| --- | --- | --- |
| AWSF-01 | T1, T2 | Mapeado |
| AWSF-02 | T1 | Mapeado |
| AWSF-03 | T2 | Mapeado |
| AWSF-04 | T3, T5, T6 | Mapeado |
| AWSF-05 | T4, T5, T6 | Mapeado |
| AWSF-06 | T7, T8 | Mapeado |
| AWSF-07 | T2, T8 | Mapeado |

**Coverage:** 7 de 7 requisitos mapeados para tarefas — 0 não mapeados.
