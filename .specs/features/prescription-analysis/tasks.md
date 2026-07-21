# F4 — Prescription Analysis Tasks

## Execution Protocol (MANDATORY -- do not skip)

Implement these tasks with the `tlc-spec-driven` skill: **activate it by name and follow its Execute flow and Critical Rules.** Do not search for skill files by filesystem path.

**If the skill cannot be activated, STOP and tell the user.**

---

**Design**: `.specs/features/prescription-analysis/design.md`
**Status**: Draft

---

## Test Coverage Matrix

> Gerada do design + stack já confirmada em F0/F3/aws-foundation (pytest + ruff; guidelines: nenhuma além de `pyproject.toml`/`ruff.toml` — defaults fortes aplicados). Mesmo princípio da fundação: **domínio puro sem AWS** vira unit; qualquer coisa que toque um cliente AWS real (DynamoDB, S3, Lambda) vira integration contra **LocalStack real** (já de pé nesta sessão).

| Code Layer | Required Test Type | Coverage Expectation | Location Pattern | Run Command |
| --- | --- | --- | --- | --- |
| Domínio puro (`models`, `catalog`, `rules`, `generator`, `adapters.PdfplumberExtractor`, `parser`, `evaluate`) | unit | Todos os ramos; 1:1 com os ACs da spec; edge cases (medicamento fora do catálogo, campo ausente, primeiro registro sem histórico, threshold exato de 50%) | `backend/tests/prescription/test_*.py` | `pytest -q -m "not integration"` |
| `history.py` (DynamoDB real) | integration | Dedup idempotente, `get_latest` com/sem histórico, condição de escrita (`ConditionExpression`) | `backend/tests/integration/test_prescription_history.py` | `pytest -q` (requer `make localstack-up`) |
| `logic.py` + `handler.py` (orquestração, usa `history.py` real) | integration | Pipeline completo por PDF: dose normal, dose fora de faixa, mudança abrupta, evento duplicado, erro de parsing | `backend/tests/integration/test_prescription_logic.py` | `pytest -q` |
| `infra.py` + deploy real (Lambda no LocalStack, gatilho S3) | integration | `make infra-prescription` roda; upload real de PDF no S3 dispara o Lambda de verdade; resultado confere no DynamoDB | `backend/tests/integration/test_prescription_infra.py` | `pytest -q` |

## Gate Check Commands

| Gate Level | When to Use | Command |
| --- | --- | --- |
| Quick | Após tarefas só com testes unitários | `pytest -q -m "not integration"` |
| Full | Após tarefas com testes de integração | `pytest -q` |
| Build | Fim de fase | `make lint && pytest -q -m "not integration"` (integração exige LocalStack de pé; roda separado) |

---

## Execution Plan

8 tarefas em 7 fases; cabe num único batch (≤ ~8) → execução inline, sem sub-agentes. Verifier independente ao final.

### Phase 1: Catálogo e regras clínicas

```
T1
```

### Phase 2: Geração sintética

```
T2
```

### Phase 3: Extração local

```
T3
```

### Phase 4: Parsing

```
T4
```

### Phase 5: Histórico (DynamoDB)

```
T5
```

### Phase 6: Orquestração + handler

```
T6
```

### Phase 7: Infra da Lambda + integração real, e avaliação

```
T7 → T8
```

---

## Task Breakdown

### T1: `models.py` + `catalog.py` + `rules.py` — catálogo e regras clínicas

**What**: Dataclasses centrais (`PrescriptionRecord`, `DrugRange`, `AnomalyResult`), o catálogo curado de faixas terapêuticas com `lookup()`, e as duas regras de anomalia (dose fora de faixa; mudança abrupta vs. registro anterior).
**Where**: `backend/pipelines/prescription/models.py`, `backend/pipelines/prescription/catalog.py`, `backend/pipelines/prescription/rules.py`, `backend/tests/prescription/test_catalog.py`, `backend/tests/prescription/test_rules.py`
**Depends on**: None
**Reuses**: —
**Requirement**: PRESC-05, PRESC-12, PRESC-13, PRESC-14

**Tools**: MCP: NONE · Skill: NONE

**Done when**:
- [ ] `catalog.lookup(nome)` devolve `DrugRange | None`; catálogo com ~10–15 medicamentos comuns e faixas de bula pública, com comentário marcando "validar contra bulário oficial antes do relatório"
- [ ] `rules.check_dose_range(record, catalog)` — dentro da faixa → `AnomalyResult(kind="normal")`; fora → `"dose_fora_de_faixa"`; medicamento ausente do catálogo → `"sem_referencia"` (nunca normal/anômalo por omissão)
- [ ] `rules.check_abrupt_change(record, previous, threshold=0.5)` — `previous=None` → `"normal"` sem falso positivo; variação > 50% → `"mudanca_abrupta"`; variação exatamente 50% → **não** anômalo (estrito, mesma convenção de F3/AD-027)
- [ ] Testes: faixa normal, faixa abaixo/acima do limite, medicamento fora do catálogo, primeiro registro (`previous=None`), variação exatamente no threshold, variação acima do threshold
- [ ] Gate: `pytest -q -m "not integration"` · Test count: ≥ 8

**Tests**: unit · **Gate**: quick
**Commit**: `feat(f4): catalogo de faixas terapeuticas e regras de anomalia`

---

### T2: `generator.py` — prescrições sintéticas com ground truth

**What**: Gera PDFs de prescrição (via `reportlab`) com casos normais e anômalos em proporção conhecida, mais o ground truth correspondente.
**Where**: `backend/pipelines/prescription/generator.py`, `backend/tests/prescription/test_generator.py`
**Depends on**: T1
**Reuses**: `catalog.lookup` (T1), `models.PrescriptionRecord`/`GroundTruthEntry`
**Requirement**: PRESC-01

**Tools**: MCP: NONE · Skill: NONE

**Done when**:
- [ ] `generate_prescription(patient_id, drug, dose, frequency, seed) -> bytes` produz um PDF real (texto embutido, não imagem)
- [ ] `generate_dataset(n, seed, anomaly_rate)` gera `n` PDFs + `GroundTruthEntry` por PDF, com a proporção de anômalos batendo (dentro de tolerância determinística pela seed)
- [ ] Mesma seed produz o mesmo dataset (determinismo, mesmo padrão de F3)
- [ ] PDF gerado é extraível de volta por `pdfplumber` sem erro (round-trip verificado no próprio teste, não presumido)
- [ ] Testes: geração de 1 PDF normal, 1 anômalo (dose fora de faixa), determinismo por seed, round-trip real com `pdfplumber.open`
- [ ] Gate: `pytest -q -m "not integration"` · Test count: ≥ 4

**Tests**: unit · **Gate**: quick
**Commit**: `feat(f4): gerador de prescricoes sinteticas com ground truth`

---

### T3: `adapters.py` — `PdfplumberExtractor` (TextExtractor local)

**What**: Implementação local de `TextExtractor` via `pdfplumber`; registro para `env="local"`.
**Where**: `backend/pipelines/prescription/adapters.py`, `backend/tests/prescription/test_adapters.py`
**Depends on**: T2
**Reuses**: `aws.adapters.ExtractedText`/`register_text_extractor`/`get_text_extractor`, `generator.generate_prescription` (T2, para gerar o PDF de teste)
**Requirement**: PRESC-03 (raia local)

**Tools**: MCP: NONE · Skill: NONE

**Done when**:
- [ ] `PdfplumberExtractor.extract(pdf_bytes)` devolve `ExtractedText` com `.lines` na ordem correta (mesmo formato de linhas do `TextractExtractor` da fundação)
- [ ] `register_local_adapters()` registra a implementação para `"local"`; após o registro, `get_text_extractor("local")` devolve uma instância de `PdfplumberExtractor`
- [ ] PDF real gerado por `generator.generate_prescription` é extraído corretamente (round-trip com dado real do pipeline, não só um PDF de brinquedo)
- [ ] Testes: extração de PDF real do gerador; registro resolve via `get_text_extractor("local")`; `.raw` presente para debug
- [ ] Gate: `pytest -q -m "not integration"` · Test count: ≥ 3

**Tests**: unit · **Gate**: quick
**Commit**: `feat(f4): PdfplumberExtractor e registro do adapter local`

---

### T4: `parser.py` — estruturação do registro

**What**: Transforma `ExtractedText` em `PrescriptionRecord`, sinalizando `ParseFailure` quando um campo obrigatório está ausente ou não é numérico.
**Where**: `backend/pipelines/prescription/parser.py`, `backend/tests/prescription/test_parser.py`
**Depends on**: T3
**Reuses**: `models.PrescriptionRecord`, `adapters.PdfplumberExtractor` + `generator` (T2/T3, para produzir `ExtractedText` real de teste)
**Requirement**: PRESC-04

**Tools**: MCP: NONE · Skill: NONE

**Done when**:
- [ ] `parse_prescription(extracted)` extrai paciente, medicamento, dose (numérica), unidade, frequência, timestamp de um `ExtractedText` real (gerado e extraído via T2+T3, não um texto inventado à mão)
- [ ] Dose não numérica ou campo ausente → `ParseFailure(reason=...)` nomeando o campo, nunca um valor inferido/adivinhado
- [ ] Testes: parsing de um PDF real completo; dose ausente; dose não numérica; frequência ausente
- [ ] Gate: `pytest -q -m "not integration"` · Test count: ≥ 4

**Tests**: unit · **Gate**: quick
**Commit**: `feat(f4): parser de campos estruturados da prescricao`

---

### T5: `history.py` — persistência e histórico no DynamoDB

**What**: Deduplicação por evento S3 (ETag+chave) e consulta do registro mais recente do paciente/medicamento, contra o DynamoDB real (LocalStack).
**Where**: `backend/pipelines/prescription/history.py`, `backend/tests/integration/test_prescription_history.py`
**Depends on**: T1
**Reuses**: `aws.clients.get_client("dynamodb")`, `models.PrescriptionRecord`, schema `pk`/`sk` já provisionado pela fundação
**Requirement**: PRESC-11, PRESC-13 (suporte)

**Tools**: MCP: NONE · Skill: NONE

**Done when**:
- [ ] `dedup_key(bucket, key, etag)` determinística a partir dos três valores
- [ ] `save_record(record, dedup_key)` grava com `pk=PATIENT#<id>#DRUG#<drug>`, `sk=timestamp`; devolve `False` (não duplica) se o `dedup_key` já existe, via `ConditionExpression`
- [ ] `get_latest(patient_id, drug)` devolve o registro de maior `sk` (mais recente) ou `None` se não há histórico
- [ ] Testes (LocalStack real, tabela provisionada via `aws.provision.ensure_table`): grava e recupera; grava o mesmo `dedup_key` duas vezes (segunda não duplica); `get_latest` sem histórico devolve `None`; `get_latest` com múltiplos registros devolve o mais recente
- [ ] Gate: `pytest -q` (com LocalStack de pé) · Test count: ≥ 4

**Tests**: integration · **Gate**: full
**Commit**: `feat(f4): persistencia e consulta de historico no DynamoDB`

---

### T6: `logic.py` + `handler.py` — orquestração e handler Lambda fino

**What**: `logic.process()` orquestra parser→regras→histórico→evidência para um PDF; `handler.py` é o Lambda fino que lê o evento S3 e chama `logic.process`.
**Where**: `backend/pipelines/prescription/logic.py`, `backend/pipelines/prescription/handler.py`, `backend/tests/integration/test_prescription_logic.py`
**Depends on**: T1, T3, T4, T5
**Reuses**: `parser`, `rules`, `history`, `adapters`, `common.evidence.save_evidence`
**Requirement**: PRESC-02, PRESC-03, PRESC-06, PRESC-07 (lógica)

**Tools**: MCP: NONE · Skill: NONE

**Done when**:
- [ ] `logic.process(pdf_bytes, bucket, key, etag)` extrai (via adapter local), parseia, aplica as duas regras, consulta/grava histórico, gera evidência (`common.evidence`) quando anômalo, devolve `ProcessResult`
- [ ] Evento já processado (mesmo `dedup_key`) → `ProcessResult(deduplicated=True)`, sem duplicar nem reprocessar a regra de mudança abrupta contra si mesmo
- [ ] `handler.lambda_handler(event, context)` lê o evento S3 (bucket/key/etag), baixa o objeto via `get_client("s3")`, chama `logic.process`; erro de extração/parsing é logado e o objeto movido para `errors/` no S3, sem propagar exceção
- [ ] Testes (LocalStack real): pipeline completo com dose normal; dose fora de faixa (evidência gerada); mudança abrupta (2 prescrições em sequência); evento S3 duplicado (mesmo objeto processado 2x não duplica); PDF corrompido/ilegível não trava o handler
- [ ] Gate: `pytest -q` · Test count: ≥ 5

**Tests**: integration · **Gate**: full
**Commit**: `feat(f4): orquestracao do processamento e handler Lambda`

---

### T7: `infra.py` — provisionamento e deploy real da Lambda

**What**: Empacota e implanta o Lambda de verdade no LocalStack, configura o gatilho S3→Lambda, e confirma via upload real de PDF que o fluxo inteiro dispara e processa.
**Where**: `backend/pipelines/prescription/infra.py`, `backend/tests/integration/test_prescription_infra.py`, `Makefile` (novo alvo)
**Depends on**: T6
**Reuses**: `aws.clients.get_client`, padrão idempotente de `aws.provision`, `handler.py` (T6, o código empacotado)

**Achado a verificar nesta tarefa (não presumir)**: a API exata do LocalStack para `create_function` + `put_bucket_notification_configuration` + `add_permission` do Lambda para o S3 invocar; e se o zip com `pdfplumber`/`pdfminer.six` cabe no limite do Lambda.

**Requirement**: PRESC-02, PRESC-07, PRESC-08, PRESC-09

**Tools**: MCP: NONE · Skill: NONE

**Done when**:
- [ ] `package_lambda()` empacota `handler.py` + módulos de `pipelines/prescription/` + dependências num zip válido
- [ ] `ensure_lambda(name, zip_bytes, role_arn)` — checa existência antes de criar/atualizar (mesmo padrão checar-antes-de-criar de `aws.provision`)
- [ ] `ensure_s3_trigger(bucket, function_arn)` configura a notificação do bucket + a permissão do Lambda para ser invocado pelo S3
- [ ] Alvo `make infra-prescription` (ou integrado a `infra-local`) roda `infra.py` de ponta a ponta
- [ ] Nenhum `boto3.client` direto (a guarda da fundação, que varre `backend/` inteiro, cobre `pipelines/prescription/` automaticamente — confirmar que passa)
- [ ] Testes: upload real de um PDF (via `generator`) no bucket S3 dispara o Lambda de verdade; resultado (registro/anomalia) confere no DynamoDB via `history.get_latest`; segunda execução de `infra.py` é idempotente (não recria a função)
- [ ] Gate: `pytest -q` (com LocalStack de pé) · Test count: ≥ 3

**Tests**: integration · **Gate**: full
**Commit**: `feat(f4): provisionamento e deploy real do Lambda no LocalStack`

---

### T8: `evaluate.py` — precision/recall vs. ground truth

**What**: Compara os registros persistidos (via `history`) contra o ground truth do gerador e calcula precision/recall por tipo de anomalia.
**Where**: `backend/pipelines/prescription/evaluate.py`, `backend/tests/prescription/test_evaluate.py`
**Depends on**: T2, T5
**Reuses**: `common.metrics.binary_metrics`/`save_report`, `models.GroundTruthEntry`
**Requirement**: PRESC-10

**Tools**: MCP: NONE · Skill: NONE

**Done when**:
- [ ] `evaluate(ground_truth, records)` calcula precision/recall/F1 por tipo de anomalia (`dose_fora_de_faixa`, `mudanca_abrupta`), reutilizando `common.metrics.binary_metrics`
- [ ] Registro marcado como "sem_referencia" (medicamento fora do catálogo) é excluído do cálculo, não contado como falso positivo/negativo
- [ ] Testes: conjunto misto normal/anômalo bate com o ground truth; registro "sem_referencia" excluído do cálculo; conjunto sem nenhum anômalo (recall indefinido, mesmo padrão de F3/VITALS-10)
- [ ] Gate: `pytest -q -m "not integration"` · Test count: ≥ 3

**Tests**: unit · **Gate**: quick
**Commit**: `feat(f4): avaliacao de precision/recall contra o ground truth`

---

## Phase Execution Map

```
Phase 1:  T1
Phase 2:  T2
Phase 3:  T3
Phase 4:  T4
Phase 5:  T5
Phase 6:  T6
Phase 7:  T7 → T8
```

8 tarefas, um único batch (≤ ~8) → execução inline, sem sub-agentes. Verifier independente ao final.

---

## Task Granularity Check

| Task | Scope | Status |
| --- | --- | --- |
| T1 | 3 arquivos pequenos, mesmo tema (conhecimento clínico: catálogo + 2 regras) | ✅ Granular |
| T2 | 1 módulo (gerador) | ✅ Granular |
| T3 | 1 classe + 1 função de registro | ✅ Granular |
| T4 | 1 função (parser) | ✅ Granular |
| T5 | 3 funções cohesas (mesmo tema: persistência) | ✅ Granular |
| T6 | 2 arquivos pequenos, mesmo tema (processar 1 evento: lógica + handler fino) | ✅ Granular |
| T7 | 3 funções cohesas (mesmo tema: provisionar e implantar a Lambda) | ✅ Granular |
| T8 | 1 função (avaliação) | ✅ Granular |

---

## Diagram-Definition Cross-Check

| Task | Depends On (corpo) | Diagrama | Status |
| --- | --- | --- | --- |
| T1 | None | início Phase 1 | ✅ |
| T2 | T1 | Phase 2 após Phase 1 | ✅ |
| T3 | T2 | Phase 3 após Phase 2 | ✅ |
| T4 | T3 | Phase 4 após Phase 3 | ✅ |
| T5 | T1 | Phase 5 após Phase 4 (T1 já concluída antes) | ✅ |
| T6 | T1, T3, T4, T5 | Phase 6 após Phase 5 (todas já concluídas antes) | ✅ |
| T7 | T6 | Phase 7 início | ✅ |
| T8 | T2, T5 | T7 → T8 (ambas já concluídas antes) | ✅ |

Nenhuma dependência aponta para uma fase posterior.

---

## Test Co-location Validation

| Task | Camada | Matriz exige | Tarefa diz | Status |
| --- | --- | --- | --- | --- |
| T1 | Domínio puro | unit | unit | ✅ |
| T2 | Domínio puro | unit | unit | ✅ |
| T3 | Domínio puro (sem cliente AWS) | unit | unit | ✅ |
| T4 | Domínio puro | unit | unit | ✅ |
| T5 | `history.py` (DynamoDB real) | integration | integration | ✅ |
| T6 | `logic.py`/`handler.py` (usa `history` real) | integration | integration | ✅ |
| T7 | `infra.py` + deploy real | integration | integration | ✅ |
| T8 | Domínio puro | unit | unit | ✅ |

Nenhuma violação.

---

## Requirement Traceability

| Requirement | Tarefas | Status |
| --- | --- | --- |
| PRESC-01 | T2 | Mapeado |
| PRESC-02 | T6, T7 | Mapeado |
| PRESC-03 | T3, T6 | Mapeado |
| PRESC-04 | T4 | Mapeado |
| PRESC-05 | T1 | Mapeado |
| PRESC-06 | T6 | Mapeado |
| PRESC-07 | T6, T7 | Mapeado |
| PRESC-08 | T7 | Mapeado |
| PRESC-09 | T7 (verificado pela guarda já existente da fundação, que varre `backend/` inteiro) | Mapeado |
| PRESC-10 | T8 | Mapeado |
| PRESC-11 | T5 | Mapeado |
| PRESC-12 | T1, T5 | Mapeado |
| PRESC-13 | T1, T5 | Mapeado |
| PRESC-14 | T1 | Mapeado |
| PRESC-15 | — | **Diferido (P3, explicitamente não bloqueante)** — adaptador MIMIC-IV opcional; sem tarefa nesta rodada |

**Coverage:** 14 de 15 requisitos mapeados; PRESC-15 diferido explicitamente (P3, não bloqueia a demo).
