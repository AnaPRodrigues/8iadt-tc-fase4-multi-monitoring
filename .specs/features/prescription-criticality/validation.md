# Prescription Criticality — Validation

**Date**: 2026-07-28
**Spec**: `.specs/features/prescription-criticality/spec.md`
**Diff range**: `924ca7b..c87a7b6` (main implementation + test commit)
**Verifier**: independent sub-agent (author != verifier) — evidence-or-zero, cobertura re-derivada da spec

**Verdict**: ✅ **PASS** — prescription-criticality pode ser fechada. 12/12 ACs em escopo com desfecho da spec asserido. Gate limpo (65/65). Sensor: **3 mutações, 3 mortas, 0 sobreviventes** — todos os testes discriminam corretamente o comportamento que a spec define.

---

## Spec-Anchored Outcome Check

| Criterion | Spec-defined outcome | `file:line` + assertion | Result |
| --- | --- | --- | --- |
| PRESC-10: `lookup("dipirona")` → criticality=1 | `criticality == 1` | `test_catalog.py:101` — `assert entry.criticality == 1` (no loop de `test_medicamento_risco_baixo_tem_criticality_1`) | ✅ |
| PRESC-10: `lookup("tramadol")` → criticality=2 | `criticality == 2` | `test_catalog.py:109` — `assert entry.criticality == 2` (no loop de `test_medicamento_risco_medio_tem_criticality_2`) | ✅ |
| PRESC-10: `lookup("morfina")` → criticality=3 | `criticality == 3` | `test_catalog.py:117` — `assert entry.criticality == 3` (no loop de `test_medicamento_alta_vigilancia_tem_criticality_3`) | ✅ |
| PRESC-10: `lookup("fentanil")` → criticality=3 | `criticality == 3` | `test_catalog.py:117` — mesmo teste, fentanil incluso no loop `("morfina", "fentanil", "metadona")` | ✅ |
| PRESC-11: dipirona(1) → morfina(3) = substituicao_critica | `kind == "substituicao_critica"` | `test_rules.py:102` — `assert result.kind == "substituicao_critica"` | ✅ |
| PRESC-11: morfina(3) → fentanil(3) = normal | `kind == "normal"` | `test_rules.py:129` — `assert result.kind == "normal"` | ✅ |
| PRESC-11: previous=None → normal | `kind == "normal"` | `test_rules.py:143` — `assert result.kind == "normal"` | ✅ |
| PRESC-11: mesmo fármaco → normal | `kind == "normal"` | `test_rules.py:137` — `assert result.kind == "normal"` | ✅ |
| PRESC-11: fármaco fora catálogo → sem_referencia | `kind == "sem_referencia"` | `test_rules.py:151` — `assert result.kind == "sem_referencia"` | ✅ |
| PRESC-12: dose_fora_de_faixa E substituicao_critica → dose primeiro | dose_fora_de_faixa primeiro na lista | `test_rules.py:180-182` — `kinds[0] == "dose_fora_de_faixa"`, `"substituicao_critica" in kinds` | ✅ |
| PRESC-12: não há anomalias → kind=normal | todos os resultados `kind == "normal"` | `test_rules.py:197-199` — `for r in results: assert r.kind == "normal"` | ✅ |
| PRESC-13: make test passa | todos os testes existentes passam | Gate check: 65 passed, 0 failed | ✅ |

**Status: 12/12 ✅** — todos os ACs com desfecho da spec asserido. Nenhum GAP.

---

## Gate Check

- **Comando**: `source .venv/bin/activate && cd backend && python -m pytest tests/prescription/ -v --tb=short`
- **Collection**: 65 items
- **Passed**: 65
- **Failed**: 0
- **Skipped**: 0
- **Tempo**: 2.25 s

Resultado: **65 passed, 0 failed, 0 skipped**. PRESC-13 confirmado.

Re-execução pós-sensor: idêntica (65 passed, 0 failed) — árvore restaurada corretamente.

---

## Discrimination Sensor

**Profundidade**: P0-core — 3 mutações, uma por AC (PRESC-10, PRESC-11, PRESC-12). Protocolo: backup do arquivo, aplica mutação, roda teste(s) relevante(s), restaura. Confirmação de que `git diff --numstat` não vazio antes de cada execução.

| # | Arquivo:linha | Mutação | Teste alvo | Killed? |
| --- | --- | --- | --- | --- |
| M1 (PRESC-11) | `rules.py:151` | `delta >= 2` → `delta > 2` | `test_substituicao_salto_2_niveis_deteta_critica` | ✅ **Morto** — `assert 'normal' == 'substituicao_critica'` |
| M2 (PRESC-12) | `rules.py:193-199` | `check_high_risk_substitution` antes de `check_dose_range` | `test_evaluate_prescription_dose_fora_de_faixa_primeiro_que_substituicao` | ✅ **Morto** — `kinds[0]` era `'substituicao_critica'`, esperado `'dose_fora_de_faixa'` |
| M3 (PRESC-10) | `catalog.py:80` | `morfina.criticality = 3` → `1` | `test_medicamento_alta_vigilancia_tem_criticality_3` | ✅ **Morto** — `assert 1 == 3` |

**Resultado**: **3/3 mortos, 0 sobreviventes.** Todos os testes discriminam corretamente o comportamento definido na spec.

Árvore após o sensor: `git status --short` vazio (apenas ficheiros `.specs/` untracked, nenhuma alteração a ficheiros de código).

---

## Code Quality Check

| Princípio | Status |
| --- | --- |
| Código mínimo, sem features além do pedido | ✅ — `criticality` só é adicionado a `DrugRange`, `catalog` e `rules`; nenhum arquivo alheio tocado |
| Sem abstrações para uso único | ✅ — `_criticality_label` é helper local de uma função, apropriado |
| Sem "flexibilidade" desnecessária | ✅ — parâmetros com defaults sensíveis |
| Só tocou arquivos exigidos | ✅ — `models.py`, `catalog.py`, `rules.py`, `logic.py`, `test_catalog.py`, `test_rules.py` |
| Não "melhorou" código não relacionado | ✅ |
| Segue padrões/estilo existentes | ✅ — mesmo padrão de `_d()` factory, mesmas convenções de nomenclatura de teste |
| Um engenheiro sénior aprovaria? | ✅ — implementação direta, sem over-engineering; testes com cobertura de bordas (fármaco anterior fora do catálogo, salto exato de 2 níveis) |
| Testes mapeiam ACs e não são rasos | ✅ — cada AC tem teste(s) correspondente(s); testes incluem asserção de `reason` text e verificação de ordem na lista |
| Spec-anchored: valor asserido = desfecho da spec | ✅ — 12/12 ACs com desfecho asserido, sem lacunas |
| Presença de código morto ou redundante leve | ⚠️ — `_lookup_with_range` devolve `DrugRange` que `check_dose_range` descarta com `_`. A função adicional `regulatory_info` faz a mesma lookup. Não é bug nem violação de spec — apenas redundância menor. O `criticality` retornado em `regulatory_info` (\:106) é um bónus não pedido pela spec mas coerente. Risco: nenhum. |

---

## Requirement Traceability

Todos os ACs PRESC-10 a PRESC-13 estão cobertos e verificados. A implementação integra-se corretamente no pipeline existente:

- `logic.py:117` chama `evaluate_prescription(parsed, previous_record)` com o histórico do paciente, o que permite `check_high_risk_substitution` funcionar.
- `logic.py:118` filtra apenas anômalos (`kind != "normal"`), preservando o contrato de `ProcessResult`.
- A ordem de gravidade clínica (dose > substituição > abrupta) é respeitada tanto em `rules.py:evaluate_prescription` como documentada em `logic.py:113-116`.

Não há ACs descopados ou fora de escopo.

---

## Summary

**Overall**: ✅ **PASS**

**Spec-anchored check**: **12/12** ACs em escopo com desfecho da spec asserido. Nenhum GAP.

**Gate**: **65 passed, 0 failed, 0 skipped** — baseline confirmada.

**Sensor**: **3/3 mortos, 0 sobreviventes** — todas as mutações detectadas pelos testes relevantes:
- `delta >= 2` → `> 2` morto pelo teste de substituição crítica (PRESC-11)
- Ordem de regras trocada morta pelo teste de prioridade de dose (PRESC-12)
- criticality errado morto pelo teste de MAV (PRESC-10)

**Qualidade**: Implementação limpa, testes cobrem bordas (fármaco anterior fora do catálogo, salto de exatamente 2 níveis), integração com `logic.py` correcta. Uma redundância menor (`_lookup_with_range` vs `check_dose_range`) identificada — sem impacto na correção.
