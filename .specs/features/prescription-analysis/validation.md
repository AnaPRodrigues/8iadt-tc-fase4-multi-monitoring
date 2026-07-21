# F4 — Prescription Analysis Validation

**Date**: 2026-07-21
**Spec**: `.specs/features/prescription-analysis/spec.md`
**Diff range**: `7fe8216..c5c9f37` (T1 catálogo/regras → T8 evaluate; inclui `95d2c03` fix de fundação descoberto durante T7)
**Verifier**: independente (author ≠ verifier); fresh-eyes, sem contexto herdado do autor

---

## Task Completion

| Task | Status  | Notes |
| ---- | ------- | ----- |
| T1   | ✅ Done | `models.py`, `catalog.py`, `rules.py` — commit `7fe8216` + fix `d5bc0e0` |
| T2   | ✅ Done | `generator.py` — commit `880112e` |
| T3   | ✅ Done | `adapters.py` — commit `765357b` |
| T4   | ✅ Done | `parser.py` — commit `5a9b2f1` |
| T5   | ✅ Done | `history.py` — commit `4e4ae28` |
| T6   | ✅ Done | `logic.py` + `handler.py` — commit `3b974b3` |
| T7   | ✅ Done | `infra.py` — commit `200ad33` (+ fix de fundação `95d2c03`, com teste próprio) |
| T8   | ⚠️ Partial | `evaluate.py` — commit `c5c9f37`; entrega métricas só para `dose_fora_de_faixa`, não para `mudanca_abrupta` (ver Gap 1) |

**STATE.md desatualizado**: o Handoff registrado em `.specs/STATE.md` afirma "T6 começada mas nenhum arquivo escrito" — isso está incorreto/obsoleto em relação ao `git log` real (T6, T7, T8 estão commitadas e com testes passando). Não é uma falha de código, é apenas o handoff que não foi atualizado após a última sessão de implementação; sinalizado para correção de higiene do `.specs/`, não bloqueia esta validação.

---

## Spec-Anchored Acceptance Criteria

### P1: Pipeline de extração e detecção de dose fora de faixa (MVP)

| Criterion (WHEN X THEN Y) | Spec-defined outcome | `file:line` + assertion | Result |
| --- | --- | --- | --- |
| AC1: gerador produz PDFs normais/anômalos em proporção conhecida, **registrando ground truth em arquivo separado do PDF** | proporção conhecida ✅ + **persistência em arquivo** do ground truth | Proporção: `backend/tests/prescription/test_generator.py:45-52` — `assert len(anomalous) > 0 / len(normal) > 0` + `assert all(e.anomaly_type == "dose_fora_de_faixa" ...)`. Persistência em arquivo: **nenhuma evidência** — `generate_dataset()` (`backend/pipelines/prescription/generator.py:64-110`) devolve `list[tuple[bytes, GroundTruthEntry]]` só em memória; nenhum `json.dump`/`csv`/arquivo é escrito em nenhum lugar do pipeline ou dos testes (`grep` confirmou zero ocorrências) | ❌ **GAP** (proporção coberta; persistência em arquivo separado do PDF não implementada) |
| AC2: upload no S3 dispara Lambda (role `LabRole`) via evento de criação | Lambda real disparada, resultado no DynamoDB | `backend/tests/integration/test_prescription_infra.py:79-101` — `test_upload_real_dispara_lambda_e_grava_no_dynamodb`: upload real, poll no DynamoDB, `assert items[0]["dose"]["N"] == "500"` | ✅ PASS |
| AC3: Lambda chama Textract/extrator para extrair campos | texto extraído corretamente do PDF real | `backend/tests/prescription/test_adapters.py:6-14` — `assert any("p42" in line ...)`; raia cloud (Textract) já coberta pela `aws-foundation` (reuso, não re-verificado aqui) | ✅ PASS |
| AC4: campos parseados estruturam registro; ausente/não numérico → sinalizado, nunca inferido | `PrescriptionRecord` com valores exatos; `ParseFailure` nomeando o campo | `backend/tests/prescription/test_parser.py:8-21` (valores exatos: `record.dose == 500.0`, `record.unit == "mg"`); `:24-31` e `:34-47` (`assert result.field == "Dose"`) | ✅ PASS |
| AC5: dose fora da faixa → anômalo "dose fora de faixa" | `AnomalyResult(kind="dose_fora_de_faixa")` | `backend/tests/prescription/test_rules.py:16-23` — `assert result.kind == "dose_fora_de_faixa"` (abaixo e acima da faixa) | ✅ PASS |
| AC6: anomalia gera evidência reproduzível (PDF anotado + motivo) no S3; execução registrada no CloudWatch | `evidence_id` não nulo; motivo presente; log da execução | Evidência: `backend/tests/integration/test_prescription_logic.py:83-91` — `assert result.evidence_id is not None`, `any(a.kind == "dose_fora_de_faixa" ...)`. **Log CloudWatch**: chamadas existem em código (`logic.py:75,87`, `handler.py:36,41,45-51`) mas **nenhum teste usa `caplog`** para afirmar conteúdo do log (arquivo/resultado/tipo) — evidence-or-zero: sub-cláusula de logging sem citação de teste | ⚠️ Spec-precision gap (evidência ✅; conteúdo do log CloudWatch sem asserção de teste) |
| AC7: falha do Textract → log + move para `errors/` + continua processando os demais | objeto movido, erro logado, lote não trava | `backend/tests/integration/test_prescription_logic.py:147-158` — `test_handler_pdf_ilegivel_move_para_errors`: `pytest.raises(ClientError)` no objeto original + `head_object` confirma em `errors/{key}`. **"Continua processando os demais"**: não há teste com múltiplos `Records` no mesmo evento (um corrompido + um válido) — só um registro por evento em cada teste | ⚠️ Spec-precision gap (movimentação para errors/ ✅ testada; continuidade do lote com múltiplos registros no mesmo evento não testada diretamente — código sugere correção via try/except por registro em `handler.py:_handle_record`, mas sem prova empírica) |
| AC8: infra provisionada por script idempotente, sem config manual | 2ª chamada não recria recursos | `backend/tests/integration/test_prescription_infra.py:104-111` — `assert result.created is False` (Lambda e gatilho S3) | ✅ PASS |
| AC9: credenciais via env/profile, `.env.example` documentado | nenhum `boto3.client` direto; vars documentadas | `.env.example:1-30` (ENV, AWS_REGION, LOCALSTACK_ENDPOINT, LAB_ROLE_ARN, DYNAMODB_TABLE etc.); guarda `backend/tests/aws/test_no_direct_boto3_client.py:27-33` varre `backend/` inteiro (inclui `pipelines/prescription/`) | ✅ PASS |
| AC10: precision/recall para "dose fora de faixa" salvos em relatório de métricas | métricas corretas contra ground truth | `backend/tests/prescription/test_prescription_evaluate.py:17-28` — `assert report.precision == 1.0`, `assert report.recall == 1.0`, `assert report.support == sum(...)`. **"Salvos em relatório"**: `common.metrics.save_report` existe (`backend/common/metrics.py:58`) mas **nunca é chamado** por nenhum módulo/CLI de F4 — o padrão equivalente em F3 (`backend/pipelines/vitals/cli.py:19,133`, `evaluate()` → `save_evaluation()`) não tem paralelo em F4 (não existe `pipelines/prescription/cli.py`) | ⚠️ Spec-precision gap (cálculo de métricas ✅ testado; persistência em relatório de arquivo não implementada nem testada) |

### P2: Histórico longitudinal e detecção de mudança abrupta

| Criterion | Spec-defined outcome | `file:line` + assertion | Result |
| --- | --- | --- | --- |
| AC1: registro processado persistido no histórico com chave de dedup, sem duplicar reentrega | `save_record` idempotente | `backend/tests/integration/test_prescription_history.py:71-79` — `assert primeira is True`, `assert segunda is False` | ✅ PASS |
| AC2: nova prescrição compara dose atual com registro anterior mais recente do mesmo medicamento | `get_latest` devolve o mais recente | `backend/tests/integration/test_prescription_history.py:86-94` — `assert latest == recente` (não o mais antigo) | ✅ PASS |
| AC3: variação > 50% → anômalo "mudança abrupta", mesmo com dose na faixa | `AnomalyResult(kind="mudanca_abrupta")` | `backend/tests/prescription/test_rules.py:43-47` — `assert result.kind == "mudanca_abrupta"` (601 vs 400, exatamente >50%); integração: `backend/tests/integration/test_prescription_logic.py:94-105` | ✅ PASS |
| AC4: primeiro registro do paciente/medicamento → pula checagem, sem falso positivo | `kind="normal"` quando `previous=None` | `backend/tests/prescription/test_rules.py:31-33` — `assert result.kind == "normal"` | ✅ PASS |
| Threshold estrito (exatamente 50% não é anômalo) | `kind="normal"` no limite exato | `backend/tests/prescription/test_rules.py:36-40` — `assert result.kind == "normal"` (600 vs 400 = exatamente 50%) | ✅ PASS — **e confirmado pelo sensor de mutação (ver abaixo)**: mutante que trocou `>` por `>=` foi morto exatamente por este teste |

### P3: Alternativa opcional MIMIC-IV (PRESC-15)

| Criterion | Result |
| --- | --- |
| AC1/AC2: adaptador MIMIC-IV opcional, não bloqueante | ✅ **Diferimento explícito e documentado** — `tasks.md` Requirement Traceability: "Diferido (P3, explicitamente não bloqueante) — adaptador MIMIC-IV opcional; sem tarefa nesta rodada"; `spec.md` P3 não recebeu tarefa de execução; AD-022 justifica. Nenhum código tenta simular isso — é uma lacuna **assumida e visível**, não silenciosa. |

**Status**: ❌ Gaps presentes (PRESC-01 AC1 — persistência de ground truth em arquivo) + ⚠️ 3 spec-precision gaps (log CloudWatch, continuidade de lote multi-registro, relatório de métricas persistido)

---

## Edge Cases (spec.md)

- [x] Medicamento fora do catálogo → "sem referência disponível", nunca normal/anômalo por omissão — `backend/tests/prescription/test_rules.py:26-28`, `backend/tests/integration/test_prescription_logic.py:119-125`
- [x] Reentrega do mesmo evento S3 → não duplica no histórico — `backend/tests/integration/test_prescription_history.py:71-79`, `test_prescription_logic.py:108-116` (morto por mutação, ver sensor)
- [x] Duas prescrições quase simultâneas → last-write-wins documentado (política aceita pela spec; não exige lock nem teste de corrida) — decisão de design, não uma lacuna
- [x] Limite de concorrência de Lambda (10) → comportamento nativo da notificação S3 (AWS/LocalStack); não é testável localmente por natureza — aceito por design
- [x] Campo parcialmente vazio (frequência ausente) → "extração incompleta" (`ParseFailure`), excluído do cálculo — garantia estrutural: `evaluate()` só aceita `list[PrescriptionRecord]` (tipo não admite `ParseFailure`); `backend/tests/prescription/test_parser.py:50-57` cobre a sinalização. Não há teste que force um `ParseFailure` end-to-end através de `evaluate()` (desnecessário dado o tipo), mas a alegação "excluído, nunca falso negativo silencioso" depende de o chamador nunca passar falhas de parsing como registros — nenhum código de F4 faz essa integração hoje (ver Gap 1/2, não existe glue code que popule `evaluate()` a partir de execuções reais)

---

## Discrimination Sensor

| # | File:line | Description | Killed? |
| - | --- | --- | --- |
| 1 | `backend/pipelines/prescription/rules.py:48` | `if relative_change > threshold:` → `if relative_change >= threshold:` (limiar de 50% de `check_abrupt_change`) | ✅ Killed — `backend/tests/prescription/test_rules.py::test_variacao_exatamente_no_threshold_nao_e_anomala` falhou (`'mudanca_abrupta' == 'normal'`) |
| 2 | `backend/pipelines/prescription/history.py:44-49` | Removida a `ConditionExpression="attribute_not_exists(dedup_key)"` de `save_record` (idempotência de evento) | ✅ Killed — 2 testes falharam: `test_prescription_history.py::test_save_record_mesmo_dedup_key_nao_duplica` e `test_prescription_logic.py::test_process_evento_duplicado_nao_reprocessa` |
| 3 | `backend/pipelines/prescription/evaluate.py:29-31` | Removido o `if result.kind == "sem_referencia": continue` (exclusão de "sem referência" do cálculo de métricas) | ❌ **Survived** — os 3 testes de `test_prescription_evaluate.py` continuaram verdes. Causa raiz: `test_evaluate_exclui_sem_referencia_do_calculo` usa uma entrada `is_anomalous=False` para o medicamento fora do catálogo; com ou sem a exclusão, essa entrada nunca produz falso positivo/negativo (`support == 0` em ambos os casos), então o teste não discrimina a linha removida. Um teste que discriminasse precisaria de uma entrada com `is_anomalous=True` e medicamento fora do catálogo — aí a exclusão faria `support == 0`, e a ausência dela contaria como falso negativo (`support == 1`, recall < 1) |

**Sensor depth**: lightweight (3 mutações direcionadas, feature não-P0)
**Result**: 2/3 killed — ❌ **1 mutante sobreviveu** (dívida de teste registrada, não bloqueador — ver Fix Plans)

Todas as 3 mutações foram revertidas via `git checkout --` antes de prosseguir; `git status`/`git diff --stat` confirmaram working tree limpa após cada reversão.

---

## Interactive UAT Results

N/A — feature backend/infraestrutura, sem superfície de UI própria nesta fatia (dashboard é F5). Não aplicável conforme regra do `validate.md` ("backend-only ou infraestrutura: checagens automatizadas bastam").

---

## Code Quality

| Principle | Status | Notes |
| --- | --- | --- |
| No features beyond what was asked | ✅ | Escopo de T1-T8 batido com o que foi implementado |
| No abstractions for single-use code | ✅ | — |
| No unnecessary "flexibility" added | ✅ | — |
| Only touched files required for task | ✅ | `95d2c03` toca `aws/clients.py` fora de `pipelines/prescription/`, mas é um fix legítimo e necessário descoberto empiricamente durante T7 (documentado no commit e com teste próprio) |
| Didn't "improve" unrelated code | ✅ | — |
| Matches existing patterns/style | ✅ | Segue o padrão `aws.clients.get_client`, `common.logging`, `common.evidence`, `common.metrics` já usado em F3/aws-foundation |
| Would senior engineer approve? | ⚠️ | Aprovaria a arquitetura; pediria a persistência de ground truth (T2) e o `cli.py`/wiring de fim-a-fim (T8) antes de fechar a feature — ver Gaps |
| Tests map to acceptance criteria and are non-shallow (spot-check T1/T6) | ✅ | `test_rules.py` e `test_prescription_logic.py` afirmam valores exatos (`kind`, `evidence_id is not None`, `deduplicated`), não apenas ausência de exceção |
| Spec-anchored outcome check | ⚠️ | Ver tabela de ACs — 3 spec-precision gaps, 1 gap real (PRESC-01) |
| Per-layer Coverage Expectation met | ✅ | Domínio puro 1:1 com ACs; integração cobre pipeline completo + erro + dedup |
| Every test maps to a spec AC/edge case/Done-when | ✅ | Nenhum teste "solto" sem rastreabilidade encontrado |
| Documented guidelines followed | ✅ | `pyproject.toml`/`ruff.toml` — defaults fortes aplicados (conforme já registrado em `tasks.md`) |

---

## Gate Check

- **Gate command**: `python3 -m pytest -q` (full) + `python3 -m ruff check backend/`
- **Result**: 299 passed, 0 failed, 0 skipped (lint: all checks passed)
- **Test count before feature** (commit `1978b9c`, design doc, imediatamente antes de T1): 254 (verificado via `git worktree add --detach` em commit isolado — 2 falhas nesse baseline são artefatos do worktree temporário sem `.venv` próprio/paths do `Makefile`, não regressões reais; confirmado que os mesmos 2 testes passam normalmente na árvore principal)
- **Test count after feature** (HEAD `c5c9f37`): 299
- **Delta**: +45 (43 novos testes de F4 — 27 unit + 16 integration — + 2 novos testes do fix de fundação `95d2c03`)
- **Skipped tests**: nenhum na execução atual (LocalStack estava de pé); os testes de integração de F4 têm `skipif` condicional a `localhost:4566` responder, com mensagem clara
- **Failures**: nenhuma

---

## Fix Plans (gaps encontrados)

### Fix 1: PRESC-01 AC1 — ground truth não persistido em arquivo separado do PDF

- **Root cause**: `generate_dataset()` devolve o ground truth só em memória (`list[tuple[bytes, GroundTruthEntry]]`); nenhum módulo escreve esse ground truth em disco (JSON/CSV), e não existe um `cli.py`/script de F4 que gere o dataset, suba os PDFs ao S3 e grave o ground truth — ao contrário do padrão já estabelecido por `pipelines/vitals/cli.py`.
- **Fix task**: Adicionar uma função (ou `cli.py` de F4) que, dado o output de `generate_dataset`, grave um arquivo (`ground_truth.json` ou `.csv`) com os `GroundTruthEntry` — separado dos PDFs — e opcionalmente faça upload dos PDFs ao S3 landing bucket.
- **Priority**: Major (AC explícito da spec, não uma nuance de precisão)

### Fix 2: Métricas de "mudança abrupta" e persistência de relatório ausentes (Success Criteria + design.md/tasks.md T8)

- **Root cause**: `evaluate()` só reaplica `check_dose_range`; nunca reaplica `check_abrupt_change` contra o histórico, então não há precision/recall para "mudança abrupta" — apesar de `design.md` ("Precision/recall por tipo de anomalia contra o ground truth") e `tasks.md` T8 Done-when #1 declararem explicitamente os dois tipos, e do Success Criteria global do `spec.md` listar ambos. Além disso, `common.metrics.save_report` nunca é chamado por F4 (nenhum relatório é persistido em arquivo).
- **Fix task**: Estender `evaluate()` (ou adicionar uma segunda chamada) para computar métricas de "mudança abrupta" contra o histórico persistido, e persistir os dois relatórios via `common.metrics.save_report`, com um ponto de entrada (`cli.py`) equivalente ao de `vitals`.
- **Priority**: Major (compromisso explícito em design.md/tasks.md e no Success Criteria global, não cumprido, sem SPEC_DEVIATION documentada)

### Fix 3: Mutante sobrevivente em `evaluate.py` — exclusão de "sem_referencia" não discriminada

- **Root cause**: `test_evaluate_exclui_sem_referencia_do_calculo` usa uma entrada `is_anomalous=False`, que não distingue "excluído do cálculo" de "incluído como verdadeiro negativo" — ambos os casos dão `support == 0`.
- **Fix task**: Adicionar (ou ajustar) o teste para usar uma `GroundTruthEntry(is_anomalous=True, drug="fora-do-catálogo")`; com a exclusão correta, `support` deve permanecer `0` (a entrada nunca entra no cálculo); sem a exclusão, a mesma entrada contaria como falso negativo (`support == 1`, recall cai).
- **Priority**: Minor (dívida de teste, comportamento de produção está correto)

### Fix 4 (spec-precision, não bloqueador): cobertura de teste para logging CloudWatch e continuidade de lote multi-registro

- **Root cause**: `handler.py`/`logic.py` já emitem os logs corretos (`log.info`/`log.warning`/`log.exception`), mas nenhum teste usa `caplog` para afirmar seu conteúdo; e não há teste com múltiplos `Records` no mesmo evento S3 (um corrompido + um válido) para provar empiricamente "não trava o processamento dos demais" (só testado com um registro por evento).
- **Fix task**: (a) Adicionar `caplog` a pelo menos um teste de `handler.py`/`logic.py` afirmando o conteúdo do log; (b) Adicionar um teste de `lambda_handler` com 2 `Records` (um corrompido, um válido) confirmando que ambos são processados e só o corrompido vai para `errors/`.
- **Priority**: Minor (spec-precision gap; a implementação provavelmente já está correta pela estrutura do código, falta só a prova)

---

## Requirement Traceability Update

| Requirement | Previous Status | New Status |
| --- | --- | --- |
| PRESC-01 | Implementing | ❌ Needs Fix (persistência de ground truth em arquivo) |
| PRESC-02 | Implementing | ✅ Verified |
| PRESC-03 | Implementing | ✅ Verified |
| PRESC-04 | Implementing | ✅ Verified |
| PRESC-05 | Implementing | ✅ Verified |
| PRESC-06 | Implementing | ⚠️ Verified com spec-precision gap (log CloudWatch sem asserção) |
| PRESC-07 | Implementing | ⚠️ Verified com spec-precision gap (continuidade multi-registro sem teste direto) |
| PRESC-08 | Implementing | ✅ Verified |
| PRESC-09 | Implementing | ✅ Verified |
| PRESC-10 | Implementing | ⚠️ Verified com spec-precision gap (relatório de métricas não persistido; "mudança abrupta" não avaliada, ver Success Criteria) |
| PRESC-11 | Implementing | ✅ Verified |
| PRESC-12 | Implementing | ✅ Verified |
| PRESC-13 | Implementing | ✅ Verified |
| PRESC-14 | Implementing | ✅ Verified |
| PRESC-15 | Implementing | ✅ Verified (diferimento explícito e documentado, P3 não bloqueante) |

---

## Summary

**Overall**: ⚠️ Issues (não é "Not Ready" — o núcleo do pipeline S3→Lambda→extração→regras→histórico→evidência está sólido e testado ponta a ponta contra LocalStack real; mas há 1 AC explícito não cumprido e 1 compromisso de design/tasks/Success-Criteria não entregue, sem documentação de desvio)

**Spec-anchored check**: 12/15 requisitos com evidência exata batendo o outcome da spec; 1 gap real (PRESC-01); 3 spec-precision gaps (PRESC-06, PRESC-07, PRESC-10)
**Sensor**: 2/3 mutações mortas; 1 sobreviveu (dívida de teste em `evaluate.py`, não bug de produção)
**Gate**: 299 passed, 0 failed; lint limpo; +45 testes líquidos vs. baseline pré-F4 (254)

**What works**: Pipeline ponta a ponta real (upload S3 → Lambda real no LocalStack → extração local via pdfplumber → parser → duas regras de anomalia → histórico DynamoDB com dedup real → evidência salva) comprovado por testes de integração reais, não mocks. Idempotência de infraestrutura (Lambda/gatilho) e de evento (dedup) comprovadas inclusive pelo sensor de mutação. Fix de fundação (`LOCALSTACK_HOSTNAME` fallback) tem teste próprio, não quebrou nenhum teste existente de `aws-foundation`, e foi descoberto exatamente como o design previu ("Achados a verificar durante a implementação").

**Issues found**:
1. PRESC-01 AC1 — ground truth do gerador não é persistido em arquivo separado do PDF (só em memória) — Fix 1
2. Métricas de "mudança abrupta" nunca calculadas nem relatório de métricas persistido em arquivo (design.md/tasks.md/Success Criteria prometem, código não entrega, sem SPEC_DEVIATION) — Fix 2
3. Mutante sobrevivente em `evaluate.py` (exclusão de "sem_referencia" não discriminada pelo teste) — Fix 3
4. Duas lacunas de precisão de teste (log CloudWatch, continuidade de lote multi-registro) — Fix 4

**Next steps**: Rotear Fix 1 e Fix 2 como tarefas de correção (bloqueantes para fechar F4 com Success Criteria pleno); Fix 3 e Fix 4 podem ficar como dívida de teste registrada (mesmo padrão de "3 follow-ups de baixa prioridade" já aceito em aws-foundation/F0), a critério do time.
