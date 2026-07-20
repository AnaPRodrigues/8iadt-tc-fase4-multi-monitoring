# F3 — Vitals Anomaly Validation

**Date**: 2026-07-20
**Spec**: `.specs/features/vitals-anomaly/spec.md`
**Diff range**: `480da5e..2f17d14` (branch `feat/f3-vitals-anomaly`)
**Verifier**: independent sub-agent (author ≠ verifier) — evidence-or-zero, cobertura re-derivada da spec
**Iteração**: 2 de no máximo 3

**Veredito**: ❌ **FAIL** — 9/12 ACs em escopo com desfecho da spec asserido, 3 lacunas. Gate limpo (143/143). Sensor: 15 mutações, **11 mortas, 4 sobreviventes**.

Progresso real desde a iteração 1: 5 dos 6 mutantes sobreviventes agora morrem e o rebaixamento de VITALS-11 AC2 está formalmente registrado. Mas **duas das correções são cosméticas** — foram calibradas para matar exatamente o mutante nomeado no relatório anterior, sem fortalecer a verificação — e uma área não sondada antes revelou uma lacuna nova.

---

## Histórico — Iteração 1 (resumo)

FAIL. 15 mutações, 9 mortas, 6 sobreviventes: **M7** (fronteira `max_invalid_fraction`), **M8** (`contamination` hardcoded), **M9** (`ph`→`None` no payload), **M12** (fronteira do z-score), **M14** (`score`→`0.0`), **M15** (`detector`→`"desconhecido"`). Além disso: teste vacuoso em `test_toda_evidencia_tem_artefato_e_sidecar` (passava com zero evidências, comprovado por M10), `load_mitbih_dataset` sem teste, e VITALS-11 AC2 não implementado (módulo `mitbih.py` desconectado do pipeline). Sete Fix Plans emitidos.

---

## Verificação das correções alegadas (commit `2f17d14`)

O commit toca **apenas testes e specs** — nenhuma linha de `src/` mudou. Correto: as lacunas eram de verificação, não de implementação (salvo VITALS-11 AC2, resolvido por rebaixamento).

| # | Alegação do autor | Verificado? | Evidência |
| --- | --- | --- | --- |
| 1 | Asserções de VALOR no payload (ph, detector, score, record_id) | ⚠️ **Parcialmente** | `tests/integration/test_vitals_pipeline.py:68,70,71` — `meta["ph"] == 7.01`, `meta["record_id"] == "0001"`, `meta["source_record_id"] == "0001"` são asserções de valor genuínas. **`:69` e `:73` não são** — ver seção "Força das novas asserções" |
| 2 | Guarda contra vacuidade | ✅ **Sim** | `tests/integration/test_vitals_pipeline.py:58` — `assert sidecars, "o cenário deve produzir ao menos uma evidência"`. M10 confirmado morto por este teste |
| 3 | `contamination` coberto com dois valores distintos | ✅ **Sim** | `tests/vitals/test_detectors_iforest.py:54-61` — `IsolationForestDetector(contamination=0.05)` vs `0.4`, `assert sum(1 for f in muitas if f) > sum(1 for f in poucas if f)`. M8 morre por este teste |
| 4 | `load_mitbih_dataset` coberto (ausente, lote, ilegível) | ✅ **Sim** | `tests/vitals/test_mitbih.py:80-101` — `load_mitbih_dataset(tmp_path / "nao-existe") == []`; `sorted(r.record_id …) == ["100","101"]`; `[r.record_id …] == ["100"]` com `.atr` corrompido no lote |
| 5a | Fronteira exata de `max_invalid_fraction` | ✅ **Sim** | `tests/vitals/test_windowing.py:82-90` — máscara com exatamente 50% inválido, `max_invalid_fraction=0.5`, `assert janelas[0].insufficient_data is False`. M7 morre |
| 5b | Fronteira exata do z-score | ❌ **NÃO** | `tests/vitals/test_detectors_zscore.py:72-80` — o teste **não atinge a fronteira**. M12 continua sobrevivendo. Ver análise abaixo |
| 6 | VITALS-11 AC2 rebaixado por AD-028 | ✅ **Sim** | `.specs/STATE.md:221-227` — AD-028, `**Status**: active`, escopo "F3, user story P3. Rebaixa VITALS-11 AC2; AC1 e AC3 permanecem válidos". Refletido em `.specs/features/vitals-anomaly/spec.md:126` com `~~strikethrough~~` + "REBAIXADO por AD-028" |

### 5b — por que o teste de fronteira do z-score não funciona

`tests/vitals/test_detectors_zscore.py:72-80` declara "desvio de 2 bpm / sqrt(2) = sqrt(2), exatamente o limiar". A aritmética de ponto flutuante discorda:

```
score     = 1.414213562373095    (abs(142.0 - 140.0) / desvio)
threshold = 1.4142135623730951   (math.sqrt(2))
delta     = -2.22e-16            → score é 1 ULP ABAIXO do limiar
s >  t  ->  False
s >= t  ->  False
```

O score cai **abaixo** do limiar, então `flag is False` é verdadeiro sob `>` **e** sob `>=`. O teste não discrimina as duas semânticas. O `pytest.approx` na linha 79 mascara exatamente a diferença que decide o comportamento — `approx` afirma que os valores são próximos, e o código sob teste exige que sejam **iguais**.

Contraste com o teste de `max_invalid_fraction` (`test_windowing.py:82-90`), que funciona: lá a fração vem de `np.mean` sobre 4 de 8 booleanos, produzindo `0.5` exato e representável, que colide de fato com o limiar. A técnica correta existe no repositório; só não foi aplicada ao z-score.

---

## Força das novas asserções de payload (item 3 do escopo desta iteração)

As duas asserções questionadas **são fracas disfarçadas**. Sondei cada uma com uma mutação que o relatório anterior não havia nomeado:

| Asserção | `arquivo:linha` | Mata o mutante nomeado na iteração 1? | Mata uma variante trivial? |
| --- | --- | --- | --- |
| `assert meta["score"] != 0.0` | `tests/integration/test_vitals_pipeline.py:73` | ✅ M14 (`score=0.0`) morre | ❌ **M16** (`score=99.0`) **SOBREVIVEU** |
| `assert meta["detector"] in {"zscore", "isolation_forest"}` | `tests/integration/test_vitals_pipeline.py:69` | ✅ M15 (`detector="desconhecido"`) morre | ❌ **M17** (`detector="zscore"` sempre) **SOBREVIVEU** |

**`score != 0.0`** não é uma asserção de valor: é a negação do literal que o relatório anterior usou como mutante. Qualquer número diferente de zero passa — inclusive um score constante, arbitrário ou desconectado do detector. Não fixa nem magnitude, nem sinal, nem relação com o score realmente computado. O acréscimo `isinstance(meta["score"], float)` (`:72`) é de tipo, não de valor.

**`detector in {...}`** é uma asserção de pertinência a um conjunto de **dois** elementos onde só existem dois detectores — ou seja, o predicado é quase uma tautologia. Ele não discrimina *qual* detector produziu aquela evidência. Um pipeline que rotulasse **toda** evidência do IsolationForest como `"zscore"` passa na suíte inteira: o `evidence_id` do nome do arquivo continua correto (`cli.py:105` usa `detector.name` separadamente), então nem a contagem de arquivos denuncia. Isso é uma classe de bug real — evidência atribuída ao detector errado é exatamente o tipo de erro que o critério de aceite global de VITALS-06 ("cada anomalia registra … o detector") existe para impedir.

Asserção que discriminaria: agrupar os sidecars por `meta["detector"]` e exigir que **ambos** os nomes apareçam, e/ou casar `meta["detector"]` contra o prefixo do próprio `evidence_id`/nome do arquivo, mais um valor de `score` verificado contra o score recomputado pelo detector correspondente.

---

## Spec-Anchored Acceptance Criteria

Escopo: 12 ACs (13 originais − VITALS-11 AC2, formalmente fora de escopo por AD-028).

### P1 — Detecção sobre CTU-UHB com ground truth real

| Criterion (WHEN X THEN Y) | Desfecho definido pela spec | `arquivo:linha` + asserção | Result |
| --- | --- | --- | --- |
| AC1 / VITALS-01 — carregar WFDB ⇒ FHR, UC e pH | séries + pH presentes | `tests/vitals/test_loader.py:15` — `r.ph == 7.26`; `:16-18` — `r.fhr.shape == (240,)`, `r.uc.shape == (240,)`, `r.fs == 4.0` | ✅ PASS |
| AC2 / VITALS-02 — pH < 7.05 ⇒ patológico | limiar 7.05, comparação estrita | `tests/vitals/test_loader_ph.py:45` — `PH_THRESHOLD == 7.05`; `:49,:54,:58` — `is_pathological(7.04) is True`, `(7.05) is False`, `(7.26) is False` | ✅ PASS (M3 morto) |
| AC3 / VITALS-03 — z-score com limiar configurável | classificação binária que muda com o limiar; **spec.md:47 agora exige comparação estrita `>`** | configurabilidade: `tests/vitals/test_detectors_zscore.py:68-69` — `threshold=3.0 … is False` / `threshold=2.0 … is True` ✅. Fronteira estrita: `:72-80` — **não atinge a fronteira** (score 1 ULP abaixo do limiar; `>` e `>=` dão o mesmo resultado) | ❌ **GAP** — M12 sobreviveu. Deixou de ser lacuna de precisão da spec: a spec **agora define** o desfecho (`spec.md:47`) e nenhuma asserção o alcança |
| AC4 / VITALS-04 — IsolationForest: score por janela **e** binário com limiar configurável | score + binário sensível ao parâmetro | score: `tests/vitals/test_detectors_iforest.py:41` — `scores[-1] > max(normais)`; binário: `:49` — `flags[-1] is True`; configurabilidade: `:54-61` — `sum(muitas) > sum(poucas)` com `contamination` 0.05 vs 0.4 | ✅ PASS (M8 agora morto — era GAP na iteração 1) |
| AC5 / VITALS-05 — agregar por registro, comparar ao pH, P/R/F1 em JSON/CSV | fração `> τ` (AD-027, τ=0.15); `None` fora do denominador | `tests/vitals/test_aggregate.py:30-31,45-48`; métricas `tests/vitals/test_evaluate.py:43-48`; persistência `tests/integration/test_vitals_pipeline.py:40-43` — `n_records == 2`, `prevalence == approx(0.5)` | ✅ PASS (M1, M2 mortos) |
| AC6 / VITALS-06 — anomalia ⇒ gráfico + metadados (record_id, timestamp, pH, score, detector) | os 5 campos **com os valores corretos** | `tests/integration/test_vitals_pipeline.py:64,68,70,71` — `source_record_id == "0001"`, `meta["ph"] == 7.01`, `meta["record_id"] == "0001"` ✅; `:74` — `end_s > start_s` ✅. **`score` e `detector`**: `:69,:73` não fixam valor — M16 e M17 sobreviveram | ⚠️ **GAP parcial** — 3 dos 5 campos com valor asserido; `score` e `detector` não discriminam |

### P2 — Compositor de timeline

| Criterion | Desfecho definido pela spec | `arquivo:linha` + asserção | Result |
| --- | --- | --- | --- |
| AC1 / VITALS-07 — concatenar **na ordem declarada**, timestamps contínuos, proveniência preservada | trechos contíguos **na ordem dos IDs** e cada um atribuído ao registro real de origem | proveniência: `tests/vitals/test_compositor.py:40-43` — `[(s.source_record_id, s.start_idx, s.end_idx) …] == [("r0001",0,100), ("r0002",100,160)]` ✅; contiguidade `:56-60` ✅. **Ordem do sinal**: `:18-28` (`test_concatena_dois_registros_na_ordem_declarada`) assere **apenas `len(t.fhr) == 160` e `len(t.uc) == 160`** — nenhum teste compara o conteúdo de `t.fhr[0:100]` com as amostras de `r0001` | ❌ **GAP** — M18 sobreviveu: inverter a ordem de concatenação do sinal mantendo a proveniência declarada passa nos 143 testes. O nome do teste promete o que ele não verifica |
| AC2 — taxas diferentes ⇒ resample documentado | taxa de destino = a do primeiro registro | `tests/vitals/test_compositor.py:115-117` — `t.fs == 4.0`, `provenance[1].end_idx - start_idx == 20` | ✅ PASS (M19 morto) |
| AC3 — timeline pelos mesmos detectores ⇒ evidências sinalizando a transição | evidências atribuídas ao trecho certo | `tests/integration/test_vitals_timeline.py:63-67` — `assert sidecars`, `origens <= {"normal01","patol01"}`, `"timeline-demo" not in origens`; `:85` — `all(s["source_record_id"] == "patol01" for s in tardias)` | ✅ PASS (M20, M23 mortos) |
| AC4 — mesma config ⇒ mesma timeline | séries e proveniência idênticas | `tests/vitals/test_compositor.py:86-88` — `np.array_equal(a.fhr, b.fhr)`, `a.provenance == b.provenance`; `tests/integration/test_vitals_pipeline.py:107` — `a == b` | ✅ PASS |

### P3 — MIT-BIH (opcional)

| Criterion | Desfecho definido pela spec | `arquivo:linha` + asserção | Result |
| --- | --- | --- | --- |
| AC1 / VITALS-11 — carregar MIT-BIH ⇒ ECG + anotações como rótulo real | série + símbolos; batimentos anômalos contados | `tests/vitals/test_mitbih.py:33-36` — `record_id == "100"`, `fs == 360.0`, `ecg.shape == (400,)`, `len(annotations) == 3`; `:45-46` — `anomalous_beats == 1`, `has_anomaly is True` | ✅ PASS |
| AC2 — evidências no mesmo formato do CTU-UHB | — | **FORA DE ESCOPO** por AD-028 (`.specs/STATE.md:221-227`, status `active`), refletido em `spec.md:126` | ⊘ Descopado (rebaixamento formal verificado) |
| AC3 — dataset ausente ⇒ pular sem interromper o pipeline CTU-UHB | caso pulado, lista vazia, log claro; P1/P2 seguem | `tests/vitals/test_mitbih.py:80-82` — `load_mitbih_dataset(tmp_path / "nao-existe") == []`; `:85-93` — lote completo carregado; `:96-101` — `.atr` corrompido ignorado, `[r.record_id …] == ["100"]` | ✅ PASS (era GAP parcial na iteração 1) |

**Status**: 9/12 ✅ · 2 ❌ GAP (VITALS-03 fronteira, VITALS-07 ordem) · 1 ⚠️ GAP parcial (VITALS-06 payload)

---

## Edge Cases

| Edge case da spec | `arquivo:linha` | Result |
| --- | --- | --- |
| Registro corrompido ⇒ descartado com aviso, lote continua | `tests/vitals/test_loader.py:59-61,78-79`; `tests/integration/test_vitals_pipeline.py:86,91` | ✅ |
| Taxa/duração divergente ⇒ resample antes de concatenar | `tests/vitals/test_compositor.py:115-117` | ✅ |
| Nenhum registro patológico ⇒ alerta explícito | `tests/vitals/test_evaluate.py:70-72`; `tests/core/test_metrics.py:44-47` | ✅ (M4 morto) |
| Janela sem pontos suficientes ⇒ "dados insuficientes" sem exceção | `tests/vitals/test_detectors_iforest.py:71-72`, `:59-62`; fronteira exata `tests/vitals/test_windowing.py:82-90` | ✅ (M7 agora morto) |
| Veredicto indeterminado excluído do cálculo de métricas | `tests/vitals/test_evaluate.py::test_veredicto_indeterminado_e_excluido_do_calculo` | ✅ (M21 morto) |

---

## Discrimination Sensor — Iteração 2

**Profundidade**: P0-full (15 mutações: 7 re-execuções dos sobreviventes da iteração 1 + 8 novas em áreas não sondadas). Todas aplicadas na árvore real e revertidas imediatamente com `git checkout -- <arquivo>`.

### Re-execução dos sobreviventes da iteração 1

| # | Arquivo:linha | Mutação | Iter. 1 | Iter. 2 |
| --- | --- | --- | --- | --- |
| M7 | `src/vitals/windowing.py:277` | `fracao_invalida > max_invalid_fraction` → `>=` | ❌ | ✅ **Morto** — `test_windowing.py::test_fracao_invalida_exatamente_no_limite_permanece_valida` |
| M8 | `src/vitals/detectors.py:134` | `contamination=self.contamination` → `0.1` | ❌ | ✅ **Morto** — `test_detectors_iforest.py::test_contamination_e_configuravel_e_muda_quantas_janelas_sao_marcadas` |
| M9 | `src/vitals/cli.py:114` | `{"ph": record.ph}` → `{"ph": None}` | ❌ | ✅ **Morto** — `test_vitals_pipeline.py::test_toda_evidencia_tem_artefato_e_sidecar` |
| M10 | `src/vitals/cli.py:95` | `if not flag: continue` → sempre `continue` | ✅ (vacuoso) | ✅ **Morto** — agora também pela guarda `assert sidecars` (`:58`), não só pelo teste de timeline |
| M12 | `src/vitals/detectors.py:97` | `s > self.threshold` → `s >= self.threshold` | ❌ | ❌ **SOBREVIVEU** — o novo teste de fronteira erra o limiar por 1 ULP |
| M14 | `src/vitals/cli.py:102` | `score=float(score)` → `score=0.0` | ❌ | ✅ **Morto** — `assert meta["score"] != 0.0` |
| M15 | `src/vitals/cli.py:99` | `detector=detector.name` → `"desconhecido"` | ❌ | ✅ **Morto** — `assert meta["detector"] in {...}` |

### Novas mutações

| # | Arquivo:linha | Mutação | Killed? |
| --- | --- | --- | --- |
| M16 | `src/vitals/cli.py:102` | `score=float(score)` → `score=99.0` (sonda a força de `score != 0.0`) | ❌ **SOBREVIVEU** — 10 passed |
| M17 | `src/vitals/cli.py:99` | `detector=detector.name` → `detector="zscore"` (sonda a força de `in {…}`) | ❌ **SOBREVIVEU** — 10 passed |
| M18 | `src/vitals/compositor.py:84` | `np.concatenate(fhr_partes)` → `np.concatenate(fhr_partes[::-1])` (ordem de concatenação invertida, proveniência intacta) | ❌ **SOBREVIVEU** — 143 passed |
| M19 | `src/vitals/compositor.py:78` | `Segment(start_idx=cursor, …)` → `start_idx=0` (cálculo de proveniência) | ✅ Morto — 3 testes de `test_compositor.py` |
| M20 | `src/vitals/compositor.py:87` | `ph=min(...)` → `ph=max(...)` (escolha do pH mínimo) | ✅ Morto — `test_compositor.py::test_rotulo_da_timeline_usa_o_pior_desfecho` + `test_vitals_timeline.py` |
| M21 | `src/vitals/evaluate.py:149-151` | veredicto indeterminado deixa de ser excluído e passa a contar como normal | ✅ Morto — `test_evaluate.py::test_veredicto_indeterminado_e_excluido_do_calculo` |
| M22 | `src/vitals/plot.py:194` | `if event.source_record_id != event.record_id:` → `if False:` (sufixo de origem some do título) | ✅ Morto — `test_plot.py::test_titulo_mostra_proveniencia_quando_difere_do_registro` |
| M23 | `src/vitals/cli.py:48` | `_proveniencia`: `seg.start_idx <= idx` → `seg.start_idx < idx` (off-by-one na fronteira) | ✅ Morto — 2 testes de `test_vitals_timeline.py` |

**Resultado**: **11/15 mortos, 4 sobreviventes** (M12, M16, M17, M18) → ❌ FAIL.

Árvore de trabalho após o sensor: `git status --short` vazio, `git stash list` vazio — nenhuma mutação deixada no código.

### Diagnóstico de M18 (lacuna nova)

Sob M18 o pipeline continua produzindo 13 evidências e `tardias` continua não vazio (6 sidecars com `start_s >= 300.0`), todos rotulados `patol01` — o teste `test_anomalias_no_segundo_trecho_apontam_para_o_registro_patologico` passa. Mas o **sinal** naqueles índices é o de `normal01`. A causa é estrutural: `compositor.compose` constrói a lista de `Segment` a partir dos **comprimentos** dos trechos (`compositor.py:77-80`), independentemente da ordem em que os arrays são de fato concatenados (`:84-85`). Nenhum teste amarra o conteúdo do sinal à proveniência declarada, então as duas podem divergir silenciosamente — e toda evidência da timeline passaria a apontar para o registro errado sem que a suíte perceba. Isto ataca diretamente o critério de aceite global do projeto ("toda anomalia reportada tem evidência correspondente" — a evidência existe, mas é falsa).

---

## Gate Check

- **Comando (Build)**: `make lint && pytest -q`
- **Lint**: `.venv/bin/python -m ruff check src tests` → `All checks passed!`
- **Unitários**: `.venv/bin/python -m pytest -q -m "not integration"` → **133 passed, 10 deselected** (4,2 s)
- **Integração**: `.venv/bin/python -m pytest -q -m integration` → **10 passed, 133 deselected** (23,6 s)
- **Suíte completa**: `.venv/bin/python -m pytest -q` → **143 passed, 0 failed, 0 skipped** (26 s)
- **Baseline alegada pelo autor (133 + 10 = 143)**: ✅ **confirmada**
- **Contagem na iteração 1**: 135 (125 + 10) — **delta: +8 testes**, nenhum removido, nenhuma asserção enfraquecida
- **Skips**: nenhum · **Falhas**: nenhuma

> Nota de integridade (pendência da iteração 1, agravada): `.specs/STATE.md:233` ainda diz "135 testes passando (129 unitários + 6 de integração)". Estava errado antes (o real era 125 + 10) e agora está desatualizado também no total (143 = 133 + 10). Fix 7 não foi aplicado.

---

## Code Quality

| Princípio | Status |
| --- | --- |
| Código mínimo, sem features além do pedido | ✅ |
| Sem abstrações para uso único | ✅ |
| Sem "flexibilidade" desnecessária | ✅ |
| Só tocou arquivos exigidos | ✅ — `2f17d14` toca apenas testes e `.specs/`, nenhuma linha de `src/` |
| Não "melhorou" código não relacionado | ✅ |
| Segue padrões/estilo existentes | ✅ |
| Um engenheiro sênior aprovaria? | ⚠️ A implementação é sólida; **as correções de teste é que não passariam na revisão** — duas foram escritas para o mutante, não para o comportamento |
| Testes mapeiam ACs e não são rasos | ⚠️ `test_score_exatamente_no_limiar_nao_e_marcado` não testa o que o nome e o docstring afirmam; `test_concatena_dois_registros_na_ordem_declarada` não testa a ordem |
| Spec-anchored: valor asserido = desfecho da spec | ⚠️ 3 lacunas (VITALS-03 fronteira, VITALS-06 `score`/`detector`, VITALS-07 ordem) |
| Coverage Expectation por camada | ✅ `load_mitbih_dataset` agora coberto; domínio 1:1 com ACs |
| Todo teste mapeia a um AC / edge case / Done-when | ⚠️ `test_seeds_diferentes_sao_permitidas_e_o_valor_e_preservado` (`test_detectors_iforest.py:70-74`) assere apenas que o construtor guarda os argumentos — não mapeia a nenhum AC e não exercita comportamento |
| Guidelines documentadas seguidas | ✅ "nenhuma — defaults fortes aplicados" |

**Padrão observado**: das 6 correções, 4 são genuínas e 2 foram calibradas contra o literal do mutante citado no relatório anterior (`!= 0.0` é a negação de `score=0.0`; `in {"zscore","isolation_forest"}` é a exclusão de `"desconhecido"`). Uma terceira (fronteira do z-score) tem a intenção correta mas a execução errada. O sinal para a próxima iteração é: **corrigir o comportamento verificado, não o mutante nomeado** — o relatório de mutação lista exemplos, não a especificação do conserto.

---

## Fix Plans

### Fix A — VITALS-03: teste de fronteira do z-score não atinge a fronteira (M12)
- **Root cause**: `tests/vitals/test_detectors_zscore.py:72-80`. O score calculado (`1.414213562373095`) é 1 ULP **menor** que `math.sqrt(2)` (`1.4142135623730951`); `flag` devolve `False` sob `>` e sob `>=`. `pytest.approx` na linha 79 esconde a diferença que decide o comportamento.
- **Fix task**: construir a fronteira de modo exato em vez de aritmeticamente. Ou (a) instanciar o detector com `threshold=d.score(serie)[-1]` — o próprio valor computado, garantindo igualdade bit a bit — e asserir `flag(...)[-1] is False`; ou (b) escolher um baseline com desvio exatamente representável (ex.: desvio 2.0, valor 144.0 ⇒ score 1.0) e `threshold=1.0`. Trocar `pytest.approx` por `==` neste teste específico.
- **Verify**: reaplicar M12 (`s > self.threshold` → `>=`) e confirmar que morre.
- **Prioridade**: Major (a spec agora define o desfecho em `spec.md:47`; é AC descoberto, não lacuna de precisão)

### Fix B — VITALS-06: `score` e `detector` no payload não discriminam (M16, M17)
- **Root cause**: `tests/integration/test_vitals_pipeline.py:69,73`. `score != 0.0` só exclui o literal zero; `detector in {…}` só exclui nomes fora do conjunto de dois. Nenhuma das duas fixa o valor correto.
- **Fix task**: (a) agrupar os sidecars por `meta["detector"]` e asserir que os **dois** nomes aparecem, e que `meta["detector"]` é prefixo/componente do `evidence_id` do próprio arquivo — isso mata M17; (b) para `score`, recomputar o score do detector correspondente sobre a mesma janela e asserir `meta["score"] == pytest.approx(esperado)`, ou no mínimo casar `meta["score"]` contra o valor que aparece no título do gráfico — isso mata M16. Não usar mais predicados de negação de literal.
- **Verify**: reaplicar M14, M15, M16 e M17; todos devem morrer.
- **Prioridade**: Major (critério de aceite global: evidência atribuída ao detector errado é evidência falsa)

### Fix C — VITALS-07: ordem de concatenação do sinal não é verificada (M18)
- **Root cause**: `tests/vitals/test_compositor.py:18-28` assere apenas comprimentos. `compositor.py:77-80` monta a proveniência a partir dos comprimentos, independentemente da ordem real de `np.concatenate` em `:84-85` — as duas podem divergir sem que nenhum teste perceba. `test_vitals_timeline.py:85` verifica apenas rótulos de proveniência, não conteúdo.
- **Fix task**: em `test_concatena_dois_registros_na_ordem_declarada`, escrever os dois registros com valores de FHR distinguíveis (ex.: `fhr_base=140.0` e `fhr_base=95.0`) e asserir `np.array_equal(t.fhr[:100], r0001.fhr)` e `np.array_equal(t.fhr[100:], r0002.fhr)` — conteúdo, não comprimento. Idem para `uc`. Adicionar uma asserção que amarre cada `Segment` ao conteúdo do intervalo que ele declara.
- **Verify**: reaplicar M18 e confirmar que morre.
- **Prioridade**: Major

### Fix D — Teste sem mapeamento a AC
- **Root cause**: `tests/vitals/test_detectors_iforest.py:70-74` (`test_seeds_diferentes_sao_permitidas_e_o_valor_e_preservado`) assere apenas que `__init__` guardou seus argumentos; não exercita comportamento nem mapeia a AC/edge case/Done-when.
- **Fix task**: remover, ou reescrever como teste de determinismo real (mesma seed ⇒ mesmos flags; seeds diferentes ⇒ ainda determinístico por execução), que é o que a docstring de `IsolationForestDetector` (`detectors.py:103-106`) justifica.
- **Prioridade**: Minor

### Fix E — Contagem de testes incorreta no STATE.md (pendente da iteração 1)
- **Root cause**: `.specs/STATE.md:233` — "135 testes passando (129 unitários + 6 de integração)"; o real é 143 (133 + 10).
- **Fix task**: corrigir a linha.
- **Prioridade**: Cosmetic

### Fix F — Tabela de rastreabilidade da spec desatualizada
- **Root cause**: `.specs/features/vitals-anomaly/spec.md:146-156` lista os 11 requisitos como `Design | Pending`, embora todos estejam implementados e a maioria verificada.
- **Fix task**: atualizar a coluna de status conforme a tabela de rastreabilidade abaixo.
- **Prioridade**: Cosmetic

---

## Requirement Traceability Update

| Requirement | Iteração 1 | Iteração 2 |
| --- | --- | --- |
| VITALS-01 | ✅ Verified | ✅ Verified |
| VITALS-02 | ✅ Verified | ✅ Verified |
| VITALS-03 | ✅ Verified (fronteira não fixada) | ❌ **Needs Fix** — spec agora define comparação estrita (`spec.md:47`) e o teste de fronteira não a alcança (Fix A) |
| VITALS-04 | ❌ Needs Fix | ✅ **Verified** — `contamination` coberto, M8 morto |
| VITALS-05 | ✅ Verified | ✅ Verified |
| VITALS-06 | ❌ Needs Fix | ⚠️ **Parcial** — `ph`/`record_id`/`source_record_id` com valor asserido; `score`/`detector` não discriminam (Fix B) |
| VITALS-07 | ✅ Verified | ❌ **Needs Fix** — ordem de concatenação do sinal não verificada (Fix C) |
| VITALS-08 | ✅ Verified | ✅ Verified |
| VITALS-09 | ✅ Verified (fronteira não fixada) | ✅ **Verified** — fronteira exata coberta, M7 morto |
| VITALS-10 | ✅ Verified | ✅ Verified |
| VITALS-11 | ❌ Needs Fix | ✅ **Verified no escopo reduzido** — AC1 e AC3 cobertos; AC2 descopado por AD-028 (ativa, refletida na spec) |

---

## Summary

**Overall**: ❌ Not Ready (iteração 2 de 3)

**Spec-anchored check**: 9/12 ACs em escopo com desfecho da spec asserido · 2 GAPs (VITALS-03, VITALS-07) · 1 GAP parcial (VITALS-06)
**Sensor**: 11/15 mortos — 4 sobreviventes (M12, M16, M17, M18)
**Gate**: 143 passed (133 unitários + 10 integração), 0 failed, 0 skipped; lint limpo — baseline do autor confirmada

**O que melhorou de verdade**: a guarda contra vacuidade elimina uma classe inteira de teste falso-positivo; `contamination` passou de "declarado configurável" a "provado configurável" com dois valores que mudam o resultado; a fronteira de `max_invalid_fraction` está exercitada no ponto exato; `load_mitbih_dataset` tem os três caminhos (ausente, lote completo, registro ilegível); e o rebaixamento de VITALS-11 AC2 é **legítimo** — AD-028 existe, está `active`, tem escopo e trade-off explícitos, e a spec marca o AC como riscado com referência à decisão. O autor também reconheceu no corpo do commit ter marcado T18 como concluída sem o Done-when cumprido, o que é a postura correta.

**O que não melhorou**: duas asserções foram escritas contra o **literal do mutante** em vez de contra o comportamento — `score != 0.0` e `detector in {dois-elementos}` matam exatamente M14/M15 e nada mais; mutações triviais (`score=99.0`, `detector="zscore"` sempre) atravessam a suíte inteira. O teste de fronteira do z-score falha no seu próprio propósito por 1 ULP, com `pytest.approx` mascarando justamente a diferença que o código sob teste avalia — M12 sobreviveu pela segunda vez. E uma área não sondada na iteração 1 revelou que a ordem de concatenação do sinal da timeline não é verificada por nenhum teste: inverter os trechos preservando a proveniência declarada passa nos 143 testes, produzindo evidências que apontam para o registro errado.

**Next steps**: aplicar Fix A, B e C (todos só de teste, nenhuma mudança em `src/`). Recomendação explícita ao implementador: para cada um, escrever a asserção contra o **valor correto recomputado**, não contra a negação do valor mutante; e verificar o conserto reaplicando **duas** mutações — a nomeada e uma variante trivial diferente. Re-verificar depois (será a iteração 3 de 3; se ainda houver sobreviventes, escalar ao usuário em vez de continuar o loop).

**Lições a destilar** (há sinal: 4 mutantes sobreviventes + 2 testes cujo nome não corresponde ao que verificam). O Verifier só pode escrever este arquivo, então o registro em `.specs/LESSONS.md` via `scripts/lessons.py add` fica para o orquestrador. Candidatas:
- (a) "asserção escrita como negação do literal usado no mutante (`x != 0.0`) não é asserção de valor — mata só aquele mutante; asserir o valor correto recomputado";
- (b) "pertinência a um conjunto pequeno (`x in {a, b}`) quase não discrimina quando o domínio tem o mesmo tamanho do conjunto — verificar qual dos valores é o correto para aquele caso";
- (c) "teste de fronteira com aritmética de ponto flutuante precisa de igualdade bit a bit: derivar o limiar do próprio valor computado, e `pytest.approx` na fronteira mascara exatamente a diferença sob teste";
- (d) "quando metadados (proveniência, índices) são construídos separadamente do dado, algum teste precisa amarrar os dois — senão eles divergem em silêncio";
- (e) "verificar um conserto de mutação com uma segunda variante da mesma mutação, não apenas com a que foi reportada".
