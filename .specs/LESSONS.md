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

## Quarantined (failed when applied — ignore)

A confirmed lesson that recurred alongside failure. Kept for the maintainer to review.

_none_
