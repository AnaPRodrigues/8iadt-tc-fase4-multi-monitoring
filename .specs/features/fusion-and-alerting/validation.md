# fusion-and-alerting Validation

**Date**: 2026-07-23
**Spec**: `.specs/features/fusion-and-alerting/spec.md`
**Diff range**: `9dd7d1d~1..cf613d0` (18 commits, T1–T18, full feature)
**Verifier**: standalone fresh-eyes fallback (see note below) — author ≠ reviewer of T1–T15; same
session authored T16–T18, but this validation pass re-derives all evidence from spec.md + the
diff from scratch (no reliance on the authoring session's per-task self-checks).

**Note on methodology**: the runtime available to this session has no tool to spawn an
independent sub-agent process (no `Task`-style dispatch tool exposed). Per
`references/sub-agents.md` § "Standalone fallback", this validation was performed as an
independent fresh-eyes pass by the same agent that authored T16–T18 (T1–T15 were authored by
prior sessions/batches) — re-reading `spec.md` and the full diff from scratch, applying
evidence-or-zero, running the spec-anchored check and the discrimination sensor (mutations in
scratch state, reverted via `git checkout --`, never touching the working tree persistently).
This is weaker than a truly separate author-blind agent for T16–T18 specifically; flagged
explicitly rather than presented as an equivalent guarantee.

**Re-verification addendum (2026-07-23, orchestrator session, commit `6466e46`)**: the 2
surviving mutants below were routed as fix tasks and closed by the orchestrating session (not a
fresh sub-agent — same transparency caveat as above applies). Both fixes were confirmed with
real evidence, not assumed: each original mutation was **reapplied** to the working tree, the
now-added test was run and observed to fail against the mutated code, then the mutation was
reverted via `git checkout --` (working tree confirmed clean via `git status --short` before and
after). See the updated Discrimination Sensor rows below for the exact failure output.

---

## Task Completion

| Task | Status | Notes |
| --- | --- | --- |
| T1 | ✅ Done | `9dd7d1d` — `pipelines/video/cli.py`, real URFD run verified again in this session (`run_id=demo`, `fall-01-fall` evidence) |
| T2 | ✅ Done | `8dbec31` — dataclasses |
| T3 | ✅ Done | `fbaa78e` — config parser |
| T4 | ✅ Done | `a0ec474` — loader.py |
| T5 | ✅ Done | `df174d9` — sort_events/decay |
| T6 | ✅ Done | `bb63c5d` — score_at/compute_timeline |
| T7 | ✅ Done | `78d12bd` — HysteresisClassifier |
| T8 | ✅ Done | `b44e52b` — transitions.py |
| T9 | ✅ Done | `57e122c` — ensure_subscription |
| T10 | ✅ Done | `d2af7c0` — alert.py (SPEC_DEVIATION documented: evidence link is `/evidence/{id}`, not `s3://`, consistent with AD-045) |
| T11 | ✅ Done | `695be6f` — handler.py |
| T12 | ✅ Done | `729d69b` — infra.py |
| T13 | ✅ Done | `7515dd0` — FastAPI skeleton + schemas |
| T14 | ✅ Done | `631a29c` — timeline/analyze routes |
| T15 | ✅ Done | `7019f91` — alerts/evidence routes |
| T16 | ✅ Done | `22a5808` — dashboard timeline + replay |
| T17 | ✅ Done | `86c7f2e` — drill-down + empty-state |
| T18 | ✅ Done | `cf613d0` — curated `demo.yaml`, real evidence for all 4 modalities |

All 18 tasks committed. No blocked/partial tasks.

---

## Spec-Anchored Acceptance Criteria

### P1: Risk score fundido e classificação verde/amarelo/vermelho

| Criterion (WHEN X THEN Y) | Spec-defined outcome | `file:line` + assertion | Result |
| --- | --- | --- | --- |
| AC1 — paciente-demo definido → carrega eventos/anomalias já produzidos por cada feature | Eventos reais resolvidos a partir de `evidence_id`/sidecar real, não fixture sintética | `backend/tests/fusion/test_fusion_loader.py:46-65` — `assert falhas == []; assert evento.evidence.evidence_id == "p7-paracetamol-..."`; e `backend/tests/fusion/test_fusion_loader.py:116-127` — `assert len(events) == 4; assert {e.modality for e in events} == {"video","audio","vitals","prescription"}` contra o `demo.yaml` real | ✅ PASS |
| AC2 — eventos fora de ordem cronológica → reordenados por timestamp antes do risk score | Lista reordenada por `demo_timestamp_s` crescente | `backend/tests/fusion/test_risk_engine.py:47-58` — `assert [e.demo_timestamp_s for e in ordenado] == [5.0, 10.0, 20.0, 30.0]` | ✅ PASS |
| AC3 — risk score por janela → combina sinais com pesos configuráveis + decaimento temporal | `score = Σ peso·severidade·decay(Δt)` | `backend/tests/fusion/test_risk_engine.py:99-113` — `assert ponto.contributions["video"] == pytest.approx(0.4*1.0*decay(200.0,600.0))` | ✅ PASS |
| AC4 — modalidade sem dado na janela → calcula com sinais disponíveis, marca ausência explícita, nunca risco zero silencioso | `missing_modalities` contém a modalidade; `contributions` não tem a chave (distinto de 0.0) | `backend/tests/fusion/test_risk_engine.py:131-141` — `assert ponto.missing_modalities == ["audio","vitals","prescription"]; assert "audio" not in ponto.contributions` | ✅ PASS |
| AC5 — score cruza limiares → classifica verde/amarelo/vermelho com histerese | Nível muda só ao cruzar `limiar ± histerese`; sequência conhecida bate com cálculo manual | `backend/tests/fusion/test_hysteresis.py:72-88` — `assert niveis == ["verde","amarelo","amarelo","amarelo","vermelho","amarelo","verde"]` | ✅ PASS (mas ver Sensor — mutante sobrevivente na fronteira VERDE→VERMELHO) |
| AC6 — nível muda → registra transição (nível anterior, novo, sinais contribuintes, timestamp) | `Transition{t, previous_level, new_level, point.contributions}` | `backend/tests/fusion/test_transitions.py:25-33` — `assert transicao.previous_level=="amarelo"; assert transicao.point.contributions == {"video":0.5,"vitals":0.3}` | ✅ PASS |

### P2: Alerta explicável via SNS

| Criterion | Spec-defined outcome | `file:line` + assertion | Result |
| --- | --- | --- | --- |
| AC1 — nível de disparo atingido → Lambda publica no SNS payload explicável (ID, nível, sinais com links) | Mensagem SNS contém patient_demo_id + nível; payload tem `(modalidade, resumo, link)` por evento | `backend/tests/fusion/test_alert.py:73-87` — `assert payload.contributions == [("video","queda detectada","/evidence/fall-01"), ...]`; `backend/tests/integration/test_fusion_handler.py:111-121` (LocalStack real) — `assert "demo-1" in mensagens[0]; assert "vermelho" in mensagens[0]` | ✅ PASS. SPEC_DEVIATION documentado: link é `/evidence/{id}` (API própria), não `s3://` — evidência do paciente-demo nunca é upada ao S3 (AD-045); registrado no docstring de `alert.py::build_payload`. |
| AC2 — mesmo evento de origem já motivou alerta → evita duplicar (dedupe por evento de origem) | Segunda tentativa com mesmo `dedup_key` não publica de novo | `backend/tests/integration/test_fusion_handler.py:124-133` — `assert segunda.get("deduped") is True; assert len(mensagens) == 1` | ✅ PASS |
| AC3 — envio SNS falha → registra falha (CloudWatch) e sinaliza "não confirmado" no dashboard | `published: False`; dedupe NÃO gravado; API expõe `confirmed: False` | `backend/tests/integration/test_fusion_handler.py:136-159` — `assert resposta_com_falha["published"] is False; assert _dynamo_tem_item(...) is False`; `backend/tests/app/test_routes.py:174-186` — `assert alertas[0]["confirmed"] is False` | ⚠️ PASS com gap no sensor — ver Discrimination Sensor (mutante sobrevivente em `_is_confirmed`) |

### P3: Dashboard Streamlit com timeline unificada e replay

| Criterion | Spec-defined outcome | Evidence | Result |
| --- | --- | --- | --- |
| AC1 — dashboard aberto → timeline unificada (4 modalidades, risk score, nível) | Timeline renderizada a partir de 1 chamada HTTP | `frontend/app.py` (`_render_score_chart`, `_render_events_table`) + verificação manual nesta sessão: `AppTest` headless contra `demo.yaml` real — `drilldown options` mostrou os 4 eventos das 4 modalidades, `n_points=17`, zero exceções (`at.exception == ElementList()`); processo real (`streamlit run` + `curl -sf localhost:8501`) confirmado sem traceback no log | ⚠️ Verificado sem harness automatizado (Test Coverage Matrix classifica esta camada como "none — manual"); AppTest headless é uma verificação real de execução do script (não visual), mas não substitui inspeção visual no navegador — **pendente para revisão humana** |
| AC2 — replay acionado → reproduz timeline em modo controlado, sem esperar duração real | Nenhuma nova chamada HTTP por passo do replay | Verificado nesta sessão: log do `uvicorn` mostrou 1 única `GET /patients/smoke-test/timeline` para toda a sessão de `AppTest`, incluindo o clique no botão "▶" de replay — nenhuma segunda chamada | ⚠️ Mesma ressalva de AC1 (manual/AppTest, não visual) |
| AC3 — evento selecionado → exibe evidência correspondente (frame/transcript/gráfico/prescrição) | Artefato renderizado por tipo | Verificado nesta sessão: `AppTest` percorreu os 4 eventos reais do `demo.yaml` (`video`→PNG/imagem, `vitals`→PNG/imagem, `prescription`→PDF/download, `audio`→PNG/imagem), zero exceções em cada seleção | ⚠️ Mesma ressalva — manual/AppTest, não visual |

### Edge Cases

| Edge case | Spec-defined outcome | `file:line` + assertion | Result |
| --- | --- | --- | --- |
| Nenhuma modalidade com evento novo na janela → mantém último nível conhecido | Nível não reseta para verde por ausência de sinal novo | `backend/tests/fusion/test_hysteresis.py:61-69` — `assert c.update(0.7) == "vermelho"; assert c.update(0.66) == "vermelho"` | ✅ PASS |
| Score oscila perto do limiar → histerese evita alertas repetidos | Nível não oscila dentro da banda `±hysteresis` | `backend/tests/fusion/test_hysteresis.py:51-58` — `assert niveis == ["amarelo"] * 6` | ✅ PASS |
| Paciente-demo sem os 4 registros vinculados → roda com as disponíveis, sinaliza ausência | `missing_modalities` correto desde `t=0`; dashboard sinaliza modalidades ausentes | `backend/tests/fusion/test_risk_engine.py:170-180` — `assert "video" in pontos[0].missing_modalities; assert all("video" in p.missing_modalities for p in pontos)`; `frontend/app.py` renderiza `st.caption` com `missing_modalities` do ponto corrente | ✅ PASS (domínio); manual (frontend) |
| Dashboard sem paciente-demo configurado → mensagem clara, nunca tela vazia | Mensagem explicando configuração pendente | Verificado nesta sessão via `AppTest`: `at.info[0].value` contém `"Nenhum paciente-demo configurado para 'demo'."` + caminho do YAML esperado; zero exceções | ⚠️ Manual/AppTest, não visual — comportamento de código confirmado, inspeção visual real pendente |

**Status**: ✅ Todos os ACs mapeados com evidência (nenhum spec-precision gap encontrado — a spec define outcomes precisos e os testes os atingem). Duas ressalvas: (a) camada de frontend não tem harness automatizado por design do projeto (Test Coverage Matrix já classifica como manual) — verificado por execução real do processo + `AppTest` headless nesta sessão, não por inspeção visual; (b) o discrimination sensor encontrou 2 mutantes sobreviventes (ver abaixo) que apontam gaps de precisão em AC5 e AC3-P2.

---

## Discrimination Sensor

| # | File:line | Description | Killed? |
| --- | --- | --- | --- |
| 1 | `backend/pipelines/fusion/hysteresis.py:41` | Fronteira VERDE→VERMELHO relaxada: `score > threshold_vermelho + hysteresis` → `score > threshold_vermelho - hysteresis` (0.75 → 0.65) | ✅ **Killed (re-teste 2026-07-23, commit `6466e46`)** — novo teste `test_verde_para_vermelho_respeita_a_fronteira_exata_da_banda_do_limiar_vermelho` (`test_hysteresis.py`) falha com a mutação reaplicada (`assert 'vermelho' == 'amarelo'`); mutação revertida via `git checkout --` logo em seguida, árvore confirmada limpa. |
| 2 | `backend/pipelines/fusion/risk_engine.py:58` | Decaimento removido: `weight * event.severity * decay(elapsed, half_life_s)` → `weight * event.severity * 1.0` | ✅ Killed — `test_score_at_soma_peso_severidade_decay...` e `test_score_at_usa_o_evento_mais_recente...` falharam (2/14 testes de `test_risk_engine.py`) |
| 3 | `backend/pipelines/fusion/alert.py:16` | Ordenação removida do `dedup_key`: `sorted(...)` → `[...]` (lista não ordenada) | ✅ Killed — `test_dedup_key_mesmo_conjunto_em_ordem_diferente_gera_a_mesma_chave` falhou (1/6 testes de `test_alert.py`) |
| 4 | `backend/app/routes.py:132` | `_is_confirmed` sempre devolve `True` após a consulta real ao DynamoDB (ignora a resposta) | ✅ **Killed (re-teste 2026-07-23, commit `6466e46`)** — novo teste de integração `test_is_confirmed_le_o_item_real_do_dynamodb_gravado_pelo_handler` (`test_fusion_handler.py`, LocalStack real) falha com a mutação reaplicada (`assert _is_confirmed(dedup_key) is False` antes do handler gravar o item falha, pois a mutação devolve `True` mesmo sem item); mutação revertida via `git checkout --`, árvore confirmada limpa. |

**Sensor depth**: lightweight (4 mutations, dentro da faixa 1-3 recomendada para o tier default — estendida em 1 para cobrir a camada de API além do domínio puro)
**Result**: 4/4 killed (2 originalmente, 2 no re-teste após fix) → ✅ **PASS**

All mutations applied and reverted via `git checkout --` in the same session; `git status --short backend/` confirmed clean before and after each mutation. The real working tree was never left in a mutated state.

---

## Code Quality

| Principle | Status |
| --- | --- |
| Minimum code | ✅ |
| Surgical changes | ✅ — T16-T18 touched only `frontend/app.py`, `backend/pipelines/fusion/configs/demo.yaml`, `backend/tests/fusion/test_fusion_loader.py` |
| No scope creep | ✅ |
| Matches existing patterns | ✅ — frontend uses only HTTP (`requests`), no direct backend import (AD-044); config.py/loader.py precedent followed for demo.yaml curation |
| Spec-anchored outcome check (asserted values match spec-defined outcome) | ✅ (see AC tables above) |
| Per-layer Coverage Expectation met | ⚠️ Domain layer (`fusion/*`) mostly 1:1, but 1 boundary gap found (hysteresis mutant #1); API layer has a real-path gap (`_is_confirmed` mutant #4) |
| Every test maps to a spec requirement — no unclaimed tests | ✅ — reverse-checked test names against FUSION-NN/AC/Done-when, nenhum teste órfão encontrado |
| Documented guidelines followed | "none — strong defaults applied" per `tasks.md` Test Coverage Matrix (no `AGENTS.md`/`CLAUDE.md` testing guideline in repo) |

---

## Edge Cases

- [x] Nenhuma modalidade com evento novo → mantém último nível: handled correctly
- [x] Oscilação perto do limiar → histerese evita alertas repetidos: handled correctly (mas ver sensor mutante #1 para a fronteira VERDE→VERMELHO especificamente)
- [x] Paciente-demo sem os 4 registros: handled correctly
- [x] Dashboard sem paciente-demo configurado: handled correctly (verificado via AppTest, não visualmente)

---

## Gate Check

- **Gate command**: `make test-unit` (T18's own Done-when) + `make localstack-up && make test && make lint` (fechamento de feature, Phase 6/última tarefa)
- **Result (após fix, commit `6466e46`)**: `make test-unit` → 396 passed, 0 failed. `make test` (suite completa, incl. `-m integration` contra LocalStack real) → 489 passed, 0 failed. `make lint` → clean.
- **Test count before feature** (baseline, pre-`9dd7d1d`): not independently re-measured (out of scope of this diff range) — the diff range itself adds 27 files, ~2946 insertions, including 12 new/expanded test files.
- **Test count after feature**: 489 (full suite, includes the 2 fix-task tests)
- **Skipped tests**: none observed in either run (all fixtures/datasets present locally: URFD, ICBHI, CTU-UHB, `output/prescription/2026072*`)
- **Failures**: none

---

## Fix Plans

### Fix 1: `hysteresis.py` VERDE→VERMELHO boundary untested at the exact threshold

- **Root cause**: `test_hysteresis.py` never calls `.update(score)` with a score in `(threshold_vermelho - hysteresis, threshold_vermelho + hysteresis]` (i.e., `(0.65, 0.75]`) while the classifier starts at `VERDE`. Existing tests only probe values far from this specific boundary (0.36, 0.9, or sequences that skip this exact range from VERDE), so a mutation that relaxes the rising threshold by `2×hysteresis` goes undetected.
- **Fix task**: Add a test asserting `HysteresisClassifier(...).update(0.70) == "amarelo"` (not `"vermelho"`) starting from VERDE — pins the exact upper boundary (`threshold_vermelho + hysteresis = 0.75`) the same way `test_classifica_amarelo_quando_score_cruza_o_limiar_amarelo_mais_a_histerese` already pins the amarelo boundary.
- **Priority**: Minor (production code is correct — confirmed by reading `hysteresis.py:41`; this is a test-coverage precision gap, not a live bug)

### Fix 2: `app/routes.py::_is_confirmed` real DynamoDB read path untested

- **Root cause**: Every `test_routes.py` test involving `confirmed` either monkeypatches `_is_confirmed` entirely (bypassing the real `client.get_item(...)` call) or hits the earlier `if not table_name` guard. The actual "read the real dedupe item from DynamoDB and report True/False" logic (FUSION-09's dashboard-facing half) has zero test coverage — including on the happy path where `DYNAMODB_TABLE` is set and the item genuinely does/doesn't exist.
- **Fix task**: Add an integration test (LocalStack, matching the `test_fusion_handler.py`/`test_provision_subscription.py` pattern: `pytest.mark.integration`, skip if `:4566` unavailable) that sets `DYNAMODB_TABLE` to a real table, writes an `ALERT#<key>` item directly via `boto3`, and asserts `_is_confirmed(key) is True`; and a companion asserting `_is_confirmed("chave-inexistente") is False` against the same real table (item genuinely absent, not just table unset).
- **Priority**: Major (this is the read-side of FUSION-09's explicit "sinalizar no dashboard que o alerta não foi confirmado como enviado" requirement — currently unverified against real infrastructure)

---

## Requirement Traceability Update

| Requirement | Previous Status | New Status |
| --- | --- | --- |
| FUSION-01 | Implementing | ✅ Verified |
| FUSION-02 | Implementing | ✅ Verified |
| FUSION-03 | Implementing | ✅ Verified |
| FUSION-04 | Implementing | ✅ Verified |
| FUSION-05 | Implementing | ✅ Verified (Fix 1 aplicado e re-testado, commit `6466e46`) |
| FUSION-06 | Implementing | ✅ Verified |
| FUSION-07 | Implementing | ✅ Verified |
| FUSION-08 | Implementing | ✅ Verified |
| FUSION-09 | Implementing | ✅ Verified (Fix 2 aplicado e re-testado, commit `6466e46`) |
| FUSION-10 | Implementing | ⚠️ Verified (manual/AppTest only — visual inspection pending) |
| FUSION-11 | Implementing | ⚠️ Verified (manual/AppTest only — visual inspection pending) |
| FUSION-12 | Implementing | ⚠️ Verified (manual/AppTest only — visual inspection pending) |
| FUSION-13 | Implementing | ✅ Verified |
| FUSION-14 | Implementing | ✅ Verified |

---

## Summary

**Overall**: ✅ PASS (após fix — ambos os gaps do sensor de discriminação corrigidos e re-verificados com evidência real de mutação morta, commit `6466e46`)

**Spec-anchored check**: 16/16 criteria (P1×6, P2×3, P3×3, edge cases×4) traced to evidence, 0 spec-precision gaps (spec.md defines precise outcomes throughout; all matched)
**Sensor**: 4/4 mutations killed (2 on first pass, 2 more after the fix)
**Gate**: 489 passed, 0 failed (`make test`); `make lint` clean

**What works**: The entire fusion engine (loader → risk_engine → hysteresis → transitions → alert → handler), the AWS integration (SNS/DynamoDB via LocalStack, real publish+dedupe+failure-handling verified), the API (4 routes, happy+edge+404 paths), and the dashboard (real end-to-end run against the curated `demo.yaml` with real evidence from all 4 modalities: URFD fall, CTU-UHB FHR anomaly, prescription dose-change, ICBHI wheeze) — all verified against real data, not fixtures, per AD-045a.

**Issues found (both fixed)**:
1. ~~`hysteresis.py` VERDE→VERMELHO exact boundary (0.75) has no dedicated test~~ — **Fixed**: `test_verde_para_vermelho_respeita_a_fronteira_exata_da_banda_do_limiar_vermelho` added, confirmed to kill the original mutation on re-test.
2. ~~`app/routes.py::_is_confirmed` real DynamoDB read path has zero coverage~~ — **Fixed**: `test_is_confirmed_le_o_item_real_do_dynamodb_gravado_pelo_handler` added (LocalStack real), confirmed to kill the original mutation on re-test.
3. (Not a sensor finding, still open) Dashboard (T16/T17) has no automated visual verification available in this environment — `AppTest` headless execution + real-process `curl` checks confirm zero Python exceptions across the full narrative (all 4 drill-down evidence types, replay to the end, empty-state message), but true browser-rendered visual correctness (layout, colors, chart legibility) was not and could not be inspected in any session so far.

**Next steps**: Fix→re-verify loop closed in 1 iteration (both gaps resolved together, commit `6466e46`) — feature is done per process. Remaining open item, not a blocker: a human reviewer should do a real-browser pass of `frontend/app.py` before the demo video recording, given the tooling limitation noted above (issue 3).
