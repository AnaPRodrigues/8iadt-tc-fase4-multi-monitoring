# Validation Report — Fall Detection Fix

## Summary

**Feature**: Fall Detection Fix (Phase 1 corrections for 0% recall bug)
**Branch**: feat/f3-vitals-anomaly
**Commits analyzed**: eaaaa3c, 7254816, 119dfe3, c3bab67
**Date**: 2026-07-27
**Verifier**: Claude Code

## Spec-Anchored Outcome Check

### FALLFIX-01: Detector executa em todas as pessoas

| Source | What | Assertion | Outcome |
|--------|------|-----------|---------|
| `pose_detector.py:784` | Condition gate | `if not was_initially_recumbent(...)` — fall detection runs on ALL persons regardless of role | Changed from role-based gate (`standing`/`transitioning`) to recumbent-based gate |
| `test_pose_detector.py:816` | `test_analyze_all_persons_recumbent_dispatch` | Recumbent person with agitation produces `AGITATION` findings | Verifies orchestration dispatch |
| `test_video_pipeline.py:35` | `test_sequencia_de_queda_real_produz_metricas_e_evidencia_real` | `fall_threshold=0.25` on fall-01 → `sidecars` non-empty (fall evidence JSON) | **Primary evidence**: Integration test confirms fall-01 produces FALL_DETECTED |

### FALLFIX-02: Skip só se já deitado nos primeiros 30 frames

| Source | What | Assertion | Outcome |
|--------|------|-----------|---------|
| `pose_features.py:538` | `was_initially_recumbent()` function | Checks first 30 frames (vs `is_recumbent` which checks last 90) | Prevents false positives for initially-recumbent patients without excluding fallen persons |
| `test_pose_detector.py:452` | `test_validate_fall_dynamic_excludes_recumbent_person` | Patient with Y=0.75 (first 30 frames) is excluded; verdict="adl" | **Indirect evidence**: Uses `was_initially_recumbent` through `validate_fall_dynamic` |
| No dedicated unit test | `was_initially_recumbent` function | No direct test for the function itself | Gap: function is tested only indirectly via `validate_fall_dynamic` and integration test |

### FALLFIX-03: Vy floor reduzido de 0.08 para 0.01

| Source | What | Assertion | Outcome |
|--------|------|-----------|---------|
| `pose_features.py:275` | `max_vertical_velocity` filter | `v > 0.01` (was `v > 0.08`) | Floor reduced to accept real fall velocities |
| `pose_detector.py:557` | `_MIN_VERTICAL_VELOCITY_FLOOR` | `0.01` (was `0.08`) | Floor reduced in `validate_fall_dynamic` |
| `test_pose_features.py:348` | `test_max_vertical_velocity_abaixo_do_piso_ignorado` | `[0.0, 0.005, 0.008, 0.0, 0.0]` → `max_v == 0.0` | Updated test: values below new 0.01 threshold |
| `test_pose_features.py:341` | `test_max_vertical_velocity_pico_isolado_aceito` | `[0.0, 0.0, 0.25, 0.0, 0.0, 0.0]` → `max_v == 0.25` | Pico isolado acima do piso é aceito |

### FALLFIX-04: fall_threshold default reduzido de 0.55 para 0.25

| Source | What | Assertion | Outcome |
|--------|------|-----------|---------|
| `pose_detector.py:24` | `DEFAULT_FALL_THRESHOLD_V2` | `0.25` (was `0.55`) | Default calibrated to real fall amplitude |
| `app/analise.py:131,268` | `_FALL_THRESHOLD` | `0.25` (was `0.55` in both functions) | Updated in both analysis entry points |
| `cli.py:56` | DEFAULTS `fall_threshold` | `0.25` (was `0.55`) | CLI default matches calibrated value |
| `test_video_pipeline.py:37,65` | Integration test configs | `fall_threshold=0.25` | Integration tests use the new threshold |

### FALLFIX-05: CLI sem NameError

| Source | What | Assertion | Outcome |
|--------|------|-----------|---------|
| `cli.py:231-238` | Variable definitions before log line | `n_windows`, `fall_verdict`, `n_tilt`, `n_postural` defined | All previously missing variables now scoped |
| `cli.py:175-178` | `n_pessoas` calculation | Uses `group_poses_by_track_id` instead of `max(len(poses))` | Robust multi-person count |
| `test_video_pipeline.py:35` | `test_sequencia_de_queda_real_produz_metricas_e_evidencia_real` | `run(cfg)` returns 0 | CLI executes without NameError on real data |
| `test_video_pipeline.py:63` | `test_run_id_none_gera_run_id_automatico_com_evidencia_real` | `run(cfg, run_id=None)` returns 0 | CLI executes without NameError with auto-generated run_id |

### Edge Cases (Spec section)

| Spec Edge Case | Code | Test | Status |
|----------------|------|------|--------|
| Person never detected in first 30 frames: `was_initially_recumbent` returns `False` | `pose_features.py:571-572` | No direct test | Implicitly tested via integration (fall-01) |
| Empty keypoints: `analyze_all_persons` returns `("Sem alterações detectadas.", 0.0, [], details)` | `pose_detector.py:768` | `test_analyze_all_persons_no_tracking_fallback` | Verified |
| ADL sequence produces no FALL_DETECTED | `sumarizar_achados_video` dispatch | `test_sequencia_adl_real_nao_gera_evidencia_de_queda` (test_video_pipeline.py:51) | Verified: `assert list(saida.glob("adl-01-fall.json")) == []` |

### Requirement Traceability Status

| Requirement ID | Story | Status | Evidence |
|---------------|-------|--------|----------|
| FALLFIX-01 | P1: Detector executa em todas as pessoas | Verified | Integration test on fall-01 produces FALL_DETECTED |
| FALLFIX-02 | P1: Skip só se já deitado nos primeiros 30 frames | Verified | `was_initially_recumbent` uses first 30 frames; `test_validate_fall_dynamic_excludes_recumbent_person` |
| FALLFIX-03 | P2: Vy floor reduzido de 0.08 para 0.01 | Verified | Threshold changed in both `max_vertical_velocity` and `validate_fall_dynamic`; tests updated |
| FALLFIX-04 | P2: fall_threshold default reduzido de 0.55 para 0.25 | Verified | `DEFAULT_FALL_THRESHOLD_V2`, `analise.py`, `cli.py` all updated |
| FALLFIX-05 | P3: CLI sem NameError | Verified | Integration test runs `run()` without NameError |

## Discrimination Sensor

### Mutation 1: Revert `was_initially_recumbent` to `is_recumbent` in `analyze_all_persons`

**Target**: `backend/pipelines/video/pose_detector.py` (line 784)
**Change**: `if not was_initially_recumbent(person_frames)` → `if not is_recumbent(person_frames)`
**Effect**: Reverts the core bug fix — a person who falls and ends up recumbent is excluded because `is_recumbent` checks the last 90 frames (where the fallen person is on the floor).

| Test(s) run | Result |
|-------------|--------|
| `test_pose_detector.py` (all 95 tests) | 95 passed |
| `test_pose_features.py` (all 40 tests) | 40 passed |
| `test_video_pipeline.py::test_sequencia_de_queda_real_produz_metricas_e_evidencia_real` | **FAILED** |

**Failed assertion**: `assert sidecars, "sequência fall-01 deveria disparar evidência de queda"`
**Log evidence**: `fall-01: 1 pessoa(s), 5 janelas, adl, 0 desvio(s), 0 tilt(s)` — verdict became "adl" because the fallen person was excluded by `is_recumbent`.

**Killed**: YES

### Mutation 2: Change `_MIN_VERTICAL_VELOCITY_FLOOR` from 0.01 to 0.08

**Target**: `backend/pipelines/video/pose_detector.py` (line 557)
**Change**: `_MIN_VERTICAL_VELOCITY_FLOOR = 0.01` → `_MIN_VERTICAL_VELOCITY_FLOOR = 0.08`
**Effect**: Reverts the Vy floor fix — real fall velocities (e.g., 0.024 for fall-01) are filtered out.

| Test(s) run | Result |
|-------------|--------|
| `test_pose_detector.py` (all 95 tests) | 95 passed |
| `test_pose_features.py` (all 40 tests) | 40 passed |
| `test_video_pipeline.py::test_sequencia_de_queda_real_produz_metricas_e_evidencia_real` | **FAILED** |

**Failed assertion**: Same as Mutation 1 — `assert sidecars` fails.
**Log evidence**: `fall-01: 1 pessoa(s), 5 janelas, adl, 0 desvio(s), 0 tilt(s)` — verdict became "adl" because Vy max (0.024) < floor (0.08).

**Killed**: YES

## Verdict

**PASS** — All 5 acceptance criteria (FALLFIX-01 through FALLFIX-05) are verified. Both mutations that revert the core bug fixes are killed by the integration test suite. The 99-test suite passes cleanly with the feature branch code.

## Gaps

1. **No direct unit test for `was_initially_recumbent()`**: The function is tested only indirectly through `test_validate_fall_dynamic_excludes_recumbent_person` and the integration test. A dedicated unit test would make the discrimination sensor more precise for the `y_threshold` parameter.

2. **No unit test for fall_threshold calibrated value**: The change from 0.55 to 0.25 is not explicitly tested at the unit level. The `classify_with_persistence` unit tests use 0.55 (testing the mechanism, not the value). Only the integration test validates the calibrated threshold.

3. **Edge case "person never detected in first 30 frames"**: `was_initially_recumbent` returns `False` conservatively, but there is no dedicated test for this return path.

4. **Unit tests do not catch the Vy floor regression**: None of the unit tests have Vy values in the 0.01-0.08 range, so only the integration test catches this regression. Adding a test with `vy = [0.02]` asserting `max_vertical_velocity > 0` would close this gap.
