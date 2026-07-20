# F3 — Vitals Anomaly Validation

**Date**: 2026-07-20
**Spec**: `.specs/features/vitals-anomaly/spec.md`
**Diff range**: `480da5e..0d0275c` (branch `feat/f3-vitals-anomaly`); rodada extra = `aa63a26`
**Verifier**: independent sub-agent (author ≠ verifier) — evidence-or-zero, cobertura re-derivada da spec
**Iteração**: **rodada extra fora do loop**, autorizada explicitamente pelo usuário após o esgotamento das 3 iterações

**Veredito**: ❌ **FAIL** — mas um FAIL **substancialmente mais estreito**. 11/12 ACs em escopo com desfecho da spec asserido. Gate limpo (161/161, lint limpo). Sensor: **29 mutações, 25 mortas, 4 sobreviventes** — os 4 no mesmo arquivo (`plot.py`), com **uma única causa raiz**.

**Manchete**: os **5 sobreviventes nomeados morreram**, e as correções são genuínas — não calibradas contra o literal do mutante. As variantes vizinhas que o autor alega ter testado (`score+0.5`, `fhr` invertido, `seed=0` vs `12345`) foram re-executadas de forma independente e **todas morrem**. A alegação do autor **confere**. O padrão de "consertar só o caso nomeado" está **atenuado, não quebrado**: os 4 novos sobreviventes são o *vizinho não nomeado* — o campo `detector` do título do gráfico, **na mesma linha de código** que o autor acabou de consertar para o campo `score`.

---

## Histórico

**Iteração 1** — FAIL. 15 mutações, 9 mortas, 6 sobreviventes. Teste vacuoso; `load_mitbih_dataset` sem teste.
**Iteração 2** — FAIL. 15 mutações, 11 mortas, 4 sobreviventes. Correções calibradas **contra o literal do mutante**.
**Iteração 3** — FAIL. 18 mutações, 13 mortas, 5 sobreviventes (V1, V2, V6, V7, N7). Correções dirigidas à **função nomeada no relatório**, deixando o vizinho descoberto.
**Rodada extra (esta)** — FAIL estreito. 29 mutações, 25 mortas, 4 sobreviventes, todos em `plot.py`.

---

## Verificação das correções alegadas (commit `aa63a26`)

`aa63a26` toca **apenas testes** (`tests/conftest.py`, 4 arquivos de teste) — nenhuma linha de `src/`. Coerente com o diagnóstico da iteração 3: os 5 sobreviventes eram lacunas de teste, não bugs de implementação.

Todas as alegações re-executadas do zero, com o patch confirmado no `git diff --numstat` **antes** de julgar o resultado.

| # | Alegação do autor | Verificado? | Evidência |
| --- | --- | --- | --- |
| 1 | **V1/V2** — `_recomputa_por_detector()` como fonte de verdade independente | ✅ **Genuína, com ressalva de escopo** | `tests/integration/test_vitals_pipeline.py:82-153`. V1 (`score * 2`), V1b (`score + 0.5`) e V2 (nomes trocados) **morrem todos por este único teste**. Ressalva: é um oráculo **diferencial**, não independente — ver seção "Circularidade" |
| 2 | **N7** — título assere score e janela, e varia com o score | ✅ **Genuína** | `tests/vitals/test_plot.py:52-75`. `test_titulo_reflete_score_diferente` assere presença **e ausência** (`"8.25" in t`, `"3.70" not in t`) — technique correta. N7 (`score*2`) e N7b (`score` fixo em `0.0`) morrem |
| 3 | **V6** — proveniência nos dois canais + alinhamento FHR↔UC | ✅ **Genuína** | `tests/vitals/test_compositor.py:33-68`; `tests/conftest.py:22` acrescenta `uc_base` para tornar `uc` distinguível por registro. V6 (`uc[::-1]`) e V5 (`fhr[::-1]`) morrem, cada um por **dois** testes |
| 4 | **V7** — assere `a != b` entre seeds | ✅ **Genuína** | `tests/vitals/test_detectors_iforest.py:69-90`. `assert a != b` presente de fato; `test_a_seed_configurada_e_a_que_alimenta_o_modelo` cobre o vizinho `seed=0` vs `seed=12345`. V7 (`random_state=0`) e V7b (`random_state=12345`) morrem |
| 5 | Baseline 161 testes (150 + 11), lint limpo | ✅ **Confirmada** | Medido: `-m "not integration"` → 150 passed; `-m integration` → 11 passed; `ruff check src tests` → All checks passed |
| 6 | Rastreabilidade marcada "Fix aplicado — aguarda reverificação" | ✅ **Honesta** | `spec.md:150,152,153` — VITALS-04/06/07 marcados assim, **não** `Verified`. Corrige a divergência que a iteração 3 apontou. AD-028 `Status: active` (`.specs/STATE.md:224`), refletida em `spec.md:126,157` |

**Nenhum teste novo é vazio ou tautológico.** Os seis testes acrescentados foram auditados um a um; todos têm asserção de comportamento e todos matam pelo menos um mutante. Isto quebra a reincidência das iterações 1 e 2.

---

## Circularidade de `_recomputa_por_detector` — a questão central desta revisão

**Pergunta**: a "fonte independente" compartilha a mutação com o código sob teste, cancelando-se?

**Resposta: sim, parcialmente — mas a circularidade está fora do que o teste alega cobrir, e a área compartilhada é coberta por outros testes.**

`_recomputa_por_detector` (`test_vitals_pipeline.py:82-115`) reimporta e reexecuta `load_dataset`, `_limpa`, `make_windows`, `extract`, `detector.flag` e `detector.score` — os **mesmos** símbolos que `run()` usa. Testei explicitamente mutando código desse caminho compartilhado e rodando **só o nó do teste novo**:

| Mutação em caminho compartilhado | Só o teste novo | Suíte completa |
| --- | --- | --- |
| C1 — `make_windows`: `n_passo` → `n_passo * 2` | ⚠️ "falhou", mas **por artefato** (ver abaixo) | ✅ Morto (5 testes, incl. 3 em `test_windowing.py`) |
| C2 — `features.extract`: `mean` → `mean * 1.5` | ❌ **SOBREVIVEU** — cancelou nos dois lados | ✅ Morto — `test_features.py::test_estatisticas_basicas_de_janela_normal` |
| C3 — `windowing`: `start_s` → `start_s + 1.0` | ❌ **SOBREVIVEU** — cancelou nos dois lados | ✅ Morto — 2 testes em `test_windowing.py` |

C2 e C3 confirmam a circularidade de forma limpa: a mutação atinge os dois lados da comparação e o teste passa.

**C1 merece correção de leitura**: o nó *falhou*, mas não por detectar a mutação. Falhou em `assert set(obtido) == set(esperado)` com `{'isolation_forest'} == {'isolation_forest','zscore'}`. Causa: `esperado[det.name]` é criado **incondicionalmente** (`:107`), mesmo quando o detector sinaliza zero janelas, enquanto `obtido` só ganha a chave se houver evidência. Verifiquei empiricamente: com stride 10 s o zscore sinaliza 2 janelas; com 20 s sinaliza 0. Ou seja, C1 foi morto por uma **fragilidade do teste**, não pelo oráculo.

**Por que isso não invalida o teste**: o que ele alega provar — que a evidência carrega o detector que a produziu e o score que o detector emitiu — depende de código que o oráculo **não** compartilha: o call site `build_event(limpo, detector.name, janela, score)` (`cli.py:118`), o laço por detector, `evidence_id_de` e `save_evidence`. É um **oráculo diferencial** sobre a fiação do CLI, e para essa fiação ele discrimina de verdade: V1, V1b, V2, W2 e W6 morrem por ele. A área compartilhada tem cobertura própria em `test_windowing.py` e `test_features.py` (C1, C2, C3 mortos na suíte).

**Veredito sobre o ponto 3 do briefing**: o teste **não é circular no que importa** e **não é** "vale nada". Mas a docstring (`:84-88`) o vende como "fonte de verdade independente", o que é **mais forte do que ele é**. Descrição correta: fonte diferencial que isola a fiação do CLI. Além disso carrega duas fragilidades latentes (não-bugs hoje): a chave incondicional em `esperado`, e os parâmetros `threshold=3.0`/`contamination=0.1`/`seed=42` fixados em código (`:104-106`) que só coincidem com `cfg` por serem os defaults de `core/config.py:19-22`.

---

## Discrimination Sensor — rodada extra

**Profundidade**: P0-full — **29 mutações**: 9 re-execuções dos sobreviventes + vizinhos alegados, 3 sondas de circularidade, 17 em vizinho-do-vizinho.

**Protocolo**: harness que (a) exige que o padrão case **exatamente uma vez** no arquivo, (b) confirma `git diff --numstat` não vazio **antes** de rodar os testes — um patch que não aplica produziria um falso "morto" —, (c) roda a suíte, (d) reverte com `git checkout --`. **Nenhuma das 29 reportou `PATCH-FAILED`**; todas estavam de fato no arquivo quando os testes rodaram.

### A — Os 5 sobreviventes da iteração 3 e os vizinhos alegados pelo autor

| # | Arquivo:linha | Mutação | Iter. 3 | Rodada extra |
| --- | --- | --- | --- | --- |
| V1 | `cli.py:118` | `score` → `score * 2` no call site | ❌ | ✅ **Morto** — `test_evidencia_corresponde_as_janelas_que_aquele_detector_marcou` |
| V1b | `cli.py:118` | `score` → `score + 0.5` (vizinho alegado) | — | ✅ **Morto** — mesmo teste |
| V2 | `cli.py:118` | nomes de detector trocados entre si | ❌ | ✅ **Morto** — mesmo teste |
| N7 | `plot.py:23` | `score {event.score * 2:.2f}` | ❌ | ✅ **Morto** — 2 testes |
| N7b | `plot.py:23` | `score` fixo em `0.0` | — | ✅ **Morto** — 2 testes |
| V6 | `compositor.py:85` | `uc_partes[::-1]` | ❌ | ✅ **Morto** — 2 testes |
| V5 | `compositor.py:84` | `fhr_partes[::-1]` (vizinho alegado) | ✅ | ✅ **Morto** — 3 testes |
| V7 | `detectors.py:134` | `random_state=0` | ❌ | ✅ **Morto** — 2 testes |
| V7b | `detectors.py:134` | `random_state=12345` (vizinho alegado) | — | ✅ **Morto** — 2 testes |

**9/9 mortos.** A alegação do autor de que rodou os 5 mutantes mais as variantes vizinhas e todos morreram **confere integralmente**.

### B — Sondas de circularidade

| # | Mutação | Nó isolado | Suíte |
| --- | --- | --- | --- |
| C1 | `make_windows` stride `* 2` | ⚠️ artefato | ✅ Morto |
| C2 | `extract` `mean * 1.5` | ❌ Sobreviveu (cancelou) | ✅ Morto |
| C3 | `windowing` `start_s + 1.0` | ❌ Sobreviveu (cancelou) | ✅ Morto |

**3/3 mortos na suíte.** Circularidade real, confinada ao caminho compartilhado, coberta em outro lugar.

### C — Vizinho-do-vizinho (as sondas pedidas no briefing + extensões)

| # | Arquivo | Mutação | Killed? |
| --- | --- | --- | --- |
| W1 | `cli.py:59` | `end_s` → `end_s + 1.0` no `build_event` | ✅ Morto — `test_cli_events.py::test_janela_e_preservada` |
| W2 | `cli.py:58` | `start_s` → `start_s + 1.0` no `build_event` | ✅ Morto — 3 testes |
| W3 | `cli.py:49` | `_proveniencia` devolve sempre `record.record_id` | ✅ Morto — 3 testes |
| W4 | `cli.py:71` | `evidence_id_de` omite o detector | ✅ Morto — 3 testes |
| W5 | `core/evidence.py:70` | `save_evidence` grava `source_record_id` fixo | ✅ Morto — 4 testes |
| W6 | `windowing.py:52-53` | `fhr`/`uc` trocados entre si no `Window` | ✅ Morto — 2 testes de integração |
| W7 | `preprocess.py:69` | `interpolate_gaps` devolve a máscara antiga | ✅ Morto — `test_gap_curto_e_interpolado_e_deixa_de_ser_invalido` |
| W8 | `aggregate.py:51` | denominador `len(window_flags)` | ✅ Morto — `test_janelas_invalidas_ficam_fora_do_denominador` |
| W9 | `plot.py:22` | **`{event.detector}` → literal `zscore` no título** | ❌ **SOBREVIVEU** — 161 passed |
| W10 | `compositor.py:78` | `end_idx` off-by-one no `Segment` | ✅ Morto — 3 testes |
| W11 | `detectors.py:134` | `contamination=self.contamination` → `0.1` | ✅ Morto — `test_contamination_e_configuravel…` |
| W12 | `cli.py:126` | `source_record_id=record.record_id` no `save_evidence` | ✅ Morto — 2 testes de timeline |
| W9b | `plot.py:22` | detector **permutado** (`zscore`↔`isolation_forest`) | ✅ Morto — `test_titulo_identifica_registro_ph_e_detector` |
| W13 | `plot.py:21` | **`{record.record_id}` → literal `1464`** | ❌ **SOBREVIVEU** — 161 passed |
| W14 | `plot.py:21` | **`{record.ph:.2f}` → literal `7.01`** | ❌ **SOBREVIVEU** — 161 passed |
| W15 | `plot.py:45` | **`axvspan(event.start_s, …)` → `axvspan(0.0, …)`** | ❌ **SOBREVIVEU** — 161 passed |
| W16 | `plot.py:26` | condicional de proveniência → `if False` | ✅ Morto — `test_titulo_mostra_proveniencia_quando_difere_do_registro` |

**13/17 mortos.** Todas as sondas nomeadas no briefing morreram. Todos os 4 sobreviventes estão em `plot.py`.

**Resultado global**: **25/29 mortos, 4 sobreviventes** (W9, W13, W14, W15) → ❌ **FAIL**.

Árvore de trabalho após o sensor: `git status --short` vazio, `git stash list` vazio, `git diff HEAD` vazio. Gate re-executado depois da reversão: 150 + 11 passed, lint limpo.

### Diagnóstico: uma causa raiz, quatro sintomas

`tests/vitals/test_plot.py` tem **um único par de fixtures** (`_registro` em `:12-20`, `_evento` em `:23-31`) com valores literais fixos: `record_id="1464"`, `ph=7.01`, `detector="zscore"`. Todos os testes de título asserem **presença de substring** (`assert "zscore" in t`). Consequência estrutural: **qualquer campo do título pode ser substituído pelo seu próprio literal da fixture e a suíte não percebe.** É o mesmo defeito que a iteração 2 diagnosticou como "asserção calibrada contra o literal", agora do lado da *fixture* em vez do lado da *asserção*.

**W9 é o mais sério e é Major.** O título do gráfico é o outro lugar, além do sidecar, onde o usuário lê qual detector produziu a anomalia. `cli.py:121` chama `plot_anomaly_window` para **todo** evento, incluindo os do `isolation_forest` — confirmado: no cenário de integração o zscore sinaliza 2 janelas e o IsolationForest 6. Com W9 aplicado, **todo PNG de evidência do IsolationForest é rotulado "zscore"** e nada falha. Isto é exatamente a classe de bug de V2 — evidência atribuída ao detector errado — apenas relocada do metadado para o artefato visual. O critério de aceite global do projeto é "toda anomalia reportada tem evidência correspondente"; um gráfico que nomeia o detector errado é evidência **falsa**. A iteração 3 recomendou explicitamente conferir o score no título "o outro lugar onde o número aparece para o usuário"; o autor implementou isso para o `score` e não generalizou para o `detector`, que está **na mesma f-string, um campo à esquerda**.

Note o contraste diagnóstico entre W9 e W9b: a **permutação** morre (porque o teste assere `"zscore" in t` e a permutação remove "zscore"), mas o **colapso para a constante** sobrevive. É a situação inversa da de V2, e mostra que a asserção de substring só detecta ausência do literal da fixture, nunca ligação ao dado.

**W13/W14** (record_id e pH fixos no título) — **Minor**, mesma causa raiz, nunca sondados em nenhuma iteração anterior.
**W15** (região destacada do gráfico ignora `start_s`) — **Minor**. O conteúdo do PNG nunca é inspecionado; os testes verificam existência e tamanho do arquivo. Defensável como escopo (verificar pixels é caro), mas significa que a janela destacada pode estar errada sem detecção.

---

## Spec-Anchored Acceptance Criteria

Escopo: 12 ACs (13 originais − VITALS-11 AC2, fora de escopo por AD-028).

### P1 — Detecção sobre CTU-UHB com ground truth real

| Criterion (WHEN X THEN Y) | Desfecho definido pela spec | `arquivo:linha` + asserção | Result |
| --- | --- | --- | --- |
| AC1 / VITALS-01 — carregar WFDB ⇒ FHR, UC e pH | séries + pH presentes | `tests/vitals/test_loader.py:15` — `r.ph == 7.26`; `:16-18` — `r.fhr.shape == (240,)`, `r.fs == 4.0` | ✅ PASS |
| AC2 / VITALS-02 — pH < 7.05 ⇒ patológico | limiar 7.05, comparação estrita | `tests/vitals/test_loader_ph.py:45,49,54,58` — `PH_THRESHOLD == 7.05`, `is_pathological(7.04) is True`, `(7.05) is False` | ✅ PASS |
| AC3 / VITALS-03 — z-score, limiar configurável, comparação estrita (`spec.md:47`) | valor igual ao limiar NÃO dispara | `tests/vitals/test_detectors_zscore.py:85` — `no_limiar.flag(serie)[-1] is False` com threshold derivado bit a bit; `:86` lado oposto | ✅ PASS |
| AC4 / VITALS-04 — IsolationForest: score por janela **e** binário com limiar configurável | score + binário sensíveis aos parâmetros declarados | score `test_detectors_iforest.py:43`; binário `:51`; `contamination` `:54-61` (W11 morto); **`seed` `:69-90`** — `assert a != b` (V7, V7b mortos) | ✅ **PASS** — era GAP parcial; fix genuíno |
| AC5 / VITALS-05 — agregar por registro, comparar ao pH, P/R/F1 em JSON/CSV | fração `> τ` (AD-027); indeterminado fora do denominador | `test_aggregate.py:30-31,45-48` (W8 morto); `test_evaluate.py:43-48`; `test_vitals_pipeline.py:40-43` | ✅ PASS |
| AC6 / VITALS-06 — anomalia ⇒ gráfico + metadados (record_id, timestamp, pH, **score**, **detector**) | os 5 campos com os valores corretos | Sidecar: `test_vitals_pipeline.py:143-153` amarra **score** e **conjunto de janelas** ao detector que os produziu (V1, V1b, V2 mortos); `:66-71` record_id/pH/proveniência. Título: `test_plot.py:52-75` cobre **score** e janela. **Mas o campo `detector` do título aceita constante (W9); `record_id` e `pH` do título idem (W13, W14)** | ⚠️ **GAP parcial** — sidecar totalmente coberto; **artefato visual verifica só o score** |

### P2 — Compositor de timeline

| Criterion | Desfecho definido pela spec | `arquivo:linha` + asserção | Result |
| --- | --- | --- | --- |
| AC1 / VITALS-07 — concatenar na ordem declarada, timestamps contínuos, proveniência preservada | cada trecho do sinal atribuído ao registro real de origem | **Ambos os canais**: `test_compositor.py:52-56` amarra `t.fhr[fatia]` **e** `t.uc[fatia]` à proveniência; `:59-68` alinhamento FHR↔UC; contiguidade `:87-90` (W10 morto) | ✅ **PASS** — era GAP parcial; V5 e V6 mortos |
| AC2 — taxas diferentes ⇒ resample documentado | taxa de destino = a do primeiro registro | `test_compositor.py:145-147` — `t.fs == 4.0`, trecho de 8 Hz vira 20 amostras | ✅ PASS |
| AC3 — timeline pelos mesmos detectores ⇒ evidências sinalizando a transição | evidências atribuídas ao trecho certo | `test_vitals_timeline.py:63-67,85` (W3, W12 mortos); `test_cli_events.py:70-80` | ✅ PASS |
| AC4 — mesma config ⇒ mesma timeline | séries e proveniência idênticas | `test_compositor.py:116-118`; `test_vitals_pipeline.py:125` — `a == b` | ✅ PASS |

### P3 — MIT-BIH (opcional)

| Criterion | Desfecho definido pela spec | `arquivo:linha` + asserção | Result |
| --- | --- | --- | --- |
| AC1 / VITALS-11 — carregar MIT-BIH ⇒ ECG + anotações como rótulo real | série + símbolos; batimentos anômalos contados | `tests/vitals/test_mitbih.py:33-36,45-46` | ✅ PASS |
| AC2 — evidências no mesmo formato do CTU-UHB | — | **FORA DE ESCOPO** por AD-028 (`.specs/STATE.md:222-227`, `Status: active`), refletido em `spec.md:126,157` | ⊘ Descopado — re-confirmado válido |
| AC3 — dataset ausente ⇒ pular sem interromper o pipeline CTU-UHB | lista vazia, log claro, P1/P2 seguem | `tests/vitals/test_mitbih.py:80-82,85-93,96-101` | ✅ PASS |

**Status**: **11/12 ✅ · 1 ⚠️ GAP parcial** (VITALS-06, artefato visual). Era 9/12 com 3 lacunas na iteração 3.

---

## Edge Cases

| Edge case da spec | `arquivo:linha` | Result |
| --- | --- | --- |
| Registro corrompido ⇒ descartado com aviso, lote continua | `test_loader.py:59-61`; `test_vitals_pipeline.py:96-109` | ✅ |
| Taxa/duração divergente ⇒ resample antes de concatenar | `test_compositor.py:145-147` | ✅ |
| Nenhum registro patológico ⇒ alerta explícito | `test_evaluate.py:70-72`; `test_metrics.py:44-47` | ✅ |
| Janela sem pontos suficientes ⇒ "dados insuficientes" sem exceção | `test_detectors_iforest.py:93-100` | ✅ |
| Veredicto indeterminado excluído do cálculo de métricas | `test_evaluate.py::test_veredicto_indeterminado_e_excluido_do_calculo` | ✅ |
| Gap curto interpolado / gap longo permanece inválido | `test_preprocess.py::test_gap_longo_permanece_invalido`; `::test_gap_curto_e_interpolado…` (W7 morto) | ✅ |

---

## Gate Check

- **Comando (Build)**: `make lint && pytest -q`
- **Lint**: `.venv/bin/python -m ruff check src tests` → `All checks passed!`
- **Unitários**: `-m "not integration"` → **150 passed, 11 deselected** (4,8 s)
- **Integração**: `-m integration` → **11 passed, 150 deselected** (25,7 s)
- **Total**: **161 passed, 0 failed, 0 skipped**
- **Baseline alegada pelo autor (150 + 11 = 161)**: ✅ **confirmada exatamente**
- **Contagem na iteração 3**: 156 (146 + 10) — **delta: +5 testes** (4 novos unitários, 1 novo de integração), nenhum removido
- **Integridade**: nenhuma asserção enfraquecida. `test_seeds_diferentes_podem_produzir_scores_diferentes` foi **fortalecida** (ganhou `assert a != b`) e renomeada para `…produzem…`; `test_conteudo_de_cada_trecho…` ganhou o canal `uc`. O caminho fim a fim do `score`, que a iteração 3 apontou como **perdido** na refatoração, foi **restaurado com força maior** do que tinha originalmente
- **Skips**: nenhum · **Falhas**: nenhuma
- **Reexecução pós-sensor**: idêntica (150 + 11, lint limpo) — árvore restaurada corretamente

---

## Code Quality

| Princípio | Status |
| --- | --- |
| Código mínimo, sem features além do pedido | ✅ — `aa63a26` não toca `src/` |
| Sem abstrações para uso único | ✅ — `_recomputa_por_detector` é helper local de um teste, apropriado |
| Sem "flexibilidade" desnecessária | ✅ |
| Só tocou arquivos exigidos | ✅ — 4 arquivos de teste + `conftest.py` |
| Não "melhorou" código não relacionado | ✅ — `uc_base` no conftest tem default `20.0`, preservando fixtures existentes |
| Segue padrões/estilo existentes | ✅ |
| Um engenheiro sênior aprovaria? | ⚠️ Os testes novos são de boa qualidade — asserção de presença **e** ausência, vizinho coberto, docstrings explicando a motivação. Ressalva: a docstring de `_recomputa_por_detector` afirma independência que o helper não tem |
| Testes mapeiam ACs e não são rasos | ✅ — **nenhum teste vacuoso nesta rodada**, quebrando a reincidência das iterações 1 e 2. Todos os 6 testes novos matam ao menos um mutante |
| Spec-anchored: valor asserido = desfecho da spec | ⚠️ 1 lacuna (VITALS-06, campos `detector`/`record_id`/`pH` do título) |
| Coverage Expectation por camada | ✅ — 13/17 vizinho-do-vizinho mortos; `cli`, `evidence`, `aggregate`, `preprocess`, `windowing`, `compositor` sólidos |
| Todo teste mapeia a um AC / edge case / Done-when | ✅ |
| Guidelines documentadas seguidas | ✅ "nenhuma — defaults fortes aplicados" |

---

## Requirement Traceability Update

A tabela em `spec.md:146-158` marca VITALS-04/06/07 como **"Fix aplicado — aguarda reverificação"**, não `Verified`. **Isso é honesto** e corrige a divergência apontada na iteração 3. Resultado da reverificação:

| Requirement | Iteração 3 | Rodada extra (re-derivado) | `spec.md` diz | Ação |
| --- | --- | --- | --- | --- |
| VITALS-01 | ✅ Verified | ✅ Verified | Verified | — |
| VITALS-02 | ✅ Verified | ✅ Verified | Verified | — |
| VITALS-03 | ✅ Verified | ✅ Verified | Verified | — |
| VITALS-04 | ⚠️ Parcial | ✅ **Verified** — V7 e V7b mortos, `assert a != b` real | Fix aplicado — aguarda reverif. | → `Verified` |
| VITALS-05 | ✅ Verified | ✅ Verified | Verified | — |
| VITALS-06 | ❌ Needs Fix | ⚠️ **Parcial** — sidecar totalmente coberto (V1, V1b, V2 mortos); **título do gráfico verifica só o `score`** (W9, W13, W14) | Fix aplicado — aguarda reverif. | → `Partial` |
| VITALS-07 | ⚠️ Parcial | ✅ **Verified** — V5 e V6 mortos, ambos os canais amarrados | Fix aplicado — aguarda reverif. | → `Verified` |
| VITALS-08 | ✅ Verified | ✅ Verified | Verified | — |
| VITALS-09 | ✅ Verified | ✅ Verified | Verified | — |
| VITALS-10 | ✅ Verified | ✅ Verified | Verified | — |
| VITALS-11 | ✅ Verified | ✅ Verified — AC1/AC3; AC2 descopado por AD-028 (ativa, refletida) | Verified | — |

**AD-028**: ✅ `Status: active` em `.specs/STATE.md:224`, coerente com o strikethrough em `spec.md:126` e a linha de rastreabilidade `:157`. Rebaixamento re-confirmado válido.

---

## Fix Plans

### Fix A — VITALS-06: o título do gráfico não amarra `detector` ao evento (W9) — **Major**

- **Root cause**: `tests/vitals/test_plot.py:23-31` — a fixture `_evento` usa sempre `detector="zscore"`, e `test_titulo_identifica_registro_ph_e_detector:49` assere `"zscore" in t`. Substituir `{event.detector}` pelo literal `"zscore"` em `plot.py:22` satisfaz a asserção. No pipeline real o IsolationForest gera 6 das 8 evidências do cenário de integração; todas ficariam rotuladas "zscore" no PNG.
- **Fix**: parametrizar o teste de título por detector, ou acrescentar o teste vizinho no molde do que já existe para o score — `titulo_evidencia` com `detector="isolation_forest"` deve conter `"isolation_forest"` **e não conter** `"zscore"`. O padrão `assert X in t and Y not in t` de `test_titulo_reflete_score_diferente:74-75` já está no arquivo e é o correto; basta replicá-lo.
- **Verify**: reaplicar W9 (`{event.detector}` → literal `zscore`); deve morrer.

### Fix B — VITALS-06: `record_id` e `pH` do título idem (W13, W14) — **Minor**

- **Root cause**: mesma causa raiz do Fix A — fixture única com literais `"1464"` e `7.01`.
- **Fix**: no mesmo teste parametrizado, variar `record_id` e `ph` e asserir presença do novo valor **e ausência do antigo**.
- **Verify**: reaplicar W13 e W14; ambos devem morrer.

### Fix C — Região destacada do gráfico não verificada (W15) — **Minor**

- **Root cause**: nenhum teste inspeciona o conteúdo do PNG; `plot.py:45` (`axvspan`) pode ignorar `event.start_s` sem detecção.
- **Fix**: extrair as fronteiras do destaque para um helper puro testável (no molde de `titulo_evidencia`), ou asserir sobre o objeto `Axes` retornado. Alternativa legítima: **aceitar como risco residual documentado**, já que verificar pixels é desproporcional.
- **Verify**: reaplicar W15; deve morrer (ou registrar a aceitação como AD).

### Fix D — Higiene de `_recomputa_por_detector` — **Cosmetic**

- **Root cause**: `test_vitals_pipeline.py:107` cria `esperado[det.name]` incondicionalmente, então `set(obtido) == set(esperado)` (`:141`) falha em falso sempre que um detector legitimamente sinaliza zero janelas. Passa hoje só porque a fixture garante ≥1 para ambos. Além disso `:104-106` fixa `threshold=3.0`/`contamination=0.1`/`seed=42`, que coincidem com `cfg` apenas por serem os defaults de `core/config.py:19-22`.
- **Fix**: omitir do `esperado` os detectores sem janelas sinalizadas; derivar os parâmetros do mesmo dicionário que alimenta `_config`. Ajustar a docstring `:84-88`: é oráculo **diferencial** sobre a fiação do CLI, não fonte independente.

---

## Summary

**Overall**: ⚠️ **Issues** — FAIL estreito, de causa raiz única e confinada a `plot.py`

**Spec-anchored check**: **11/12** ACs em escopo com desfecho da spec asserido (era 9/12) · 1 GAP parcial (VITALS-06, artefato visual)
**Sensor**: **25/29 mortos** — 4 sobreviventes (W9, W13, W14, W15), todos em `plot.py`, todos com a mesma causa
**Gate**: 161 passed (150 unitários + 11 integração), 0 failed, 0 skipped; lint limpo — baseline do autor confirmada exatamente

**O que melhorou de verdade**: pela primeira vez em quatro rodadas, **as correções alegadas conferem integralmente sob verificação independente**. Os 5 sobreviventes morreram, e não por asserção calibrada contra o literal: V1 morre tanto com `score*2` quanto com `score+0.5`; V7 morre tanto com `random_state=0` quanto com `12345`; V6 e V5 morrem cada um por dois testes distintos. **Nenhum teste novo é vacuoso ou tautológico** — a reincidência das iterações 1 e 2 está quebrada. `test_titulo_reflete_score_diferente` usa a técnica correta (presença **e** ausência), e o autor a aplicou por iniciativa própria. O caminho fim a fim do `score`, que a iteração 3 apontou ter **perdido** cobertura na refatoração, voltou mais forte do que era originalmente. As 12 sondas de vizinho-do-vizinho nomeadas no briefing — `start_s`/`end_s`, `_proveniencia`, `evidence_id_de`, `save_evidence`, troca `fhr`/`uc`, `interpolate_gaps`, denominador do `aggregate` — **morreram todas**, o que indica que a suíte é sólida onde não houve reação a relatório. E a rastreabilidade em `spec.md` está **honesta**: "Fix aplicado — aguarda reverificação", não `Verified`, corrigindo exatamente o que a iteração 3 cobrou.

**Sobre a circularidade de `_recomputa_por_detector`** (ponto central do briefing): a suspeita **procede em parte, mas não invalida o teste**. Mutando `extract` e `windowing.start_s` — código que os dois lados compartilham — o teste novo passa: a mutação se cancela. Porém o que ele alega provar (fidelidade de detector e de score entre o que o detector emitiu e o que a evidência gravou) depende do call site em `cli.py:118`, que o oráculo **não** compartilha, e ali ele discrimina de verdade — V1, V1b, V2, W2 e W6 morrem por ele. A área compartilhada tem cobertura própria (C1, C2, C3 mortos na suíte). Conclusão: **oráculo diferencial legítimo, vendido pela docstring como mais do que é.**

**O que não melhorou**: o padrão está **atenuado, não quebrado**. O autor cobriu o caso nomeado **e** todos os vizinhos que lhe foram nomeados — `score+0.5`, `fhr` invertido, `seed 0 vs 12345` estavam listados no próprio briefing da rodada. O que continua descoberto é o vizinho **que ninguém nomeou**: ao consertar o `score` do título do gráfico (N7), o autor não olhou para o campo `detector`, que está **na mesma f-string de `plot.py:22`, um campo à esquerda** — e que é a mesma classe de bug que V2, pela qual ele acabara de ser reprovado. Colapsar `{event.detector}` para a constante `"zscore"` faz todo PNG do IsolationForest mentir sobre sua origem e passa nos 161 testes. A causa raiz é estrutural e não foi tocada em nenhuma das quatro rodadas: `test_plot.py` tem **uma única fixture com literais fixos** e assere só presença de substring, então qualquer campo do título pode ser trocado pelo próprio literal da fixture sem consequência.

**Next steps**: Fix A é o único bloqueador real e é pequeno — replicar em `test_plot.py` o padrão `assert X in t and Y not in t` que o próprio autor já escreveu para o score, agora para o detector. Fixes B e C saem de graça na mesma parametrização. Recomendação do Verifier: **corrigir A e B** (o custo é um teste parametrizado), **aceitar C como risco residual documentado** via AD, e aplicar Fix D como higiene. Feito isso, VITALS-06 fecha e F3 está pronta. Se houver pressão de prazo (27/07/2026), A é o único que não deve ser dispensado: evidência visual que nomeia o detector errado é evidência falsa, o mesmo argumento que a iteração 3 usou para recusar V2 como risco aceitável.

**Lições a destilar** (há sinal: 4 sobreviventes de causa raiz única). O Verifier só pode escrever este arquivo; o registro em `.specs/LESSONS.md` via `scripts/lessons.py add` fica para o orquestrador. Candidatas desta rodada:
- (k) "fixture com valor literal único torna indetectável a substituição do campo pelo próprio literal — variar o valor entre dois testes é o que amarra a saída ao dado de entrada";
- (l) "asserção de **presença** de substring (`X in saida`) detecta permutação mas não colapso para constante; parear com **ausência** (`Y not in saida`) fecha os dois lados";
- (m) "ao consertar um campo de uma string/estrutura formatada, cobrir **todos os campos da mesma expressão** — eles compartilham o mesmo modo de falha";
- (n) "um oráculo de teste que reexecuta o código sob teste é **diferencial**, não independente: mutações no caminho compartilhado se cancelam. Vale pela fiação que ele isola — descrever seu escopo com precisão e cobrir o caminho compartilhado em outro lugar";
- (o) "verificar que uma chave de dicionário esperado é criada condicionalmente: chave incondicional transforma comparação de conjuntos em falso negativo/positivo dependente da fixture".
