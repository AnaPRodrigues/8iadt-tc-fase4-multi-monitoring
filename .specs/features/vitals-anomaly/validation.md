# F3 — Vitals Anomaly Validation

**Date**: 2026-07-20
**Spec**: `.specs/features/vitals-anomaly/spec.md`
**Diff range**: `480da5e..HEAD` (branch `feat/f3-vitals-anomaly`, HEAD = `cd5be75`)
**Verifier**: independent sub-agent (author ≠ verifier) — evidence-or-zero, coverage re-derived from the spec

**Verdict**: ❌ **FAIL** — 8 de 13 ACs totalmente cobertos, 4 parciais/não cobertos, 1 lacuna de precisão da spec. Gate limpo, mas o sensor de discriminação encontrou 6 mutantes sobreviventes.

---

## Task Completion

| Task | Status | Notas |
| --- | --- | --- |
| T1–T10, T12–T17 | ✅ Done | Done-when verificados por amostragem; commits atômicos presentes |
| T11 (`IsolationForestDetector`) | ⚠️ Parcial | Done-when "limiar configurável" implementado mas **não coberto por teste** — mutante M8 sobreviveu |
| T18 (adaptador MIT-BIH) | ❌ Parcial | Done-when "Produz evidências no mesmo formato do CTU-UHB (AD-026)" **não cumprido**: `src/vitals/mitbih.py` não é referenciado por nenhum outro módulo (`grep -rn mitbih src/ tests/ Makefile configs/` só retorna o próprio módulo e seu teste). Nenhum detector, nenhuma evidência. |

---

## Spec-Anchored Acceptance Criteria

### P1 — Detecção sobre CTU-UHB com ground truth real

| Criterion (WHEN X THEN Y) | Desfecho definido pela spec | `arquivo:linha` + asserção | Result |
| --- | --- | --- | --- |
| AC1 / VITALS-01 — carregar WFDB ⇒ extrair FHR, UC e pH | séries FHR e UC + valor de pH presentes no objeto carregado | `tests/vitals/test_loader.py:15` — `assert r.ph == 7.26`; `:16-18` — `assert r.fhr.shape == (240,)`, `assert r.uc.shape == (240,)`, `assert r.fs == 4.0` | ✅ PASS |
| AC2 / VITALS-02 — pH < 7.05 ⇒ "patológico", senão "normal" | limiar exato 7.05, comparação estrita `<` | `tests/vitals/test_loader_ph.py:45` — `assert PH_THRESHOLD == 7.05`; `:49` — `assert is_pathological(7.04) is True`; `:54` — `assert is_pathological(7.05) is False`; `:58` — `assert is_pathological(7.26) is False` | ✅ PASS (fronteira asserida; mutante M3 morto) |
| AC3 / VITALS-03 — z-score ⇒ classificar janelas com limiar configurável | classificação binária que muda com o limiar | `tests/vitals/test_detectors_zscore.py:68-69` — `RollingZScoreDetector(threshold=3.0, baseline_size=5).flag(serie)[-1] is False` e `threshold=2.0 … is True`; score exato em `:54` — `assert scores[-1] == pytest.approx(5 / math.sqrt(2))` | ✅ PASS (semântica da fronteira `>` vs `>=` não definida na spec — ver ⚠️ abaixo) |
| AC4 / VITALS-04 — IsolationForest ⇒ score por janela **e** classificação binária derivada de limiar configurável | score por janela + binário sensível ao limiar configurado | score: `tests/vitals/test_detectors_iforest.py:41` — `assert scores[-1] > max(normais)`; binário: `:49` — `assert flags[-1] is True`. **Nenhum teste varia `contamination`** — todo o arquivo usa `contamination=0.1` | ⚠️ **GAP parcial** — a parte "limiar configurável" do AC não tem evidência; mutante M8 (`contamination` hardcoded) **sobreviveu** |
| AC5 / VITALS-05 — agregar janelas por registro ⇒ comparar ao pH e calcular P/R/F1 em relatório JSON/CSV | fração de janelas anômalas `> τ` (AD-027, τ=0.15); janelas `None` fora do denominador; P/R/F1 gravados | agregação: `tests/vitals/test_aggregate.py:30-31` — `anomalous_fraction == approx(0.2)` + `predicted_pathological is False` (fronteira `> τ`); `:45-48` — `n_windows_valid == 10`, `n_windows_excluded == 90`, `anomalous_fraction == approx(0.3)`; `:38` — τ default 0.15. Métricas: `tests/vitals/test_evaluate.py:43-48` — `z.precision == 1.0`, `z.recall == 1.0`, `i.precision == approx(0.5)`. Persistência: `tests/integration/test_vitals_pipeline.py:40-43` — `metrics["n_records"] == 2`, `metrics["prevalence"] == approx(0.5)`, `{m["detector"] …} == {"zscore","isolation_forest"}` | ✅ PASS (mutantes M1 e M2 mortos) |
| AC6 / VITALS-06 — anomalia detectada ⇒ gráfico + metadados (record_id, timestamp, pH, score, detector) | os 5 campos presentes **com os valores corretos** ao lado do artefato | gráfico: `tests/vitals/test_plot.py:40-41` — `assert destino.is_file()` + `st_size > 0`; título: `:47-49` — `"1464" in t`, `"7.01" in t`, `"zscore" in t`. Contrato core: `tests/core/test_evidence.py:36-40` — `sidecar["source_record_id"] == "1464"`, `metadata["detector"] == "zscore"`, `metadata["score"] == 3.7`, `metadata["ph"] == 7.01` (metadados construídos à mão no teste). **Pipeline real**: `tests/integration/test_vitals_pipeline.py:59` — `dados_side["source_record_id"] == "0001"` (valor ✅); `:61` — `assert "ph" in dados_side["metadata"]` (**presença apenas**) | ⚠️ **GAP de payload** — no payload produzido pelo pipeline, `ph`, `score` e `detector` nunca têm o **valor** asserido. Mutantes M9 (`ph` → `None`), M14 (`score` → `0.0`) e M15 (`detector` → `"desconhecido"`) **sobreviveram** |

### P2 — Compositor de timeline

| Criterion | Desfecho definido pela spec | `arquivo:linha` + asserção | Result |
| --- | --- | --- | --- |
| AC1 / VITALS-07 — concatenar na ordem declarada, timestamps contínuos sem sobreposição, proveniência preservada | trechos contíguos, cada um atribuído ao registro real de origem | `tests/vitals/test_compositor.py:40-43` — `[(s.source_record_id, s.start_idx, s.end_idx) …] == [("r0001",0,100), ("r0002",100,160)]`; `:57-60` — `seguinte.start_idx == anterior.end_idx`, `provenance[-1].end_idx == len(t.fhr)`; `:27` — `len(t.fhr) == 160` (soma exata das durações) | ✅ PASS |
| AC2 — taxas diferentes ⇒ resample para taxa comum documentada | taxa de destino = a do primeiro registro; nº de amostras convertido | `tests/vitals/test_compositor.py:115-117` — `assert t.fs == 4.0` e `t.provenance[1].end_idx - t.provenance[1].start_idx == 20` (40 amostras a 8 Hz ⇒ 20 a 4 Hz) | ✅ PASS |
| AC3 — timeline processada pelos mesmos detectores ⇒ anomalias/evidências sinalizando a transição normal→patológico | evidências ao longo da timeline atribuídas ao trecho certo | `tests/integration/test_vitals_timeline.py:40` — `assert run(cfg, run_id="tl") == 0`; `:63-66` — `assert sidecars`, `origens <= {"normal01","patol01"}`, `"timeline-demo" not in origens`; `:85` — `assert all(s["source_record_id"] == "patol01" for s in tardias)` (janelas com `start_s >= 300.0`) | ✅ PASS (mutantes M10 e M13 mortos por estes testes) |
| AC4 — mesma config ⇒ mesma timeline (determinismo) | séries e proveniência idênticas entre execuções | `tests/vitals/test_compositor.py:86-88` — `np.array_equal(a.fhr, b.fhr)`, `np.array_equal(a.uc, b.uc)`, `a.provenance == b.provenance`; ponta a ponta: `tests/integration/test_vitals_pipeline.py:107` — `assert a == b` (metrics.json de duas execuções) | ✅ PASS |

### P3 — MIT-BIH (opcional)

| Criterion | Desfecho definido pela spec | `arquivo:linha` + asserção | Result |
| --- | --- | --- | --- |
| AC1 / VITALS-11 — carregar MIT-BIH ⇒ extrair ECG + anotações de arritmia como rótulo real | série ECG + símbolos de anotação; batimentos anômalos contados | `tests/vitals/test_mitbih.py:33-36` — `r.record_id == "100"`, `r.fs == 360.0`, `r.ecg.shape == (400,)`, `len(r.annotations) == 3`; `:45-46` — `r.anomalous_beats == 1`, `r.has_anomaly is True` | ✅ PASS |
| AC2 — série MIT-BIH processada pelos detectores ⇒ anomalias e evidências **no mesmo formato do CTU-UHB** | mesmos detectores (z-score + IsolationForest) + contrato de evidência AD-026 | **nenhuma evidência — nem em teste nem em código.** `grep -rn "mitbih" src/ tests/ Makefile configs/` retorna apenas `src/vitals/mitbih.py` e `tests/vitals/test_mitbih.py`; o módulo não importa `detectors`, `features` nem `core.evidence`, e nenhum outro módulo o importa | ❌ **NÃO COBERTO / NÃO IMPLEMENTADO** |
| AC3 — dataset ausente ⇒ pular o caso sem interromper o pipeline CTU-UHB | caso pulado com log claro; P1/P2 seguem rodando | detecção de ausência: `tests/vitals/test_mitbih.py:59` — `assert mitbih_disponivel(tmp_path / "nao-existe") is False`; `:66` — diretório vazio ⇒ `False`. **`load_mitbih_dataset()` — a função que efetivamente pula e devolve `[]` — não tem nenhum teste**; e o CLI nunca a chama, então "sem interromper o CTU-UHB" é verdadeiro por vacuidade, sem asserção que o prove | ⚠️ **GAP parcial** |

---

## Edge Cases

| Edge case da spec | `arquivo:linha` + asserção | Result |
| --- | --- | --- |
| Registro corrompido/incompleto ⇒ descartado com aviso, lote continua | `tests/vitals/test_loader.py:59-61` — `sorted(r.record_id for r in registros) == ["0001","0002"]`, `sorted(f.record_id for f in falhas) == ["0003","0004"]`; log: `:78-79` — `"1" in caplog.text`, `"0003" in caplog.text`; ponta a ponta: `tests/integration/test_vitals_pipeline.py:86` — `run(...) == 0` com header ilegível no lote, `:91` — `metrics["n_records"] == 2` | ✅ |
| Taxa/duração divergente entre trechos ⇒ resample antes de concatenar | `tests/vitals/test_compositor.py:115-117` (ver P2 AC2) | ✅ |
| Nenhum registro patológico no subconjunto ⇒ alerta explícito em vez de recall zero sem contexto | `tests/vitals/test_evaluate.py:70-72` — `rel.prevalence == 0.0`, `…recall is None`, `"recall" in caplog.text.lower()`; base: `tests/core/test_metrics.py:44-47` — `r.recall is None`, `r.support == 0`, `r.precision == 0.0`, `r.f1 is None` | ✅ (mutante M4 morto) |
| Janela sem pontos suficientes para o IsolationForest ⇒ "dados insuficientes" sem exceção | `tests/vitals/test_detectors_iforest.py:71-72` — `all(s is None for s in scores)`, `d.insufficient_data is True`; `:59-62` — `scores[-1] is None`, `flags[-1] is None`, `d.n_treino == 30` | ✅ |

---

## Discrimination Sensor

**Profundidade**: P0-full (15 mutações — regra ≥5 para caminho crítico/integridade de dados). Todas aplicadas na árvore real e revertidas imediatamente com `git checkout -- <arquivo>`; `git status` final limpo.

| # | Arquivo:linha | Mutação | Killed? |
| --- | --- | --- | --- |
| M1 | `src/vitals/aggregate.py:54` | `fracao > tau` → `fracao >= tau` (fronteira AD-027) | ✅ Morto — `test_aggregate.py::test_fracao_exatamente_igual_a_tau_nao_e_patologico` |
| M2 | `src/vitals/aggregate.py:51` | denominador `len(validas)` → `len(window_flags)` (inclui janelas `None`, viola AD-027) | ✅ Morto — `test_aggregate.py::test_janelas_invalidas_ficam_fora_do_denominador` |
| M3 | `src/vitals/loader.py:49` | `ph < PH_THRESHOLD` → `ph <= PH_THRESHOLD` (fronteira VITALS-02) | ✅ Morto — `test_loader_ph.py::test_ph_exatamente_no_limiar_nao_e_patologico` |
| M4 | `src/core/metrics.py:42` | recall `None` → `0.0` sem positivos reais (viola VITALS-10) | ✅ Morto — 3 testes, incl. `test_evaluate.py::test_conjunto_sem_patologico_avisa_que_recall_e_indefinido` |
| M5 | `src/vitals/preprocess.py:60` | remove a guarda `na_borda` — passa a interpolar gaps de borda (fabricaria dado) | ✅ Morto — 3 testes, incl. `test_preprocess.py::test_sinal_todo_perdido_nao_interpola_nada` |
| M6 | `src/vitals/features.py:51` | `min_amostras = int(DECEL_MIN_S * fs)` → `1` (ignora duração mínima da deceleração) | ✅ Morto — `test_features.py::test_queda_curta_demais_nao_conta_como_deceleracao` |
| M7 | `src/vitals/windowing.py:56` | `fracao_invalida > max_invalid_fraction` → `>=` (fronteira de `insufficient_data`) | ❌ **Sobreviveu** — testes usam 25% e 75%, nunca exatamente 50% |
| M8 | `src/vitals/detectors.py:134` | `contamination=self.contamination` → `contamination=0.1` (limiar do IsolationForest deixa de ser configurável) | ❌ **Sobreviveu** — VITALS-04 exige limiar configurável e nenhum teste varia `contamination` |
| M9 | `src/vitals/cli.py:114` | `{"ph": record.ph}` → `{"ph": None}` no payload de evidência | ❌ **Sobreviveu** — a integração só assere `"ph" in metadata` |
| M10 | `src/vitals/cli.py:95` | `if not flag: continue` → `if True: continue` (nenhuma evidência é gerada) | ✅ Morto — mas **apenas** por `test_vitals_timeline.py::test_evidencia_atribui_a_anomalia_ao_registro_de_origem`. `test_vitals_pipeline.py::test_toda_evidencia_tem_artefato_e_sidecar` passou com zero evidências (teste vacuoso — itera uma lista vazia sem `assert sidecars`) |
| M11 | `src/vitals/compositor.py:87` | `ph=min(...)` → `ph=max(...)` (rótulo da timeline deixa de refletir o pior desfecho) | ✅ Morto — `test_compositor.py::test_rotulo_da_timeline_usa_o_pior_desfecho` |
| M12 | `src/vitals/detectors.py:97` | `s > self.threshold` → `s >= self.threshold` (fronteira do z-score) | ❌ **Sobreviveu** — fronteira exata nunca exercitada |
| M13 | `src/vitals/cli.py:49` | `_proveniencia` devolve sempre `record.record_id` (perde a proveniência da timeline) | ✅ Morto — 2 testes de `test_vitals_timeline.py` |
| M14 | `src/vitals/cli.py:102` | `score=float(score)` → `score=0.0` no evento de evidência | ❌ **Sobreviveu** — nenhum teste assere o valor de `score` no sidecar do pipeline |
| M15 | `src/vitals/cli.py:99` | `detector=detector.name` → `detector="desconhecido"` | ❌ **Sobreviveu** — nenhum teste assere o valor de `detector` no sidecar do pipeline |

**Resultado**: 9/15 mortos, **6 sobreviventes** (M7, M8, M9, M12, M14, M15) → ❌ FAIL.

Árvore de trabalho após o sensor: `git status --short` vazio — nenhuma mutação deixada no código.

---

## Regra de Payload (proveniência, pH, detector, score)

| Campo exigido pela spec | Asserção de **valor** existe? | Onde |
| --- | --- | --- |
| `source_record_id` (proveniência, VITALS-07) | ✅ Sim | `tests/integration/test_vitals_pipeline.py:59` — `== "0001"`; `tests/integration/test_vitals_timeline.py:85` — `== "patol01"`; `tests/core/test_evidence.py:36` — `== "1464"` |
| `ph` | ❌ Não no payload do pipeline (só presença de chave) | `tests/integration/test_vitals_pipeline.py:61` — `assert "ph" in dados_side["metadata"]`. Valor asserido apenas no contrato core com metadados fabricados (`tests/core/test_evidence.py:40`) |
| `detector` | ❌ Não no payload do pipeline | valor asserido só em `tests/core/test_evidence.py:38` (metadados fabricados) e no título do gráfico (`tests/vitals/test_plot.py:49`) |
| `score` | ❌ Não no payload do pipeline | valor asserido só em `tests/core/test_evidence.py:39` (metadados fabricados) |
| `timestamp` (`start_s`/`end_s`) | ✅ Parcial | `tests/integration/test_vitals_timeline.py:83-85` — filtra por `metadata["start_s"] >= 300.0` e assere a origem |

Conclusão: o contrato genérico de `core/evidence.py` é bem testado, mas o **conteúdo que o pipeline de F3 realmente escreve** nele não é — três mutantes de payload sobreviveram.

---

## Gate Check

- **Comando (Build)**: `make lint && pytest -q`
- **Lint**: `.venv/bin/python -m ruff check src tests` → `All checks passed!`
- **Unitários**: `.venv/bin/python -m pytest -q -m "not integration"` → **125 passed, 10 deselected**
- **Suíte completa**: `.venv/bin/python -m pytest -q` → **135 passed, 0 failed, 0 skipped** (26s)
- **Contagem antes da feature**: 0 (projeto greenfield; `480da5e` é o esqueleto) — **delta: +135**
- **Skips**: nenhum
- **Falhas**: nenhuma

> Nota de integridade: o `STATE.md` (linha 225) registra "129 unitários + 6 de integração". A composição real é **125 unitários + 10 de integração**. Total confere (135); a quebra por tipo está incorreta.

---

## Code Quality

| Princípio | Status |
| --- | --- |
| Código mínimo, sem features além do pedido | ✅ |
| Sem abstrações para uso único | ✅ (o `Detector` Protocol é usado por 2 implementações) |
| Sem "flexibilidade" desnecessária | ✅ |
| Só tocou arquivos exigidos pelas tarefas | ✅ |
| Não "melhorou" código não relacionado | ✅ |
| Segue padrões/estilo existentes | ✅ (docstrings em PT-BR, dataclasses frozen, logging via `core.logging` — consistente em todos os módulos) |
| Um engenheiro sênior aprovaria? | ⚠️ Com ressalvas — o código é sólido e bem documentado nas decisões (`SPEC_DEVIATION` explícitos, comentários justificando `>` estrito e `None` vs `0.0`); as ressalvas são de **teste**, não de implementação, exceto o MIT-BIH incompleto |
| Testes mapeiam ACs e não são rasos | ⚠️ 1 teste vacuoso identificado (`test_toda_evidencia_tem_artefato_e_sidecar` — sem `assert sidecars`) |
| Spec-anchored: valor asserido = desfecho da spec | ⚠️ 4 lacunas (VITALS-04 limiar, payload `ph`/`score`/`detector`) |
| Coverage Expectation por camada (domínio 1:1 com ACs; orquestração happy+edge+erro) | ⚠️ Domínio quase 1:1; `src/vitals/mitbih.py::load_mitbih_dataset` sem teste |
| Todo teste mapeia a um AC / edge case / Done-when (sem testes órfãos) | ✅ |
| Guidelines documentadas seguidas | ✅ "nenhuma — defaults fortes aplicados" (declarado na Test Coverage Matrix de `tasks.md`) |

**Desvios de spec declarados no código** (todos com justificativa explícita, nenhum silencioso):
`src/core/evidence.py:7`, `src/vitals/preprocess.py:7`, `src/vitals/windowing.py:3`, `src/vitals/detectors.py:3`, `src/vitals/evaluate.py:3`. Cada um altera uma assinatura do design por necessidade técnica real (genericidade do `core`, `fs` faltando, máscara faltando, `None` vs `0.0`, prevalência fora do `MetricsReport`). Nenhum contradiz a spec — mas o `design.md` não foi atualizado para refleti-los.

---

## Fix Plans

### Fix 1 — VITALS-11 / P3 AC2: MIT-BIH não é processado pelos detectores nem gera evidência
- **Root cause**: `src/vitals/mitbih.py` só carrega e conta batimentos; não extrai features, não chama `RollingZScoreDetector`/`IsolationForestDetector` e não usa `core.evidence`. Nenhum módulo o importa. O Done-when de T18 ("Produz evidências no mesmo formato do CTU-UHB (AD-026)") não foi cumprido.
- **Fix task**: (a) adaptar o ECG ao caminho `windowing → features → detectors` e emitir `AnomalyEvent`/`save_evidence` com `feature="vitals"`; (b) teste unitário asserindo que o sidecar gerado tem as mesmas chaves e tipos do sidecar do CTU-UHB. **Ou** — se o grupo decidir manter P3 fora do escopo por tempo (o brief permite: "opcional, não bloqueante") — rebaixar explicitamente VITALS-11 na spec para "carga + skip apenas", registrando a decisão como AD, e marcar o AC2 como descartado em vez de pendente.
- **Prioridade**: Major (P3 opcional, mas o AC está na spec como escrito e a tarefa foi marcada ✅ Concluída)

### Fix 2 — VITALS-06: valores de `ph`, `score` e `detector` no payload de evidência do pipeline
- **Root cause**: `tests/integration/test_vitals_pipeline.py:61` verifica presença de chave, não valor. Mutantes M9/M14/M15 sobrevivem.
- **Fix task**: em `test_toda_evidencia_tem_artefato_e_sidecar`, asserir `dados_side["metadata"]["ph"] == 7.01`, `dados_side["metadata"]["detector"] in {"zscore","isolation_forest"}` e `dados_side["metadata"]["score"] != 0.0` (ou `> 0`, coerente com a semântica "maior = mais anômalo"). **Verify**: reaplicar M9, M14 e M15 e confirmar que morrem.
- **Prioridade**: Major (é o critério de aceite global do projeto: "toda anomalia reportada tem evidência correspondente")

### Fix 3 — Teste vacuoso de evidência
- **Root cause**: `tests/integration/test_vitals_pipeline.py:55-61` itera `sidecars` sem antes garantir que a lista não está vazia; o teste passa mesmo se o pipeline não gerar evidência alguma (comprovado por M10).
- **Fix task**: adicionar `assert sidecars, "o pipeline deve produzir ao menos uma evidência"` antes do laço — o mesmo padrão já usado em `test_vitals_timeline.py:63`.
- **Prioridade**: Major

### Fix 4 — VITALS-04: limiar configurável do IsolationForest sem cobertura
- **Root cause**: todo `tests/vitals/test_detectors_iforest.py` usa `contamination=0.1`; nada prova que o parâmetro afeta a classificação (M8 sobrevive).
- **Fix task**: teste espelhando `test_detectors_zscore.py:65-69` — mesma série, dois valores de `contamination` (ex.: 0.05 e 0.4), asserindo que o conjunto de janelas marcadas difere. **Verify**: M8 passa a morrer.
- **Prioridade**: Major

### Fix 5 — `load_mitbih_dataset()` sem teste (VITALS-11 AC3)
- **Root cause**: a função que implementa o skip gracioso (devolve `[]` e loga) nunca é exercitada; só `mitbih_disponivel()` é.
- **Fix task**: teste asserindo `load_mitbih_dataset(tmp_path / "nao-existe") == []` e que o log contém "pulado"; e um teste com dataset presente asserindo `len(...) == 1`.
- **Prioridade**: Minor

### Fix 6 — Fronteiras não definidas pela spec (lacuna de precisão da spec)
- **Root cause**: a spec não define se a comparação com o limiar do z-score (VITALS-03) e com `max_invalid_fraction` (VITALS-09) é estrita ou inclusiva. O código usa `>` estrito em ambos, coerente com AD-027, mas nenhum teste fixa a fronteira (M7 e M12 sobrevivem).
- **Fix task**: registrar na spec (ou como AD) que **todos** os limiares de F3 usam comparação estrita `>`, e adicionar um teste de fronteira para cada — igual ao que já existe para τ (`test_aggregate.py:26`) e para o pH (`test_loader_ph.py:52`).
- **Prioridade**: Minor

### Fix 7 — Contagem de testes incorreta no STATE.md
- **Root cause**: `.specs/STATE.md:225` diz "129 unitários + 6 de integração"; o real é 125 + 10.
- **Fix task**: corrigir a linha.
- **Prioridade**: Cosmetic

---

## Requirement Traceability Update

| Requirement | Status anterior | Novo status |
| --- | --- | --- |
| VITALS-01 | Implementing | ✅ Verified |
| VITALS-02 | Implementing | ✅ Verified |
| VITALS-03 | Implementing | ✅ Verified (⚠️ fronteira não fixada — Fix 6) |
| VITALS-04 | Implementing | ❌ Needs Fix (limiar configurável sem cobertura — Fix 4) |
| VITALS-05 | Implementing | ✅ Verified |
| VITALS-06 | Implementing | ❌ Needs Fix (valores do payload não asseridos — Fix 2, Fix 3) |
| VITALS-07 | Implementing | ✅ Verified |
| VITALS-08 | Implementing | ✅ Verified |
| VITALS-09 | Implementing | ✅ Verified (⚠️ fronteira não fixada — Fix 6) |
| VITALS-10 | Implementing | ✅ Verified |
| VITALS-11 | Implementing | ❌ Needs Fix (AC2 não implementado; AC3 parcialmente coberto — Fix 1, Fix 5) |

---

## Summary

**Overall**: ❌ Not Ready

**Spec-anchored check**: 8/13 ACs com desfecho da spec asserido; 3 GAPs (VITALS-04 parcial, VITALS-06 payload, VITALS-11 AC2) + 1 GAP parcial (VITALS-11 AC3) + 1 lacuna de precisão da spec (fronteiras de limiar em VITALS-03/VITALS-09)
**Sensor**: 9/15 mutantes mortos — 6 sobreviveram
**Gate**: 135 passed, 0 failed, 0 skipped; lint limpo

**O que funciona**: as três decisões críticas do design estão corretamente implementadas **e** protegidas por testes discriminantes — fronteira estrita `> τ` de AD-027, exclusão de janelas `None` do denominador, e limiar de pH `< 7.05`. Preprocess não fabrica dado nas bordas; `core/metrics` distingue métrica indefinida (`None`) de zero, exatamente como VITALS-10 exige; o compositor preserva proveniência trecho a trecho e a evidência da timeline aponta para o registro real de origem. Resiliência do lote (VITALS-08) verificada tanto no unitário quanto ponta a ponta.

**Problemas encontrados**: (1) o adaptador MIT-BIH é código morto — nunca é chamado, não passa pelos detectores e não gera evidência, contrariando o Done-when de T18; (2) o payload de evidência que o pipeline realmente grava não tem nenhum valor de `ph`, `score` ou `detector` asserido — três mutações no metadado passam despercebidas; (3) um teste de integração de evidência é vacuoso; (4) o limiar configurável do IsolationForest exigido por VITALS-04 não tem cobertura.

**Next steps**: aplicar Fix 2, 3 e 4 (baratos, só testes) e decidir sobre Fix 1 — implementar o caminho MIT-BIH ou rebaixar formalmente VITALS-11 AC2 na spec com um AD. Re-verificar depois (iteração 1 de no máximo 3).

**Lições a destilar**: há sinal (6 mutantes sobreviventes + 1 lacuna de precisão da spec). O Verifier opera sob restrição de escrita apenas neste arquivo, então o registro em `.specs/LESSONS.md` via `scripts/lessons.py add` fica pendente para o orquestrador. Lições candidatas: (a) "asserção de presença de chave em payload não substitui asserção de valor — o campo pode ser preenchido com qualquer coisa"; (b) "teste que itera uma coleção sem antes asserir que ela é não vazia passa por vacuidade"; (c) "parâmetro declarado configurável precisa de teste com dois valores distintos que mudem o resultado"; (d) "todo limiar precisa de um teste na fronteira exata, e a spec precisa dizer se a comparação é estrita".
