# LESSONS — auto-maintained by scripts/lessons.py

> Machine-owned. Do NOT hand-edit. Changes are overwritten on the next `lessons.py` write.
> Canonical state lives in `.specs/lessons.json`. Edit lessons only via the script.
> promote_threshold=2 distinct features · window_days=45 · quarantine_threshold=2

## Confirmed (load these at Specify/Design)

Corroborated across multiple features. Safe to apply as guidance.

_none_

## Candidates (under observation — do NOT load as guidance yet)

Seen once or not yet corroborated. Tracked, not trusted.

### L-001 — Asserir presenca de chave em payload (assert 'campo' in meta) nao prova nada: o campo pode conter qualquer valor. Asserir sempre o valor esperado.
- signal: `surviving_mutant` · recurrence: 1 feature(s) · scope: `tests` · harmful: 0
- features: vitals-anomaly
- evidence: M9,M14,M15 (tests)
- last seen: 2026-07-20T17:27:04Z

### L-002 — Teste que itera uma colecao passa por vacuidade quando ela vem vazia. Asserir que a colecao e nao-vazia antes do laco.
- signal: `surviving_mutant` · recurrence: 1 feature(s) · scope: `tests` · harmful: 0
- features: vitals-anomaly
- evidence: M10 (tests)
- last seen: 2026-07-20T17:27:05Z

### L-003 — Parametro declarado configuravel precisa de teste com dois valores distintos que produzam resultados distintos, senao hardcodear o valor passa despercebido.
- signal: `surviving_mutant` · recurrence: 1 feature(s) · scope: `tests` · harmful: 0
- features: vitals-anomaly
- evidence: M8 (tests)
- last seen: 2026-07-20T17:27:05Z

### L-004 — Todo limiar precisa de teste na fronteira exata, e a spec precisa declarar se a comparacao e estrita ou inclusiva.
- signal: `spec_precision_gap` · recurrence: 1 feature(s) · scope: `spec` · harmful: 0
- features: vitals-anomaly
- evidence: VITALS-03,VITALS-09 (spec)
- last seen: 2026-07-20T17:27:05Z

### L-005 — Modulo com testes proprios mas nao importado por ninguem e codigo morto: verificar integracao real (grep pelo modulo) antes de marcar a tarefa concluida.
- signal: `ac_gap` · recurrence: 1 feature(s) · scope: `process` · harmful: 0
- features: vitals-anomaly
- evidence: VITALS-11 AC2 (process)
- last seen: 2026-07-20T17:27:05Z

### L-006 — Antes de rodar teste de mutacao, commitar o trabalho: 'git checkout -- <arq>' reverte ao ultimo commit e destroi alteracoes nao commitadas.
- signal: `gate_fail` · recurrence: 1 feature(s) · scope: `process` · harmful: 0
- features: vitals-anomaly
- evidence: sensor iteracao 3 (process)
- last seen: 2026-07-20T17:51:47Z

### L-007 — Script de mutacao precisa validar que o padrao casou antes de rodar os testes; sed que nao casa produz falso 'mutante morto' quando os testes falham por outro motivo (ex: ImportError).
- signal: `gate_fail` · recurrence: 1 feature(s) · scope: `process` · harmful: 0
- features: vitals-anomaly
- evidence: M17 falso positivo (process)
- last seen: 2026-07-20T17:51:47Z

### L-008 — Nao asserir a negacao do literal do mutante (score != 0.0): asserir o valor correto. Validar cada conserto com o mutante nomeado E uma variante trivial.
- signal: `surviving_mutant` · recurrence: 1 feature(s) · scope: `tests` · harmful: 0
- features: vitals-anomaly
- evidence: M16,M17 (tests)
- last seen: 2026-07-20T17:51:47Z

### L-009 — Teste de fronteira de float deve usar o valor computado bit a bit como limiar; constante 'equivalente' (math.sqrt(2)) erra por 1 ULP e passa sob > e sob >=.
- signal: `surviving_mutant` · recurrence: 1 feature(s) · scope: `tests` · harmful: 0
- features: vitals-anomaly
- evidence: M12 (tests)
- last seen: 2026-07-20T17:51:47Z

### L-010 — Corrigir apenas o que o relatorio nomeia deixa o caso vizinho descoberto: ao consertar uma lacuna, sondar tambem o call site, o outro canal/campo e o parametro irmao.
- signal: `surviving_mutant` · recurrence: 1 feature(s) · scope: `tests` · harmful: 0
- features: vitals-anomaly
- evidence: V1,V2,N7,V6,V7 (tests)
- last seen: 2026-07-20T18:12:46Z

### L-011 — Teste unitario de uma funcao nao cobre o call site dela: se o valor pode ser corrompido entre produtor e consumidor, e preciso assercao ponta a ponta tambem.
- signal: `surviving_mutant` · recurrence: 1 feature(s) · scope: `tests` · harmful: 0
- features: vitals-anomaly
- evidence: V1 (tests)
- last seen: 2026-07-20T18:12:46Z

### L-012 — Assercao entre dois valores derivados da mesma fonte e tautologica (nome do arquivo vs metadados do mesmo evento): comparar com fonte independente.
- signal: `surviving_mutant` · recurrence: 1 feature(s) · scope: `tests` · harmful: 0
- features: vitals-anomaly
- evidence: V2 (tests)
- last seen: 2026-07-20T18:12:46Z

### L-013 — Teste chamado 'X difere de Y' precisa asserir a != b; sem isso e teste vazio com nome enganoso.
- signal: `surviving_mutant` · recurrence: 1 feature(s) · scope: `tests` · harmful: 0
- features: vitals-anomaly
- evidence: V7 (tests)
- last seen: 2026-07-20T18:12:46Z

### L-014 — Ao remover assercao fraca, substituir por assercao forte no MESMO nivel; remover sem repor reduz a cobertura em vez de melhora-la.
- signal: `gate_fail` · recurrence: 1 feature(s) · scope: `process` · harmful: 0
- features: vitals-anomaly
- evidence: iteracao 3 (process)
- last seen: 2026-07-20T18:12:46Z

### L-015 — Ao consertar um campo de uma string/payload composta, sondar TODOS os outros campos da mesma expressao: o vizinho literal costuma ter a mesma fragilidade.
- signal: `surviving_mutant` · recurrence: 1 feature(s) · scope: `tests` · harmful: 0
- features: vitals-anomaly
- evidence: W9 (tests)
- last seen: 2026-07-20T22:49:18Z

### L-016 — Fixture unica com literais fixos + assercao de substring permite trocar qualquer campo por constante. Verificar por VARIACAO: parametrizar e asserir 'X in A and X not in B'.
- signal: `surviving_mutant` · recurrence: 1 feature(s) · scope: `tests` · harmful: 0
- features: vitals-anomaly
- evidence: W9,W13,W14 (tests)
- last seen: 2026-07-20T22:49:19Z

### L-017 — Oraculo de teste deve ler a mesma config do codigo sob teste; repetir valores que coincidem com os defaults cria concordancia acidental.
- signal: `gate_fail` · recurrence: 1 feature(s) · scope: `tests` · harmful: 0
- features: vitals-anomaly
- evidence: Fix D (tests)
- last seen: 2026-07-20T22:49:19Z

### L-018 — Dicionario de esperados com chave criada incondicionalmente faz conjunto vazio parecer concordancia: so registrar a chave quando ha conteudo.
- signal: `gate_fail` · recurrence: 1 feature(s) · scope: `tests` · harmful: 0
- features: vitals-anomaly
- evidence: Fix D (tests)
- last seen: 2026-07-20T22:49:19Z

### L-019 — Corrigir apenas os vizinhos NOMEADOS no relatorio ainda deixa lacuna: apos cada conserto, enumerar exaustivamente os campos/canais/parametros irmaos e sondar todos.
- signal: `gate_fail` · recurrence: 1 feature(s) · scope: `process` · harmful: 0
- features: vitals-anomaly
- evidence: iteracoes 1-4 (process)
- last seen: 2026-07-20T22:49:19Z

### L-020 — Antes de confiar numa URL de dataset, validar que ela serve o arquivo real (magic bytes / Content-Type application/zip), nao uma pagina de erro 403/HTML com exit 0. Ter um espelho alternativo (Dataverse/Zenodo) para fontes de sites institucionais instaveis.
- signal: `spec_precision_gap` · recurrence: 1 feature(s) · scope: `process` · harmful: 0
- features: data-acquisition
- evidence: ICBHI 403 (process)
- last seen: 2026-07-20T23:55:54Z

### L-021 — Test resume behavior by stubbing the downloader to assert the resume flag is passed, not just that a download succeeds
- signal: `surviving_mutant` · recurrence: 1 feature(s) · scope: `scripts` · harmful: 0
- features: data-acquisition
- evidence: M10/M11 (download_datasets.sh:184,128) (scripts)
- last seen: 2026-07-21T01:30:56Z

### L-022 — When a later backstop can mask an earlier guard, add a test that isolates the guard with input only it rejects
- signal: `surviving_mutant` · recurrence: 1 feature(s) · scope: `scripts` · harmful: 0
- features: data-acquisition
- evidence: M8/M9 (download_datasets.sh:190,134) (scripts)
- last seen: 2026-07-21T01:30:56Z

### L-023 — Sem __init__.py entre subpastas de testes, dois conftest.py disputam o mesmo nome de modulo 'conftest' e um pode sombrear o outro dependendo da ordem de colecao. Manter um unico conftest.py compartilhado na raiz de tests/, nunca um por subpasta.
- signal: `gate_fail` · recurrence: 1 feature(s) · scope: `tests` · harmful: 0
- features: aws-foundation
- evidence: conftest collision (tests)
- last seen: 2026-07-21T16:03:28Z

### L-024 — Teste de erro esperado deve verificar a MENSAGEM/mecanismo especifico (ex: log nomeia a variavel), nao so o codigo de retorno — um erro generico diferente pode produzir o mesmo rc por acidente e mascarar a checagem real sendo removida.
- signal: `surviving_mutant` · recurrence: 1 feature(s) · scope: `tests` · harmful: 0
- features: aws-foundation
- evidence: main() variavel ausente (tests)
- last seen: 2026-07-21T16:49:51Z

### L-025 — Logica de paginacao (list_topics, list_objects, etc.) so e exercitada de verdade com dado suficiente para forcar mais de uma pagina; testar com poucos itens deixa a segunda pagina sem cobertura, e o risco cresce silenciosamente conforme o ambiente real acumula recursos.
- signal: `surviving_mutant` · recurrence: 1 feature(s) · scope: `tests` · harmful: 0
- features: aws-foundation
- evidence: ensure_topic paginacao (tests)
- last seen: 2026-07-21T16:49:51Z

### L-026 — When a spec AC requires ground truth or labels to be written to a separate file, verify a file is actually created on disk — an in-memory return value is not a substitute.
- signal: `ac_gap` · recurrence: 1 feature(s) · scope: `prescription` · harmful: 0
- features: prescription-analysis
- evidence: spec.md PRESC-01 AC1 / backend/pipelines/prescription/generator.py:64-110 (prescription)
- last seen: 2026-07-21T20:14:39Z

### L-027 — When testing that a category is excluded from a metrics calculation, use a ground-truth entry that would change the result if the exclusion were removed, not one that is already a true negative either way.
- signal: `surviving_mutant` · recurrence: 1 feature(s) · scope: `metrics` · harmful: 0
- features: prescription-analysis
- evidence: backend/pipelines/prescription/evaluate.py:29-31 / backend/tests/prescription/test_prescription_evaluate.py:31-65 (metrics)
- last seen: 2026-07-21T20:14:39Z

### L-028 — When design.md or tasks.md commits to evaluating multiple categories/anomaly types, narrowing the implementation to one category without a SPEC_DEVIATION comment leaves an undocumented, undetected scope cut.
- signal: `spec_deviation` · recurrence: 1 feature(s) · scope: `prescription` · harmful: 0
- features: prescription-analysis
- evidence: design.md evaluate.py Purpose vs backend/pipelines/prescription/evaluate.py:15-36 (só dose_fora_de_faixa) (prescription)
- last seen: 2026-07-21T20:14:39Z

### L-029 — When a spec AC requires an observable side effect such as a log statement or a persisted report file, assert its actual content or existence in a test, not just that the code path that produces it ran without raising.
- signal: `spec_precision_gap` · recurrence: 1 feature(s) · scope: `prescription` · harmful: 0
- features: prescription-analysis
- evidence: PRESC-06/PRESC-10 — backend/pipelines/prescription/handler.py:36,41,45-51; backend/pipelines/prescription/evaluate.py (no save_report call) (prescription)
- last seen: 2026-07-21T20:14:48Z

### L-030 — A thin function that only composes/delegates to an already-tested primitive (e.g., loop + call an existing save/persist helper) still needs its own direct test asserting the delegation actually happens for each expected key — glue code is exactly where untested wiring hides even when the underlying primitive is well covered.
- signal: `surviving_mutant` · recurrence: 1 feature(s) · scope: `test-coverage` · harmful: 0
- features: prescription-analysis
- evidence: backend/pipelines/prescription/evaluate.py:65-69 (save_evaluation, no direct test — no-op mutant survived full suite) (test-coverage)
- last seen: 2026-07-21T20:51:09Z

### L-031 — When a spec requires an error/limit to be logged to an observable sink (CloudWatch, audit log), assert the log actually reaches that sink for the failure path, not just that the pipeline continues without propagating the exception.
- signal: `spec_precision_gap` · recurrence: 1 feature(s) · scope: `observability` · harmful: 0
- features: video-analysis
- evidence: VIDEO-10 — backend/tests/integration/test_video_handler.py:102-122 (observability)
- last seen: 2026-07-22T15:32:16Z

### L-032 — When a training call sets a class-imbalance-handling parameter (e.g. class_weight="balanced"), add a test with an imbalanced dataset or that introspects the fitted estimator's params — a balanced synthetic fixture alone cannot detect its removal.
- signal: `surviving_mutant` · recurrence: 1 feature(s) · scope: `backend/pipelines` · harmful: 0
- features: audio-analysis
- evidence: backend/pipelines/audio/icbhi_classifier.py:40-42 (mutant 2 in validation.md) (backend/pipelines)
- last seen: 2026-07-22T22:07:03Z

### L-033 — When an acceptance criterion requires writing an evidence artifact on a threshold-crossing condition computed inside the CLI orchestrator (not the pure domain function), add a test that drives the orchestrator itself past the threshold — unit-testing only the pure scoring function leaves the actual evidence-write branch uncovered.
- signal: `ac_gap` · recurrence: 1 feature(s) · scope: `backend/pipelines` · harmful: 0
- features: audio-analysis
- evidence: P3 AC3 (spec.md) — cli.py:111-131 _salva_evidencia_fadiga, no file:line test citation (backend/pipelines)
- last seen: 2026-07-22T22:07:08Z

### L-034 — Before naming a new test file, check for an existing test file with the same basename anywhere under backend/tests/ — pytest's default import mode has no package markers there, so a duplicate basename breaks full-suite collection even when the narrower per-feature test command passes.
- signal: `gate_fail` · recurrence: 1 feature(s) · scope: `backend/tests` · harmful: 0
- features: audio-analysis
- evidence: make test / pytest -q at repo root — import file mismatch on backend/tests/audio/test_config.py vs backend/tests/common/test_config.py (backend/tests)
- last seen: 2026-07-22T22:07:12Z

### L-035 — When an error-handling pattern (try/except around a batch item) is copied to a second call site by analogy with an already-tested one, add a test for the new call site too — proximity to tested code is not evidence of coverage.
- signal: `ac_gap` · recurrence: 1 feature(s) · scope: `backend/pipelines` · harmful: 0
- features: audio-analysis
- evidence: Edge case AUDIO-12 (spec.md) — cli.py:143-148 consult_audio_paths try/except, no file:line test citation (backend/pipelines)
- last seen: 2026-07-22T22:07:28Z

### L-036 — When testing a hysteresis/threshold state machine, add a dedicated test pinning each exact boundary value (threshold ± band) from each starting state — tests only using far-from-boundary values (e.g. 0.36, 0.9) miss a relaxed-boundary mutation entirely.
- signal: `surviving_mutant` · recurrence: 1 feature(s) · scope: `backend/pipelines/fusion/` · harmful: 0
- features: fusion-and-alerting
- evidence: backend/pipelines/fusion/hysteresis.py:41 (mutant #1) (backend/pipelines/fusion/)
- last seen: 2026-07-23T22:33:38Z

### L-037 — When a route test monkeypatches a helper function entirely to isolate the route logic, also add a separate integration test exercising the real helper against real infra (LocalStack/DB) — otherwise the helper's actual read/query logic has zero coverage even though the route looks fully tested.
- signal: `surviving_mutant` · recurrence: 1 feature(s) · scope: `backend/app/` · harmful: 0
- features: fusion-and-alerting
- evidence: backend/app/routes.py:132 (mutant #4, _is_confirmed) (backend/app/)
- last seen: 2026-07-23T22:33:39Z

## Quarantined (failed when applied — ignore)

A confirmed lesson that recurred alongside failure. Kept for the maintainer to review.

_none_
