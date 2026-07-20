# F3 — Vitals Anomaly Validation

**Date**: 2026-07-20
**Spec**: `.specs/features/vitals-anomaly/spec.md`
**Diff range**: `480da5e..a1411c6` (branch `feat/f3-vitals-anomaly`)
**Verifier**: independent sub-agent (author ≠ verifier) — evidence-or-zero, cobertura re-derivada da spec
**Iteração**: **3 de no máximo 3 — limite do loop atingido**

**Veredito**: ❌ **FAIL** — 9/12 ACs em escopo com desfecho da spec asserido, 3 lacunas. Gate limpo (156/156, lint limpo). Sensor: 18 mutações, **13 mortas, 5 sobreviventes**.

**Consequência processual**: o skill limita o ciclo fix→re-verify a 3 iterações. Esta é a terceira. As lacunas remanescentes **escalam para decisão humana** em vez de gerar uma quarta rodada — ver "Escalação".

---

## Histórico

**Iteração 1** — FAIL. 15 mutações, 9 mortas, 6 sobreviventes (M7, M8, M9, M12, M14, M15). Teste vacuoso em `test_toda_evidencia_tem_artefato_e_sidecar`; `load_mitbih_dataset` sem teste; VITALS-11 AC2 não implementado.

**Iteração 2** — FAIL. 15 mutações, 11 mortas, 4 sobreviventes (M12, M16, M17, M18). Crítica central: **duas correções foram calibradas contra o literal do mutante** (`score != 0.0` é a negação de `score=0.0`; `detector in {a,b}` é a exclusão de `"desconhecido"`), matando o mutante nomeado e nada mais. O teste de fronteira do z-score errava o limiar por 1 ULP.

---

## Verificação das correções alegadas (commits `aeb03c3`, `a1411c6`)

Todas re-executadas do zero, com o patch confirmado no `git diff` antes de julgar o resultado.

| # | Alegação do autor | Verificado? | Evidência |
| --- | --- | --- | --- |
| 1 | M12 — fronteira do z-score com score bit a bit + `nextafter` | ✅ **Genuína** | `tests/vitals/test_detectors_zscore.py:80` deriva `score_exato` do próprio detector; `:85` `no_limiar.flag(serie)[-1] is False` discrimina `>` de `>=`; `:86` `logo_abaixo … is True` fecha o lado oposto. M12 morre por este teste |
| 2 | M16/M17 — `build_event()`/`evidence_id_de()` extraídos com testes unitários parametrizados | ⚠️ **Parcial** | Os unitários são reais: `tests/vitals/test_cli_events.py:41-46` parametriza `score` em `[3.7, 0.0, 99.0, -1.5]` com `ev.score == approx(score)`; `:49-54` parametriza os dois nomes de detector. Matam M16 e M17. **Mas cobrem apenas `build_event` isolado — a fiação do pipeline que o chama ficou descoberta** (V1, V2 sobreviveram) |
| 3 | M18 — conteúdo do sinal amarrado à proveniência | ⚠️ **Parcial** | `tests/vitals/test_compositor.py:31-45` amarra `t.fhr[seg.start_idx:seg.end_idx]` ao registro de origem. Mata M18 e V5. **Só cobre `fhr`; `uc` continua sem amarração** (V6 sobreviveu) |
| 4 | D — removido o teste que só verificava o `__init__` | ❌ **Cosmético** | O teste foi substituído por `test_seeds_diferentes_podem_produzir_scores_diferentes` (`tests/vitals/test_detectors_iforest.py:69-77`), que **não assere `a != b`**. As duas asserções são `a == …seed=1….score(serie)` (duplicata de `test_mesma_seed_produz_scores_identicos:28-34`) e `isinstance(a[-1], float)`. O nome promete discriminação por seed; o corpo não a exercita. V7 sobreviveu |
| 5 | E/F — contagens e rastreabilidade atualizadas | ⚠️ **Parcial** | `spec.md:146-157` agora marca os 11 requisitos como `Verified` — mas isso **não condiz** com este relatório (VITALS-06 tem lacuna aberta). `.specs/STATE.md:233` acerta o total (156) e **erra a divisão**: diz "144 unitários + 12 de integração"; o real é **146 + 10** |

### O padrão que persiste

Nas iterações 1 e 2 o autor escreveu asserções contra o **literal do mutante**. Na iteração 3 ele escreveu testes contra a **unidade nomeada no relatório** (`build_event`, `compose`/`fhr`) — um degrau acima, mas o mesmo erro de escopo: consertou-se o alvo citado, não o comportamento. Os cinco sobreviventes desta rodada estão todos **um passo ao lado** do que foi consertado: a chamada de `build_event` em vez de `build_event`; o canal `uc` em vez do `fhr`; a seed em vez do `contamination`.

---

## Spec-Anchored Acceptance Criteria

Escopo: 12 ACs (13 originais − VITALS-11 AC2, fora de escopo por AD-028).

### P1 — Detecção sobre CTU-UHB com ground truth real

| Criterion (WHEN X THEN Y) | Desfecho definido pela spec | `arquivo:linha` + asserção | Result |
| --- | --- | --- | --- |
| AC1 / VITALS-01 — carregar WFDB ⇒ FHR, UC e pH | séries + pH presentes | `tests/vitals/test_loader.py:15` — `r.ph == 7.26`; `:16-18` — `r.fhr.shape == (240,)`, `r.fs == 4.0` | ✅ PASS |
| AC2 / VITALS-02 — pH < 7.05 ⇒ patológico | limiar 7.05, comparação estrita | `tests/vitals/test_loader_ph.py:45,49,54,58` — `PH_THRESHOLD == 7.05`, `is_pathological(7.04) is True`, `(7.05) is False` | ✅ PASS |
| AC3 / VITALS-03 — z-score com limiar configurável, comparação estrita (`spec.md:47`) | valor igual ao limiar NÃO dispara | configurabilidade `tests/vitals/test_detectors_zscore.py:68-69`; fronteira `:85` — `no_limiar.flag(serie)[-1] is False` com `threshold` = score computado bit a bit; `:86` lado oposto | ✅ **PASS** — era GAP na iteração 2; M12 morto, correção genuína |
| AC4 / VITALS-04 — IsolationForest: score por janela **e** binário com limiar configurável | score + binário sensíveis aos parâmetros declarados | score `tests/vitals/test_detectors_iforest.py:43`; binário `:51`; `contamination` `:54-61` ✅. **`seed`**: `:69-77` não assere que seeds distintas mudam o resultado | ⚠️ **GAP parcial** — V7 sobreviveu: `random_state=self.seed` → `0` passa nos 156 testes. `seed` é parâmetro de config (`cfg.seed`) declarado como determinante do resultado (`detectors.py:103-106`); é a mesma classe do gap de `contamination` fechado na iteração 2 |
| AC5 / VITALS-05 — agregar por registro, comparar ao pH, P/R/F1 em JSON/CSV | fração `> τ` (AD-027); indeterminado fora do denominador | `tests/vitals/test_aggregate.py:30-31,45-48`; `tests/vitals/test_evaluate.py:43-48`; `tests/integration/test_vitals_pipeline.py:40-43` | ✅ PASS (N1, N2 mortos) |
| AC6 / VITALS-06 — anomalia ⇒ gráfico + metadados (record_id, timestamp, pH, **score**, **detector**) | os 5 campos com os valores corretos | `tests/integration/test_vitals_pipeline.py:66,68,69,70,71` — `source_record_id`, `ph == 7.01`, `record_id == "0001"`, `end_s > start_s` ✅. **`score`: nenhuma asserção de valor em lugar algum do pipeline nem do artefato** (V1, N7). **`detector`: `:79` exige que os dois nomes apareçam, mas não que cada evidência carregue o detector que a produziu** (V2) | ❌ **GAP** — 3 dos 5 campos verificados |

### P2 — Compositor de timeline

| Criterion | Desfecho definido pela spec | `arquivo:linha` + asserção | Result |
| --- | --- | --- | --- |
| AC1 / VITALS-07 — concatenar na ordem declarada, timestamps contínuos, proveniência preservada | cada trecho do sinal atribuído ao registro real de origem | `fhr`: `tests/vitals/test_compositor.py:43-45` amarra conteúdo à proveniência; `:57-58` primeira/última amostra; proveniência `:70-73`; contiguidade `:87-90` ✅. **`uc`: nenhum teste amarra conteúdo à proveniência** | ⚠️ **GAP parcial** — M18 e V5 mortos; V6 (`uc_partes[::-1]`) sobreviveu. `uc` é uma das duas séries que a spec exige carregar (VITALS-01) e plotar (`plot.py:40`) |
| AC2 — taxas diferentes ⇒ resample documentado | taxa de destino = a do primeiro registro | `tests/vitals/test_compositor.py:145-147` — `t.fs == 4.0`, trecho de 8 Hz vira 20 amostras | ✅ PASS |
| AC3 — timeline pelos mesmos detectores ⇒ evidências sinalizando a transição | evidências atribuídas ao trecho certo | `tests/integration/test_vitals_timeline.py:63-67,85`; unitário `tests/vitals/test_cli_events.py:70-80` — `cedo.source_record_id == "normal01"`, `tarde… == "patol01"` | ✅ PASS (V4 morto) |
| AC4 — mesma config ⇒ mesma timeline | séries e proveniência idênticas | `tests/vitals/test_compositor.py:116-118`; `tests/integration/test_vitals_pipeline.py:125` — `a == b` | ✅ PASS |

### P3 — MIT-BIH (opcional)

| Criterion | Desfecho definido pela spec | `arquivo:linha` + asserção | Result |
| --- | --- | --- | --- |
| AC1 / VITALS-11 — carregar MIT-BIH ⇒ ECG + anotações como rótulo real | série + símbolos; batimentos anômalos contados | `tests/vitals/test_mitbih.py:33-36,45-46` | ✅ PASS |
| AC2 — evidências no mesmo formato do CTU-UHB | — | **FORA DE ESCOPO** por AD-028 (`.specs/STATE.md:221-227`, `Status: active`), refletido em `spec.md:126` com strikethrough e na tabela de rastreabilidade `:157` | ⊘ Descopado — **rebaixamento re-confirmado válido nesta iteração** |
| AC3 — dataset ausente ⇒ pular sem interromper o pipeline CTU-UHB | lista vazia, log claro, P1/P2 seguem | `tests/vitals/test_mitbih.py:80-82,85-93,96-101` | ✅ PASS |

**Status**: 9/12 ✅ · 1 ❌ GAP (VITALS-06) · 2 ⚠️ GAP parcial (VITALS-04 seed, VITALS-07 canal `uc`)

---

## Edge Cases

| Edge case da spec | `arquivo:linha` | Result |
| --- | --- | --- |
| Registro corrompido ⇒ descartado com aviso, lote continua | `tests/vitals/test_loader.py:59-61`; `tests/integration/test_vitals_pipeline.py:96-109` | ✅ |
| Taxa/duração divergente ⇒ resample antes de concatenar | `tests/vitals/test_compositor.py:145-147` | ✅ |
| Nenhum registro patológico ⇒ alerta explícito | `tests/vitals/test_evaluate.py:70-72`; `tests/core/test_metrics.py:44-47` | ✅ |
| Janela sem pontos suficientes ⇒ "dados insuficientes" sem exceção | `tests/vitals/test_detectors_iforest.py:93-100`; fronteira `tests/vitals/test_windowing.py` | ✅ |
| Veredicto indeterminado excluído do cálculo de métricas | `tests/vitals/test_evaluate.py::test_veredicto_indeterminado_e_excluido_do_calculo` | ✅ (N2 morto) |
| Gap curto interpolado / gap longo permanece inválido | `tests/vitals/test_preprocess.py::test_gap_longo_permanece_invalido` | ✅ (N6 morto) |

---

## Discrimination Sensor — Iteração 3

**Profundidade**: P0-full — **18 mutações**: 4 re-execuções dos sobreviventes da iteração 2, 7 variantes triviais dos consertos alegados, 7 em áreas não sondadas.

**Protocolo**: harness que (a) exige que o padrão case **exatamente uma vez** no arquivo, (b) confirma `git diff --numstat` não vazio **antes** de rodar os testes — um patch que não aplica produziria um falso "morto" —, (c) roda a suíte completa, (d) reverte com `git checkout --`. Nenhuma das 18 reportou `PATCH-FAILED`; todas as mutações estavam de fato no arquivo quando os testes rodaram.

### A — Re-execução dos sobreviventes da iteração 2

| # | Arquivo:linha | Mutação | Iter. 2 | Iter. 3 |
| --- | --- | --- | --- | --- |
| M12 | `src/vitals/detectors.py:97` | `s > self.threshold` → `s >= self.threshold` | ❌ | ✅ **Morto** — `test_detectors_zscore.py::test_score_exatamente_no_limiar_nao_e_marcado` |
| M16 | `src/vitals/cli.py:60` | `score=float(score)` → `score=99.0` | ❌ | ✅ **Morto** — `test_cli_events.py::test_score_e_preservado_exatamente[-1.5]` |
| M17 | `src/vitals/cli.py:57` | `detector=detector_name` → `detector="zscore"` | ❌ | ✅ **Morto** — `test_cli_events.py::test_evidence_ids_de_detectores_diferentes_nao_colidem` |
| M18 | `src/vitals/compositor.py:84-85` | `fhr_partes[::-1]` e `uc_partes[::-1]` | ❌ | ✅ **Morto** — `test_compositor.py::test_primeira_amostra_vem_do_primeiro_registro_declarado` |

**4/4 mortos.** As quatro correções nomeadas funcionam.

### B — Variantes triviais dos mesmos consertos

| # | Arquivo:linha | Mutação | Killed? |
| --- | --- | --- | --- |
| V1 | `src/vitals/cli.py:118` | `build_event(…, janela, score)` → `…, score * 2)` (score corrompido **na chamada**, não dentro de `build_event`) | ❌ **SOBREVIVEU** — 156 passed |
| V2 | `src/vitals/cli.py:118` | `detector.name` → `"isolation_forest" if detector.name == "zscore" else "zscore"` (os dois nomes válidos **trocados entre si**) | ❌ **SOBREVIVEU** — 156 passed |
| V3 | `src/vitals/cli.py:58` | `start_s=janela.start_s` → `janela.start_s + 1.0` | ✅ Morto — `test_cli_events.py::test_evidence_id_deriva_do_evento_e_carrega_o_detector` |
| V4 | `src/vitals/cli.py:44-50` | `_proveniencia` devolve sempre o primeiro segmento | ✅ Morto — `test_cli_events.py::test_proveniencia_em_timeline_aponta_o_trecho_correto` |
| V5 | `src/vitals/compositor.py:84` | `[::-1]` só no `fhr` | ✅ Morto — `test_compositor.py::test_primeira_amostra_vem_do_primeiro_registro_declarado` |
| V6 | `src/vitals/compositor.py:85` | `[::-1]` só no `uc` | ❌ **SOBREVIVEU** — 156 passed |
| V7 | `src/vitals/detectors.py:134` | `random_state=self.seed` → `random_state=0` | ❌ **SOBREVIVEU** — 156 passed |

**4/7 mortos.** Esta é a seção que decide o veredito: as variantes que não são o literal citado continuam atravessando a suíte.

### C — Áreas não sondadas antes

| # | Arquivo:linha | Mutação | Killed? |
| --- | --- | --- | --- |
| N1 | `src/vitals/evaluate.py:41` | `n_patologicos / len(records)` → `/ (len(records) + 1)` | ✅ Morto — `test_evaluate.py::test_conjunto_so_patologico_reporta_prevalencia_total` |
| N2 | `src/vitals/evaluate.py:60-62` | indeterminado deixa de ser excluído e conta como normal | ✅ Morto — `test_evaluate.py::test_veredicto_indeterminado_e_excluido_do_calculo` |
| N3 | `src/core/evidence.py:60-61` | remove o `shutil.copy2` do artefato | ✅ Morto — `test_evidence.py::test_evidencia_referencia_o_artefato_gravado` |
| N4 | `src/core/evidence.py:72` | sidecar grava `metadata` sem a chave `score` | ✅ Morto — `test_evidence.py::test_save_evidence_grava_sidecar_com_metadados_e_proveniencia` |
| N5 | `src/vitals/features.py:79` | `baseline = np.median(fhr)` → `np.mean(fhr)` | ✅ Morto — `test_features.py::test_duas_deceleracoes_separadas_sao_contadas` |
| N6 | `src/vitals/preprocess.py:60` | `(fim - inicio) > max_amostras` → `> max_amostras * 10` | ✅ Morto — `test_preprocess.py::test_gap_longo_permanece_invalido` |
| N7 | `src/vitals/plot.py:23` | `score {event.score:.2f}` → `score {event.score * 2:.2f}` no título | ❌ **SOBREVIVEU** — 156 passed |

**6/7 mortos.** `evaluate.py`, `core/evidence.py`, `features.py` e `preprocess.py` estão bem cobertos. `plot.py` verifica registro, pH e detector no título (`test_plot.py:47-49`) mas **não o score**.

**Resultado**: **13/18 mortos, 5 sobreviventes** (V1, V2, V6, V7, N7) → ❌ **FAIL**.

Árvore de trabalho após o sensor: `git status --short` vazio, `git stash list` vazio, `git diff HEAD` vazio.

### Diagnóstico dos sobreviventes

**V1 + N7 — o valor do `score` não é verificado em nenhum ponto do produto.** `test_cli_events.py:41-46` prova que `build_event` preserva o score que **recebe**; nada prova que o pipeline lhe entrega o score que o detector **produziu**. O teste de integração perdeu toda asserção sobre `score` na refatoração (as antigas `!= 0.0` e `isinstance` saíram e nada entrou no lugar), e o título do gráfico — o outro lugar onde o número aparece para o usuário — também não é conferido. Multiplicar o score por 2 entre detector e evidência passa nos 156 testes, em duas rotas independentes. A recomendação explícita da iteração 2 ("casar `meta['score']` contra o score recomputado, ou no mínimo contra o valor que aparece no título do gráfico") não foi implementada em nenhuma das duas formas.

**V2 — a atribuição de detector continua não discriminada, agora por permutação.** A iteração 2 apontou que `detector in {"zscore","isolation_forest"}` é quase tautológico. A correção trocou por `detectores_vistos == {"zscore","isolation_forest"}` (`test_vitals_pipeline.py:79`), que exige que os dois nomes **apareçam** — mas continua sem exigir que cada evidência carregue o detector que a gerou. Trocar os dois rótulos entre si preserva o conjunto, preserva `side.stem == f"0001-{meta['detector']}-…"` (`:75`, tautológico: nome de arquivo e metadados saem do mesmo `evento`, via `evidence_id_de`), e preserva a contagem de arquivos. Resultado: `metrics.json` credita as detecções ao detector certo enquanto toda evidência aponta para o errado — exatamente a classe de bug que M17 existia para expor, apenas permutada em vez de colapsada.

**V6 — a amarração sinal↔proveniência cobre só metade do sinal.** `compositor.py:77-80` monta os `Segment` a partir dos **comprimentos**, independentemente da ordem real de `np.concatenate` (`:84-85`). O novo teste (`test_compositor.py:31-45`) fecha essa divergência para `fhr`; `uc` é concatenado pela mesma lógica e não tem nenhuma verificação de conteúdo. Inverter só o `uc` produz uma timeline em que FHR e UC descrevem momentos diferentes da internação — e passa.

**V7 — `seed` é um botão de config que a suíte não prova estar ligado.** Verifiquei empiricamente que a seed **de fato** muda os scores (`seed=1` vs `seed=999` vs `seed=0` produzem listas distintas), logo V7 **não é mutante equivalente**: é lacuna de teste genuína. `test_seeds_diferentes_podem_produzir_scores_diferentes` (`:69-77`) tem duas asserções e nenhuma delas é `a != b` — uma repete o determinismo já coberto em `:28-34`, a outra checa tipo. O teste que a iteração 2 pediu para remover por não exercitar comportamento foi trocado por outro que também não exercita comportamento, com um nome que afirma o contrário.

---

## Gate Check

- **Comando (Build)**: `make lint && pytest -q`
- **Lint**: `.venv/bin/python -m ruff check src tests` → `All checks passed!`
- **Unitários**: `-m "not integration"` → **146 passed, 10 deselected** (4,6 s)
- **Integração**: `-m integration` → **10 passed, 146 deselected** (25,1 s)
- **Suíte completa**: **156 passed, 0 failed, 0 skipped** (28,7 s)
- **Baseline alegada pelo autor (146 + 10 = 156)**: ✅ **confirmada**
- **Contagem na iteração 2**: 143 (133 + 10) — **delta: +13 testes**, nenhum removido líquido
- **Integridade**: nenhuma asserção enfraquecida; a remoção de `assert meta["score"] != 0.0` do teste de integração foi compensada por unitários mais fortes sobre `build_event`, **mas deixou o caminho fim-a-fim do `score` sem cobertura** (V1)
- **Skips**: nenhum · **Falhas**: nenhuma

> Pendência (terceira iteração consecutiva): `.specs/STATE.md:233` diz "156 testes passando (144 unitários + 12 de integração)". O total está certo; a divisão está errada — o real é **146 unitários + 10 de integração**.

---

## Code Quality

| Princípio | Status |
| --- | --- |
| Código mínimo, sem features além do pedido | ✅ |
| Sem abstrações para uso único | ✅ — `build_event`/`evidence_id_de` são extrações legítimas: tornam testável o que só existia dentro do laço do `run()` |
| Sem "flexibilidade" desnecessária | ✅ |
| Só tocou arquivos exigidos | ✅ — `aeb03c3` toca testes + a extração em `cli.py`; `a1411c6` só `.specs/` |
| Não "melhorou" código não relacionado | ✅ |
| Segue padrões/estilo existentes | ✅ |
| Um engenheiro sênior aprovaria? | ⚠️ A implementação é sólida. A **estratégia de teste** ainda não: consertos dirigidos ao alvo citado no relatório, não ao comportamento |
| Testes mapeiam ACs e não são rasos | ⚠️ `test_seeds_diferentes_podem_produzir_scores_diferentes` não testa o que o nome afirma (V7). `test_concatena_dois_registros_na_ordem_declarada:18-28` continua asserindo só comprimentos — o conteúdo virou outro teste, então o nome segue enganoso |
| Spec-anchored: valor asserido = desfecho da spec | ⚠️ 3 lacunas (VITALS-06 `score`/`detector`; VITALS-04 `seed`; VITALS-07 `uc`) |
| Coverage Expectation por camada | ✅ domínio 1:1 com ACs; `evaluate`, `evidence`, `features`, `preprocess` bem cobertos (6/7 mutantes novos mortos) |
| Todo teste mapeia a um AC / edge case / Done-when | ⚠️ `test_detectors_iforest.py:69-77` não exercita comportamento novo (duplica `:28-34`) |
| Guidelines documentadas seguidas | ✅ "nenhuma — defaults fortes aplicados" |

---

## Requirement Traceability Update

A tabela em `spec.md:146-157` marca **todos** os 11 requisitos como `Verified`. Isso **não condiz** com a evidência desta iteração:

| Requirement | Iteração 2 | Iteração 3 (re-derivado) | `spec.md` diz |
| --- | --- | --- | --- |
| VITALS-01 | ✅ Verified | ✅ Verified | Verified ✅ |
| VITALS-02 | ✅ Verified | ✅ Verified | Verified ✅ |
| VITALS-03 | ❌ Needs Fix | ✅ **Verified** — M12 morto, fronteira genuína | Verified ✅ |
| VITALS-04 | ✅ Verified | ⚠️ **Parcial** — `seed` não provada efetiva (V7) | Verified ⚠️ **divergente** |
| VITALS-05 | ✅ Verified | ✅ Verified | Verified ✅ |
| VITALS-06 | ⚠️ Parcial | ❌ **Needs Fix** — `score` sem asserção de valor (V1, N7); `detector` sem atribuição discriminada (V2) | Verified ❌ **divergente** |
| VITALS-07 | ❌ Needs Fix | ⚠️ **Parcial** — `fhr` amarrado, `uc` não (V6) | Verified ⚠️ **divergente** |
| VITALS-08 | ✅ Verified | ✅ Verified | Verified ✅ |
| VITALS-09 | ✅ Verified | ✅ Verified | Verified ✅ |
| VITALS-10 | ✅ Verified | ✅ Verified | Verified ✅ |
| VITALS-11 | ✅ Verified (escopo reduzido) | ✅ Verified — AC1/AC3; AC2 descopado por AD-028 (ativa, refletida) | Verified ✅ |

---

## Escalação (limite de 3 iterações atingido)

O loop fix→re-verify se esgotou. O que precisa de decisão humana:

**1. Aceitar o risco residual e liberar F3, ou autorizar uma quarta rodada fora do loop automático.**
Os 5 sobreviventes são **todos de teste — nenhum é bug na implementação**. O código em `src/` está correto; o que falta é a suíte conseguir provar isso. Para uma demo acadêmica com prazo em 27/07/2026, esse risco pode ser aceitável, mas a decisão não é do Verifier.

**2. O caso mais sério é V2 (atribuição de detector).** O critério de aceite global do projeto é "toda anomalia reportada tem evidência correspondente". Sob V2 a evidência existe e é **falsa**: aponta o detector errado. Se F5 (dashboard) fizer drill-down por detector, mostra o conjunto errado. Recomendo que este não seja aceito como risco residual mesmo que os outros quatro sejam.

**3. Corrigir a tabela de rastreabilidade em `spec.md:146-157`.** Marcar 11/11 como `Verified` contradiz este relatório. VITALS-06 deve voltar a `Needs Fix`; VITALS-04 e VITALS-07 a `Partial`. Manter como está é o único item desta iteração que afeta a **honestidade do artefato de spec**, e não só a força dos testes.

**4. Decidir sobre a divisão de contagem em `.specs/STATE.md:233`** (146+10, não 144+12). Cosmético.

---

## Fix Plans (se a quarta rodada for autorizada)

### Fix A — VITALS-06: `score` sem verificação fim a fim (V1, N7) — **Major**
- **Root cause**: `tests/vitals/test_cli_events.py:41-46` cobre `build_event` isolado; a chamada em `cli.py:118` não é coberta. `tests/integration/test_vitals_pipeline.py` não assere `score` em nenhuma linha. `tests/vitals/test_plot.py:44-49` não confere o score no título.
- **Fix**: no teste de integração, recomputar o score do detector correspondente sobre a mesma janela e asserir `meta["score"] == pytest.approx(esperado)`; **ou** asserir que `meta["score"]` é coerente com a ordenação dos scores do detector. Em `test_plot.py`, acrescentar `assert "3.70" in t` ao teste de título.
- **Verify**: reaplicar V1 (`score * 2`) e N7 (`event.score * 2`); ambos devem morrer.

### Fix B — VITALS-06: atribuição de detector não discriminada (V2) — **Major**
- **Root cause**: `tests/integration/test_vitals_pipeline.py:79` exige que os dois nomes apareçam; `:75` é tautológico (nome de arquivo e metadados derivam do mesmo `evento`). Nada amarra o rótulo ao detector que gerou a janela.
- **Fix**: rodar cada detector isoladamente (uma config por detector, ou inspecionar `verdicts`) e asserir que as evidências daquele run carregam **apenas** aquele nome; ou asserir que o conjunto de janelas rotuladas `zscore` coincide com o conjunto que `RollingZScoreDetector.flag` marca para o mesmo registro.
- **Verify**: reaplicar V2 (troca dos dois nomes) e M17; ambos devem morrer.

### Fix C — VITALS-07: canal `uc` sem amarração à proveniência (V6) — **Minor**
- **Root cause**: `tests/vitals/test_compositor.py:43-45` percorre a proveniência conferindo só `t.fhr`.
- **Fix**: dar a `uc` valores distinguíveis por registro na fixture e repetir a asserção para `t.uc[seg.start_idx:seg.end_idx]`.
- **Verify**: reaplicar V6; deve morrer.

### Fix D — VITALS-04: `seed` não provada efetiva (V7) — **Minor**
- **Root cause**: `tests/vitals/test_detectors_iforest.py:69-77` — nenhuma asserção compara `a` com `b`.
- **Fix**: `assert a != b` (verificado empiricamente como verdadeiro para `seed=1` vs `seed=999`), mantendo a asserção de determinismo. Ou remover o teste e renomear honestamente.
- **Verify**: reaplicar V7 (`random_state=0`); deve morrer.

### Fix E — Rastreabilidade divergente — **Major (honestidade do artefato)**
- **Root cause**: `spec.md:146-157` marca 11/11 `Verified`, contradizendo este relatório.
- **Fix**: VITALS-06 → `Needs Fix`; VITALS-04 e VITALS-07 → `Partial`.

### Fix F — Divisão de contagem no STATE.md — **Cosmetic**
- **Root cause**: `.specs/STATE.md:233` — "144 unitários + 12 de integração"; real é 146 + 10.

---

## Summary

**Overall**: ❌ Not Ready — **iteração 3 de 3, loop esgotado, escala para decisão humana**

**Spec-anchored check**: 9/12 ACs em escopo com desfecho da spec asserido · 1 GAP (VITALS-06) · 2 GAPs parciais (VITALS-04, VITALS-07)
**Sensor**: 13/18 mortos — 5 sobreviventes (V1, V2, V6, V7, N7)
**Gate**: 156 passed (146 unitários + 10 integração), 0 failed, 0 skipped; lint limpo — baseline do autor confirmada

**O que melhorou de verdade**: os **4 mutantes nomeados na iteração 2 morreram**, e não por acaso. A fronteira do z-score é agora um teste correto de verdade — deriva o limiar do próprio score computado, o que é a técnica certa para fronteira em ponto flutuante, e cobre os dois lados. A extração de `build_event`/`evidence_id_de` é uma boa mudança de design, não só de teste: tornou verificável o que antes só existia dentro do laço do `run()`, e os testes parametrizados sobre ela são genuínos (a parametrização de `score` inclui `99.0`, o próprio valor do mutante da iteração 2, sem que o teste seja escrito contra ele). A amarração sinal↔proveniência no `fhr` fecha uma classe estrutural de bug. As áreas nunca sondadas se saíram bem: 6 dos 7 mutantes novos em `evaluate.py`, `core/evidence.py`, `features.py` e `preprocess.py` morreram sem nenhum conserto prévio, o que indica que a suíte é sólida onde não houve reação a relatório.

**O que não melhorou**: o padrão de consertar o **alvo citado** em vez do **comportamento** sobreviveu a três iterações, só mudou de altitude — antes se escrevia contra o literal do mutante, agora se escreve contra a função nomeada no relatório. Os cinco sobreviventes estão todos um passo ao lado do que foi consertado: a **chamada** de `build_event` em vez de `build_event`; o canal **`uc`** em vez do `fhr`; a **`seed`** em vez do `contamination`. O `score` acabou a iteração **com menos cobertura fim a fim do que começou** — a asserção fraca do teste de integração saiu e nada a substituiu naquele nível, então corrompê-lo entre detector e evidência passa por duas rotas independentes. E `test_seeds_diferentes_podem_produzir_scores_diferentes` é o segundo teste consecutivo naquele arquivo cujo nome afirma uma discriminação que o corpo não faz.

**Next steps**: decisão humana sobre os 4 pontos da seção "Escalação". Recomendação do Verifier: **não** aceitar V2 como risco residual (evidência atribuída ao detector errado é evidência falsa) e corrigir a rastreabilidade em `spec.md`, que hoje afirma mais do que a evidência sustenta. Os outros três sobreviventes são defensavelmente aceitáveis para uma demo acadêmica com prazo curto, desde que a aceitação seja **registrada como decisão explícita** (AD-0xx), não deixada implícita.

**Lições a destilar** (há sinal: 5 sobreviventes + 2 testes cujo nome não corresponde ao que verificam). O Verifier só pode escrever este arquivo; o registro em `.specs/LESSONS.md` via `scripts/lessons.py add` fica para o orquestrador. Candidatas novas desta iteração:
- (f) "testar a função extraída não cobre a chamada dela: se o relatório aponta um campo, verificar o campo **no ponto de uso**, não só na unidade que o constrói";
- (g) "asserção sobre o **conjunto** de rótulos produzidos (`vistos == {a, b}`) não discrimina **permutação** — trocar dois rótulos válidos entre si preserva o conjunto; amarrar cada rótulo à sua causa";
- (h) "ao substituir uma asserção fraca por testes unitários mais fortes, verificar que o caminho fim a fim não ficou **descoberto** — cobertura pode diminuir enquanto a contagem de testes aumenta";
- (i) "quando um conserto amarra metadado a dado em um canal/campo, aplicar a mesma amarração aos canais irmãos (`fhr`→`uc`) — a lógica que diverge é a mesma";
- (j) "antes de reportar um mutante sobrevivente, confirmar empiricamente que ele **não é equivalente** (aqui: que seeds distintas de fato mudam o resultado), senão a lacuna reportada não existe".
