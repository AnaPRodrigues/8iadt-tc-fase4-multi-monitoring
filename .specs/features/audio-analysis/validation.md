# Audio Analysis (F2) Validation

**Date**: 2026-07-22
**Spec**: `.specs/features/audio-analysis/spec.md`
**Diff range**: `4fb87e7..HEAD` (design/tasks docs + `365a9a1..2aafbfe`, T1–T13)
**Verifier**: independent sub-agent (author ≠ verifier)

---

## Task Completion

| Task | Status  | Notes |
| ---- | ------- | ----- |
| T1   | ✅ Done | `models.py` — 8 frozen dataclasses match design exactly |
| T2   | ⚠️ Done, side effect | `config.py` correct, but its test file's basename collides with a pre-existing test file — see Gate |
| T3   | ✅ Done | `icbhi_loader.py` — parsing, "both" label, tolerant loader, deterministic subset |
| T4   | ✅ Done | `icbhi_features.py` — fixed-size MFCC/spectral vector |
| T5   | ⚠️ Done, weak test | `icbhi_classifier.py` — logic correct but `class_weight="balanced"` is unverified (see Sensor) |
| T6   | ✅ Done | `icbhi_evaluate.py` — per-class precision/recall/F1, `None` on empty support |
| T7   | ✅ Done | `icbhi_evidence.py` — spectrogram + sidecar, anomalous-only |
| T8   | ✅ Done | `transcribe.py` — `reliable` logic fully unit-tested; documented accepted gap (positive path) confirmed still valid |
| T9   | ✅ Done | `critical_terms.py` — search, context, timestamp, evidence |
| T10  | ✅ Done | `sentiment.py` — lexicon-based, local-only |
| T11  | ✅ Done | `acoustic_features.py` — jitter/shimmer/HNR/pause/rate, plausible ranges |
| T12  | ⚠️ Done, coverage gap | `fatigue_score.py` function-level logic correct; CLI-level evidence path untested (see AC P3.3) |
| T13  | ⚠️ Done, coverage gap | `cli.py` orchestrates correctly; corrupted-consult-audio branch untested |

**13/13 tasks committed.** All "Done when" boxes are met at the unit-function level; two orchestration-level branches (fatigue evidence write, consult-audio corruption tolerance) are exercised by no test (see AC/Edge Case tables below).

---

## Spec-Anchored Acceptance Criteria

### P1: Classificação de dificuldade respiratória sobre ICBHI 2017 (MVP)

| Criterion (WHEN X THEN Y) | Spec-defined outcome | `file:line` + assertion | Result |
| --- | --- | --- | --- |
| AC1: ciclo anotado carregado → extrai features MFCC/espectrais via librosa + anotação real | `RespiratoryCycle.label` set from real crackle/wheeze flags; feature vector computed via librosa | `backend/tests/audio/test_icbhi_loader.py:42-57` — `assert labels == ["normal","crackle","wheeze","both"]`; `backend/tests/audio/test_icbhi_features.py:32-40` — `assert curto.shape == longo.shape`; real-data proof: `backend/tests/audio/test_icbhi_loader.py:123-136` — `assert len(cycles) == 6898` | ✅ PASS |
| AC2: features de subconjunto extraídas → treina/carrega classificador leve CPU | `train()` fits a CPU model (RandomForest) on the extracted vectors | `backend/tests/audio/test_icbhi_classifier.py:90-102` — `assert predict(modelo, alvo_normal).predicted_label == "normal"` and `== "crackle"` on a separable synthetic set (proves train→predict wiring, not just no-exception) | ✅ PASS |
| AC3: classificador processa ciclo de teste → retorna classe + score de confiança | `Prediction.predicted_label` + `confidence` in `[0,1]` | `backend/tests/audio/test_icbhi_classifier.py:77-87` — `assert 0.0 <= pred.confidence <= 1.0` | ✅ PASS |
| AC4: previsões vs. anotações reais → precision/recall/F1 por classe salvos | Exact numeric precision/recall from known confusion counts, persisted to JSON | `backend/tests/audio/test_icbhi_evaluate.py:32-42` — `assert crackle.precision == 1.0` / `assert crackle.recall == 0.5`; `test_icbhi_evaluate.py:44-55` — reloads JSON, `assert {item["detector"] for item in carregado} == set(CLASSES)` | ✅ PASS |
| AC5: classe anômala prevista → evidência (espectrograma + metadados: ID, classe prevista, classe real, score) | PNG artifact + sidecar JSON with exactly those 4 metadata fields | `backend/tests/audio/test_icbhi_evidence.py:69-87` — `assert meta["record_id"]==...`, `meta["predicted_label"]=="crackle"`, `meta["real_label"]=="wheeze"`, `meta["score"]==0.73`; negative case `test_icbhi_evidence.py:56-66` — `assert resultado is None` for `"normal"` | ✅ PASS |

### P2: Transcrição, termos críticos e sentimento

| Criterion (WHEN X THEN Y) | Spec-defined outcome | `file:line` + assertion | Result |
| --- | --- | --- | --- |
| AC1: áudio de consulta processado pelo faster-whisper → gera transcript em texto | Non-empty transcript text from real speech audio | `backend/tests/audio/test_transcribe.py:38-49` — `assert transcript.text.strip() != ""` (fake model, controlled segments); **positive path with real recorded speech has no integration test** — pre-documented, accepted gap (tasks.md § "Aberto"), confirmed still valid: `reliable`-decision logic has full unit coverage (`test_transcribe.py:38-98`, 6 cases including exact-threshold boundary at line 65-71) | ✅ PASS (gap pre-accepted, re-confirmed not silently dropped) |
| AC2: transcript gerado → busca termos críticos configuráveis, destaca com contexto | Exact matched term + exact context substring | `backend/tests/audio/test_critical_terms.py:25-33` — multiword, accent/case-insensitive match; `test_critical_terms.py:79-95` — `assert sidecar["metadata"]["context"] == "Sinto muita dor no peito agora"` | ✅ PASS |
| AC3: transcript gerado → sentimento (positivo/negativo/neutro), motor local, sem nuvem | Correct label per majority lexicon hits + no cloud import | `backend/tests/audio/test_sentiment.py:16-26` — `assert resultado.label == "positivo"` / `"negativo"`; `test_sentiment.py:40-46` — `assert "boto3" not in fonte` (source-code introspection) | ✅ PASS |
| AC4: termo crítico encontrado → evidência (transcript destacado + timestamp aproximado) | `**termo**` highlighted in artifact + `approx_timestamp_s` in sidecar | `backend/tests/audio/test_critical_terms.py:79-95` — `assert "**dor no peito**" in conteudo`; `assert sidecar["metadata"]["approx_timestamp_s"] == 0.0` | ✅ PASS |
| AC5 / AUDIO-10: áudio sem transcrição inteligível → "não confiável", sem termo crítico falso | `reliable=False`, zero critical terms reported, on **real** non-speech audio | `backend/tests/integration/test_audio_pipeline.py:56-77` — `assert resumo["reliable"] is False`; `assert resumo["critical_terms_found"] == 0`; `assert evidencias_de_termo == []` (real ICBHI audio through the full CLI) | ✅ PASS — strongest test in the suite (real data, exact spec wording) |

### P3: Score de qualidade vocal (fadiga)

| Criterion (WHEN X THEN Y) | Spec-defined outcome | `file:line` + assertion | Result |
| --- | --- | --- | --- |
| AC1: áudio de consulta processado → extrai jitter, shimmer, HNR, taxa de pausas, velocidade de fala | 5 finite features in plausible ranges; pause_rate responds to inserted silence; speaking_rate driven by transcript word count | `backend/tests/audio/test_acoustic_features.py:38-49` (ranges); `:52-61` (pause_rate ordering); `:64-74` — `assert seis_palavras.speaking_rate_wps == pytest.approx(2 * tres_palavras.speaking_rate_wps)` | ✅ PASS |
| AC2: features combinadas → score heurístico de fadiga, fórmula/limiar documentados no relatório técnico | z-score-based combination; documentation in the written technical report is a project deliverable, not code | `backend/tests/audio/test_fatigue_score.py:24-33` — `assert score_fatigado > score_normal` (matches spec's own Independent Test wording verbatim) | ✅ PASS (code); report-doc clause out of this diff's scope, same pattern as other F2 heuristics |
| AC3: score ultrapassa limiar → sinaliza "possível fadiga vocal" como evidência complementar, marcada como heurística não validada | Evidence artifact is written and worded as non-clinically-validated when `is_fatigued=True` | `is_fatigued()` unit-tested (`test_fatigue_score.py:36-40`); **the CLI code path that actually writes this evidence (`cli.py:111-131 _salva_evidencia_fadiga`, called from `cli.py:178-179`) has NO test exercising `fatigued=True`** — no `file:line` citation exists for this behavior | ❌ GAP — evidence-or-zero: NOT covered |

**Status**: ⚠️ 12/13 story ACs PASS; 1 GAP (P3 AC3, orchestration-level evidence write, see Sensor/Fix Plans for the deeper structural cause).

---

## Edge Cases

| Edge case (spec.md) | Result | Evidence |
| --- | --- | --- |
| Áudio corrompido/formato não suportado → erro claro, pula, sem travar lote (AUDIO-12) | ⚠️ PARTIAL | ICBHI side: `backend/tests/audio/test_icbhi_loader.py:78-90` — `assert falhas == ["101_1b1_Al_sc_Meditron.wav"]` ✅. Consult-audio side (`cli.py:143-148`, `try/except Exception` around `transcribe()`): **no test feeds a corrupted `consult_audio_paths` entry through `run()`** — behavior exists in code but is unverified |
| Anotação ICBHI ausente para um ciclo → excluído das métricas, não erro do classificador (AUDIO-13) | ✅ PASS | `backend/tests/audio/test_icbhi_loader.py:60-75` — `assert len(cycles) == 2` (malformed lines silently dropped, not counted) |
| Mesmo arquivo processado duas vezes → mesmo transcript/score/classe; não-determinismo documentado se existir (AUDIO-14) | ✅ PASS | Classifier: `test_icbhi_classifier.py:60-74` (`seed` fixed → same prediction); Features: `test_icbhi_features.py:43-51` (`np.array_equal`); Whisper: `test_transcribe.py:91-97` — `assert fake.calls[0]["temperature"] == 0.0` (proxy for determinism, matches design's own reasoning — the risk is the stochastic fallback ladder, and that's exactly what's asserted). `acoustic_features.py`/`fatigue_score.py` have no dedicated repeat-call test, but contain no randomness (Praat calls + `librosa.effects.split` are deterministic) — low residual risk, consistent with where the spec places emphasis |
| Lista de termos críticos vazia/ausente → usa lista padrão documentada | ✅ PASS | `backend/tests/audio/test_critical_terms.py:44-54` — `assert load_terms(None) == [...]` and same for an empty file |

---

## Discrimination Sensor

| # | File:line | Description | Killed? |
| - | --- | --- | --- |
| 1 | `backend/pipelines/audio/transcribe.py:64` | Flipped `avg_no_speech <= no_speech_threshold` → `>=` | ✅ Killed — `test_transcribe.py::test_reliable_true_...` and `::test_reliable_false_quando_no_speech_prob_medio_acima_do_limiar` fail |
| 2 | `backend/pipelines/audio/icbhi_classifier.py:40-42` | Removed `class_weight="balanced"` from `RandomForestClassifier(...)` | ❌ **Survived** — all 4 tests in `test_icbhi_classifier.py` still pass (every synthetic dataset used is class-balanced 50/50; no test exercises class imbalance or introspects `model.class_weight`) |
| 3 | `backend/pipelines/audio/acoustic_features.py:49-51` | Inverted `pause_rate` formula: `speech_duration_s / duration_s` instead of `(duration_s - speech_duration_s) / duration_s` | ✅ Killed — `test_acoustic_features.py::test_sinal_com_pausas_inseridas_produz_pause_rate_maior_que_sem_pausas` fails (`0.712 > 1.0` is false) |

All three mutations were applied directly to the working tree (repo was clean beforehand), the targeted test file was run, and the file was reverted with `git checkout --` immediately after each measurement; `git status --short` was empty before, between, and after all three. No mutation persists in the final tree (confirmed: full `backend/tests/audio` + integration gate re-run at 55/55 passed after the sensor).

**Sensor depth**: lightweight (3 targeted behavior-level mutations)
**Result**: 2/3 killed — ❌ **FAIL** (one surviving mutant → fix task required, see Fix Plans)

---

## Code Quality

| Principle | Status |
| --- | --- |
| No features beyond what was asked | ✅ |
| No abstractions for single-use code | ✅ |
| No unnecessary "flexibility" added | ✅ |
| Only touched files required for task | ⚠️ `backend/tests/audio/test_config.py` reuses a basename already used by `backend/tests/common/test_config.py`, which is a real cross-feature collision under pytest's default import mode (no `__init__.py` in `backend/tests/`) — not a scope violation per se, but a naming choice that breaks the full-repo gate (see Gate Check below) |
| Didn't "improve" unrelated code | ✅ |
| Matches existing patterns/style | ✅ — CLI skeleton, evidence contract, config discipline, `common/metrics.py` reuse all mirror `vitals`/`video` precedent faithfully |
| Would senior engineer approve? | ⚠️ Yes for domain logic; the untested fatigue-evidence branch and the `class_weight="balanced"` mutant would be flagged in review |
| Tests map to acceptance criteria and are non-shallow (spot-check P2) | ✅ — P2 AC5 (`test_audio_pipeline.py:56-77`) is a genuinely strong test: real non-speech audio through the full CLI, asserting the exact spec-required negative outcome, not just "no exception" |
| Spec-anchored outcome check (asserted values match spec-defined outcome) | ⚠️ 12/13 story ACs match precisely; 1 gap (P3 AC3) |
| Per-layer Coverage Expectation met (domain 1:1 ACs; routes/e2e happy+edge+error) | ⚠️ Domain layer: 1:1 with ACs, mostly. CLI/e2e layer: happy path and one documented negative path (P2/AUDIO-10) are covered; the corrupted-consult-audio error path and the fatigue-evidence-write path are not |
| Every test maps to a spec AC, listed edge case, or Done-when criterion (no unclaimed tests) | ✅ — every test file's docstring cites its AUDIO-NN requirement(s); no orphan tests found |
| Documented project quality/testing guidelines followed | ✅ — `tasks.md` § Test Coverage Matrix (unit uses synthetic/tmp_path fixtures, integration marked `@pytest.mark.integration` against real downloaded data) followed exactly; deviation from that pattern (T8's `"tiny"` model download) explicitly justified in `tasks.md` itself, not silently introduced |

---

## Gate Check

- **Gate command (as scoped for this validation)**: `.venv/bin/python -m pytest -q backend/tests/audio backend/tests/integration/test_audio_pipeline.py && ruff check backend`
  - **Result**: 55 passed, 0 failed, 0 skipped; `ruff check backend` → "All checks passed!"
  - **Test count before feature**: 0 (`backend/tests/audio/` did not exist)
  - **Test count after feature**: 55
  - **Delta**: +55 (all new) — matches expectation
- **Gate command (as literally defined in `tasks.md` § Gate Check Commands, "Build" row)**: `make test && make lint`
  - **Result**: ❌ **FAILS** — `make test` (`.venv/bin/python -m pytest -q`, `testpaths = ["backend/tests"]` per root `pyproject.toml`) aborts with:
    ```
    import file mismatch:
    imported module 'test_config' has this __file__ attribute:
      backend/tests/audio/test_config.py
    which is not the same as the test file we want to collect:
      backend/tests/common/test_config.py
    HINT: remove __pycache__ / .pyc files and/or use a unique basename for your test file modules
    Interrupted: 1 error during collection
    ```
    Exit code 2. Zero tests run in this mode — not a partial failure, a total collection abort for the entire repository's test suite. Root cause: `backend/tests/audio/test_config.py` (introduced by T2) has the same basename as the pre-existing `backend/tests/common/test_config.py`; `backend/tests/` has no `__init__.py` anywhere, so pytest's default "prepend" import mode requires globally-unique test module basenames. Confirmed this is the *only* such collision (`find backend/tests -name "test_*.py" | xargs -n1 basename | sort | uniq -d` → only `test_config.py`).
    `make lint` alone passes cleanly.
- **Skipped tests**: none
- **Failures**: `make test` full-suite collection (see above) — this is the gate command `tasks.md` itself designates as "Build / Fim de fase"; it was evidently never run by the implementers (or was run and its failure was not acted on), since T2's own self-check only ran the narrow `-m "not integration" backend/tests/audio/test_config.py` command.

---

## Fix Plans

### Fix 1: `make test` (full repository) fails to collect — basename collision

- **Root cause**: `backend/tests/audio/test_config.py` (T2) duplicates the basename of pre-existing `backend/tests/common/test_config.py`; no `__init__.py` package markers exist under `backend/tests/`, so pytest's default import mode cannot disambiguate the two modules.
- **Fix task**: Rename `backend/tests/audio/test_config.py` to a unique basename (e.g. `test_audio_config.py`), OR add `__init__.py` files under `backend/tests/` and each subpackage to switch pytest to package-relative imports. Prefer the rename — it's the smaller, more surgical change and matches how the rest of `backend/tests/<feature>/` is organized (no existing `__init__.py` anywhere in the tree).
- **Verify**: `.venv/bin/python -m pytest -q` from repo root (i.e. `make test`) collects and runs without the `import file mismatch` error.
- **Priority**: **Blocker** — breaks the project's own designated CI-level gate for every feature going forward, not just F2.

### Fix 2: `class_weight="balanced"` in `icbhi_classifier.train()` is untested (surviving mutant)

- **Root cause**: All synthetic fixtures in `test_icbhi_classifier.py` use perfectly class-balanced data (50/50 `normal`/`crackle`), so removing `class_weight="balanced"` changes nothing observable.
- **Fix task**: Add a test that either (a) introspects `train(cycles, seed).get_params()["class_weight"] == "balanced"` directly, or (b) trains on a deliberately imbalanced synthetic set (e.g. 9:1) and asserts the minority class is still predicted at least once / recall doesn't collapse to 0 — proving the balancing actually changes behavior, not just that the parameter is set.
- **Verify**: Re-apply the mutation (remove `class_weight="balanced"`) and confirm the new test fails.
- **Priority**: Major — this is exactly the design decision called out in `design.md` § Tech Decisions to handle the ICBHI's real class imbalance (crackle 27%, wheeze 13%, both 7%, normal 53%); if it silently regressed, precision/recall for the minority classes (the actually pathological ones) would degrade without any test noticing.

### Fix 3: P3 AC3 — fatigue evidence write path is untested, and unreachable for the single-audio case

- **Root cause**: (a) No unit or integration test drives `cli.py::_run_p2_p3` to a `fatigued=True` state, so `_salva_evidencia_fadiga` (the code that writes the spec-required "possível fadiga vocal... heurística não validada clinicamente" artifact) is never exercised. (b) Structurally, `_run_p2_p3` builds `baseline` from all processed consult audios in the same run (`cli.py:169`); when `consult_audio_paths` has exactly 1 entry (a scenario the spec explicitly permits — "1–2 gravações curtas"), that single audio's own features are the entire baseline population, `fatigue_score._zscore`'s `pstdev(population)` is 0 for every component, so `score()` always returns `0.0` and `is_fatigued(0.0, threshold=1.0)` is always `False`. The evidence-generation branch is dead code for the 1-audio case.
- **Fix task**: Either (a) document explicitly in `design.md`/technical report that the fatigue score requires ≥2 consult audios in the same run to be meaningful (and treat "1 audio" as a known, accepted limitation, same pattern as the T8 gap), or (b) change the baseline strategy so a single audio can still be flagged (e.g., compare against fixed/documented plausible-range thresholds rather than a self-relative z-score when `len(baseline) < 2`). Either way, add a test that exercises `_run_p2_p3` (or extract `_salva_evidencia_fadiga` reachability into something testable) with ≥2 consult audios, one clearly more "fatigued" than the other, and assert the evidence file is written with the expected wording.
- **Priority**: Major for the code-coverage gap (untested branch); the structural single-audio limitation is Minor in isolation (P3 is explicitly the lowest-priority story, "não é indispensável") but worth flagging before the group records their real 1–2 audios, since the demo could produce zero fatigue evidence even when the heuristic should plausibly fire.

### Fix 4: Edge case — corrupted `consult_audio_paths` entry is untested

- **Root cause**: `cli.py:143-148` wraps `transcribe()` in `try/except Exception` for AUDIO-12 tolerance on consult audio, but no test supplies a corrupted/unsupported file via `consult_audio_paths` to `run()` to confirm the batch continues and the failure is logged.
- **Fix task**: Add an integration test with `consult_audio_paths=[<corrupted or non-existent audio file>, <valid ICBHI wav>]` and assert `run()` still returns `0`, the valid audio's summary is written, and a warning is logged for the corrupted one.
- **Priority**: Minor — the code pattern is a direct copy of the already-tested ICBHI-side tolerance pattern, so the risk of it actually being broken is low, but it's currently unverified per evidence-or-zero.

---

## Requirement Traceability Update

| Requirement | Previous Status | New Status |
| --- | --- | --- |
| AUDIO-01 | In Tasks | ✅ Verified |
| AUDIO-02 | In Tasks | ✅ Verified |
| AUDIO-03 | In Tasks | ✅ Verified |
| AUDIO-04 | In Tasks | ✅ Verified |
| AUDIO-05 | In Tasks | ✅ Verified |
| AUDIO-06 | In Tasks | ✅ Verified |
| AUDIO-07 | In Tasks | ✅ Verified |
| AUDIO-08 | In Tasks | ✅ Verified |
| AUDIO-09 | In Tasks | ✅ Verified |
| AUDIO-10 | In Tasks | ✅ Verified |
| AUDIO-11 | In Tasks | ❌ Needs Fix (P3 AC3 evidence path untested + single-audio structural gap) |
| AUDIO-12 | In Tasks | ❌ Needs Fix (consult-audio corruption path untested) |
| AUDIO-13 | In Tasks | ✅ Verified |
| AUDIO-14 | In Tasks | ✅ Verified |

---

## Summary

**Overall**: ❌ Not Ready

**Spec-anchored check**: 12/13 story ACs matched spec outcome (1 GAP: P3 AC3); all 4 edge cases evidenced except one partial (AUDIO-12 consult-audio side)
**Sensor**: 2/3 mutations killed, 1 survived (`class_weight="balanced"`)
**Gate**: 55/55 passed on the F2-scoped command; **the repository's own `make test` full-suite gate fails to collect** due to a basename collision introduced by T2

**What works**: The domain logic across all three raias (P1 ICBHI classifier, P2 transcription/terms/sentiment, P3 acoustic features) is well-tested at the unit level, with precise spec-anchored assertions (not just "doesn't throw"). The SPEC_DEVIATION (`"both"` class) is implemented consistently across loader, evaluator, and evidence generation. AUDIO-10 (unreliable-transcript, no-false-positive) is proven end-to-end against real ICBHI audio through the full CLI — the strongest test in the suite. The T8 documented gap (no real speech audio yet) was re-confirmed, not silently dropped, and its unit coverage genuinely proves what it claims.

**Issues found**:
1. `make test` (full repo) fails to collect — `backend/tests/audio/test_config.py` basename collides with `backend/tests/common/test_config.py`. Fix: rename the F2 test file.
2. `class_weight="balanced"` in the classifier is a surviving mutant — no test would catch its removal. Fix: add an imbalance-sensitive test or direct param introspection.
3. P3's fatigue-evidence write path (`cli.py::_salva_evidencia_fadiga`) is untested and structurally unreachable when only 1 consult audio is configured — a scenario the spec explicitly allows. Fix: add a ≥2-audio test and decide/document the single-audio behavior.
4. The consult-audio side of AUDIO-12 (corrupted file tolerance in `cli.py`) is untested. Fix: add an integration test with a corrupted `consult_audio_paths` entry.

**Next steps**: Orchestrator to create fix tasks for the 4 items above (Fix 1 is a Blocker — it affects every feature's `make test`, not just F2 — recommend it be prioritized first regardless of F2-specific triage order), dispatch to an implementer, and re-run this Verifier.
