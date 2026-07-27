# Video Pose Analysis Expansion — Tasks

## Execution Protocol (MANDATORY)

Implement these tasks with the `tlc-spec-driven` skill: activate it by name and follow its Execute flow and Critical Rules. Do not search for skill files by filesystem path. The skill is the source of truth for the full flow (per-task cycle, sub-agent delegation, adequacy review, Verifier, discrimination sensor).

If the skill cannot be activated, STOP and tell the user — do not proceed without it.

---

**Design**: `.specs/features/video-pose-expansion/design.md`
**Spec**: `.specs/features/video-pose-expansion/spec.md`
**Status**: Done

---

## Test Coverage Matrix

> Generated from existing test patterns in `backend/tests/video/test_pose_*.py`, project Makefile, and spec. Guidelines found: `Makefile` (`make test`, `make test-unit`), `pyproject.toml` (pytest).

| Code Layer | Required Test Type | Coverage Expectation | Location Pattern | Run Command |
| --- | --- | --- | --- | --- |
| Domain / business-logic (pose_features, pose_detector, pose_evidence) | unit | All branches; 1:1 to spec ACs (POSE-01 a POSE-10); every listed edge case | `backend/tests/video/test_pose_*.py` | `make test-unit` |
| Pipeline integration (cli.py run) | integration | Happy path (unified pipeline → N findings) + edge (zero findings, no person) + error (corrupted video) | `backend/tests/integration/test_video_pipeline.py` | `make test` |
| Entity / Config (models.py, cli.py Config) | none | Build gate only — lint + import check | — | `ruff check backend` |

## Gate Check Commands

> Generated from project Makefile and `pyproject.toml`.

| Gate Level | When to Use | Command |
| --- | --- | --- |
| Quick | After tasks with unit tests only (domain layer) | `PYTHONPATH=backend python -m pytest backend/tests/video/ -q -m "not integration"` |
| Full | After tasks with integration tests or pipeline wiring | `make test` |
| Build | After phase completion | `make test && ruff check backend` |

---

## Execution Plan

Phases are ordered and run sequentially — each phase completes before the next begins.

```
Phase 1: Foundation     T1 → T2
Phase 2: Multi-Person   T3 → T4
Phase 3: Detection      T5 → T6 → T7
Phase 4: Evidence       T8 → T9
Phase 5: Integration    T10
```

### Phase 1: Foundation (2 tasks)
Data models + config. No domain logic — entity/config layer.

### Phase 2: Multi-Person + Features (2 tasks)
Extraction layer. `num_poses` injection + `extract_all_keypoints` + `select_ground_person`.

### Phase 3: Detection (3 tasks)
Classification logic. Persistence filter + postural deviations + trunk tilt.

### Phase 4: Evidence (2 tasks)
Visual evidence + metadata expansion.

### Phase 5: Integration (1 task)
Unified pipeline wiring. Both detectors in sequence on same frames.

---

## Task Breakdown

### T1: Add JointTarget and PosturalFinding to models.py

**What**: Add two new frozen dataclasses to `models.py` — `JointTarget` (joint name + landmark indices + angle targets) and `PosturalFinding` (finding type + measured/expected angles + duration + score + clinical description). Existing dataclasses unchanged.
**Where**: `backend/pipelines/video/models.py` (append, no modifications)
**Depends on**: None
**Reuses**: Existing `PoseFrame`, `MovementWindow` patterns
**Requirement**: POSE-08, POSE-09, POSE-10

**Done when**:
- `JointTarget` frozen dataclass with `joint_name: str`, `landmark_a/b/c: int`, `min_angle: float`, `target_angle: float`
- `PosturalFinding` frozen dataclass with `finding_type: str`, `joint_name: str | None`, `measured_angle: float`, `expected_angle: float`, `duration_s: float`, `frame_index: int`, `score: float`, `description: str`
- `ruff check backend/pipelines/video/models.py` clean
- Existing imports (PoseFrame, MovementWindow, etc.) still work

**Tests**: none (entity layer)
**Gate**: build

**Commit**: `feat(video-pose): add JointTarget and PosturalFinding models`

---

### T2: Expand CLI Config with all parameters

**What**: Add fall detection + physiotherapy parameters to `cli.py` Config dataclass and `DEFAULTS` dict. All new fields have documented defaults. Validation remains strict (unknown field → ValueError). Existing configs without new fields → defaults applied.
**Where**: `backend/pipelines/video/cli.py` (modify `DEFAULTS` and `Config`)
**Depends on**: T1 (imports `JointTarget` for type hints)
**Reuses**: Existing `Config` pattern (frozen dataclass, YAML → validated), `audio/config.py` validation pattern
**Requirement**: POSE-12 (defaults)

**Done when**:
- `DEFAULTS` expanded: `fall_threshold=0.55`, `persistence_frames=30`, `num_poses=3`, `joint_targets=[]`, `trunk_tilt_max=30.0`, `tilt_persistence_frames=90`
- `Config` expanded with typed fields: `fall_threshold: float`, `persistence_frames: int`, `num_poses: int`, `joint_targets: list[JointTarget]`, `trunk_tilt_max: float`, `tilt_persistence_frames: int`
- `load_config` validates unknown fields → `ValueError`
- Config YAML with only `dataset_dir` still loads (backward compat — defaults fill the rest)
- `ruff check backend/pipelines/video/cli.py` clean

**Tests**: none (config layer — build gate)
**Gate**: build

**Commit**: `feat(video-pose): expand CLI config with fall and physio parameters`

---

### T3: Multi-person extraction — num_poses + extract_all_keypoints

**What**: (a) Add `num_poses` parameter to `create_landmarker` (default 3). (b) Create `extract_all_keypoints` returning `list[PoseFrame]` (all detected skeletons per frame). (c) Keep `extract_keypoints` as wrapper for backward compatibility.
**Where**: `backend/pipelines/video/pose.py`
**Depends on**: None (uses existing `PoseFrame`)
**Reuses**: `ensure_pose_model`, `PoseLandmarker`, `extract_keypoints` logic
**Requirement**: POSE-03, POSE-18

**Done when**:
- `create_landmarker(model_path, num_poses=3)` injects `num_poses` into `PoseLandmarkerOptions`
- `extract_all_keypoints(frame_path, landmarker) -> list[PoseFrame]` iterates `result.pose_landmarks`, returns list (empty if no person)
- `extract_keypoints` unchanged signature, delegates to `extract_all_keypoints` and returns first element or `None`
- Unit test: `num_poses=2` synthetic frame, verify 2 `PoseFrame` returned
- Unit test: frame with no person → empty list from `extract_all_keypoints`, `None` from `extract_keypoints`
- Unit test: `extract_keypoints` backward compat — same result as before for 1-person frame
- Existing tests (`test_pose.py`) still pass
- `ruff check backend/pipelines/video/pose.py` clean

**Tests**: unit
**Gate**: quick

**Commit**: `feat(video-pose): add multi-person extraction with configurable num_poses`

---

### T4: Multi-person selection + joint angles + trunk tilt

**What**: Add to `pose_features.py`: (a) `select_ground_person` — selects pose with lowest mean Y per frame, (b) `joint_angle` — angle at joint via dot product, (c) `trunk_tilt` — spine angle vs. vertical Y, (d) `joint_angles_per_frame` — all configured angles for one frame. Existing `windowed_features` unchanged.
**Where**: `backend/pipelines/video/pose_features.py` (append new functions)
**Depends on**: T1 (uses `JointTarget`), T3 (uses `extract_all_keypoints` format)
**Reuses**: `_center_of_mass`, `_asymmetry` (unchanged), `PoseFrame`
**Requirement**: POSE-03, POSE-06, POSE-07, POSE-19

**Done when**:
- `select_ground_person(all_poses: list[list[PoseFrame | None]]) -> list[PoseFrame | None]` — per frame, picks pose with lowest mean Y; returns `None` for frames where all poses are empty
- `joint_angle(frame, a, b, c) -> float | None` — `arccos(dot(v1,v2)/(|v1|*|v2|))` in degrees; `None` if any landmark visibility < 0.5
- `trunk_tilt(frame) -> float | None` — angle of mid(11,12)→mid(23,24) vs (0,1); `None` if visibility low
- `joint_angles_per_frame(frame, joints) -> dict[str, float | None]`
- Unit: `joint_angle` on right-angle synthetic landmarks → ~90°
- Unit: `joint_angle` on 180° line → ~180°
- Unit: `trunk_tilt` on perfectly vertical spine → ~0°
- Unit: `trunk_tilt` on 30° tilted spine → ~30°
- Unit: `select_ground_person` — 2 people, one at Y=0.9 (floor), one at Y=0.3 (standing) → floor person selected
- Unit: `select_ground_person` — single person → that person
- Unit: `joint_angle` with low-visibility landmark → `None` (POSE-19)
- Unit: `joint_angles_per_frame` — multi-joint config returns all angles
- Existing `test_pose_features.py` tests still pass
- `ruff check backend/pipelines/video/pose_features.py` clean

**Tests**: unit
**Gate**: quick

**Commit**: `feat(video-pose): add ground-person selection, joint angles, and trunk tilt`

---

### T5: Fall detection with temporal persistence

**What**: Add `classify_with_persistence` to `pose_detector.py` — fall only confirmed after `persistence_frames` consecutive windows above threshold; counter resets when amplitude drops below. Keep `classify_sequence` unchanged for backward compat.
**Where**: `backend/pipelines/video/pose_detector.py` (append, don't modify `classify_sequence`)
**Depends on**: T4 (consumes `windowed_features` output)
**Reuses**: `MovementWindow`, `DEFAULT_FALL_THRESHOLD` (0.3 kept; new `DEFAULT_FALL_THRESHOLD_V2 = 0.55`)
**Requirement**: POSE-01, POSE-02, POSE-04

**Done when**:
- `DEFAULT_FALL_THRESHOLD_V2 = 0.55` constant added
- `classify_with_persistence(windows, threshold, persistence_frames) -> tuple[str, int | None]` — returns `("queda", frame_idx)` or `("adl", None)` or `("dados_insuficientes", None)`
- Counter increments when `window.amplitude > threshold`; resets to 0 when below
- Fall confirmed only when counter ≥ `persistence_frames`; `frame_idx` = frame of first window in the streak
- Unit: 30 windows all above threshold → `("queda", idx)`
- Unit: 20 windows above, then 1 below, then 40 above → counter resets at frame 20, fall confirmed at frame 50 (20+30)
- Unit: all windows below threshold → `("adl", None)`
- Unit: empty list → `("dados_insuficientes", None)`
- Unit: amplitude 0.50 with threshold 0.55 → no fall (filters out agachamento)
- Existing `test_pose_detector.py` (using `classify_sequence`) still passes
- `ruff check backend/pipelines/video/pose_detector.py` clean

**Tests**: unit
**Gate**: quick

**Commit**: `feat(video-pose): add fall detection with temporal persistence filter`

---

### T6: Postural deviation detection

**What**: Add `detect_postural_deviations` to `pose_detector.py` — per joint target, compare measured angle to min threshold; if below min for `persistence_frames` consecutive, emit `POSTURAL_DEVIATION` finding.
**Where**: `backend/pipelines/video/pose_detector.py` (append)
**Depends on**: T4 (`joint_angles_per_frame`), T1 (`JointTarget`, `PosturalFinding`)
**Reuses**: `joint_angle` from `pose_features`, config `persistence_frames`
**Requirement**: POSE-08, POSE-19

**Done when**:
- `detect_postural_deviations(frames, joint_targets, persistence_frames, fps) -> list[PosturalFinding]`
- For each joint in `joint_targets`, computes `joint_angle` per frame
- Counter increments when `angle < min_angle`; resets when `angle >= min_angle` or `None`
- Finding emitted when counter ≥ `persistence_frames`; `frame_index` = first frame of streak
- `score = max(0.0, min(1.0, 1.0 - measured / expected))` — linear, clamped
- `description` in clinical language: "Amplitude articular reduzida em flexão de {joint} (alcançado: {X}°, esperado: >{Y}°)."
- `duration_s = persistence_frames / fps`
- Unit: 40 consecutive frames with knee at 62° (min=70) → 1 finding emitted
- Unit: 20 frames below min, then 1 frame above, then 40 below → counter resets, second streak produces finding
- Unit: all frames above min → empty list
- Unit: NaN angles interleaved → counter resets (POSE-19), no false positive
- `ruff check backend/pipelines/video/pose_detector.py` clean

**Tests**: unit
**Gate**: quick

**Commit**: `feat(video-pose): add postural deviation detection for physiotherapy`

---

### T7: Trunk tilt detection

**What**: Add `detect_trunk_tilt` to `pose_detector.py` — if trunk tilt exceeds `max_angle` for `tilt_persistence_frames` consecutive, emit `TRUNK_TILT` finding.
**Where**: `backend/pipelines/video/pose_detector.py` (append)
**Depends on**: T4 (`trunk_tilt`), T1 (`PosturalFinding`)
**Reuses**: `trunk_tilt` from `pose_features`, same persistence pattern as T5/T6
**Requirement**: POSE-09, POSE-19

**Done when**:
- `detect_trunk_tilt(frames, max_angle, persistence_frames, fps) -> list[PosturalFinding]`
- Counter increments when `tilt > max_angle`; resets when `tilt <= max_angle` or `None`
- Finding emitted when counter ≥ `persistence_frames`
- `score = min(1.0, measured / (2 * max_angle))`
- `description`: "Desvio postural / inclinação de tronco sustentada ({X}° de inclinação por {Y}s)."
- Unit: 100 consecutive frames at 34° (max=30) → 1 finding emitted
- Unit: 50 frames tilted, then 1 frame straight, then 80 tilted → counter resets, second streak produces finding
- Unit: all frames below max → empty list
- Unit: NaN tilt → counter resets (POSE-19)
- `ruff check backend/pipelines/video/pose_detector.py` clean

**Tests**: unit
**Gate**: quick

**Commit**: `feat(video-pose): add trunk tilt detection with temporal persistence`

---

### T8: Annotated evidence drawing

**What**: Create `pose_evidence.py` with `draw_annotated_frame` — renders skeleton (blue), highlights anomalous joints (yellow/red), overlays angle labels near joints, and draws spine line + tilt angle for trunk findings. Keep old `draw_keypoints` in `pose_detector.py` unchanged.
**Where**: `backend/pipelines/video/pose_evidence.py` (new file)
**Depends on**: T1 (`PosturalFinding`), T3 (`PoseFrame`)
**Reuses**: `cv2` drawing patterns from `draw_keypoints`, `common/evidence.py`
**Requirement**: POSE-05, POSE-10

**Done when**:
- `draw_annotated_frame(frame_path, pose_frame, findings, output_path) -> Path`
- All 33 landmarks with visibility ≥ 0.5 drawn as blue circles (radius 4)
- Landmarks involved in findings drawn yellow (`POSTURAL_DEVIATION`) or red (`TRUNK_TILT`, `FALL_DETECTED`), radius 6
- Angle text overlaid near affected joint (e.g., `62°` in yellow)
- Spine line drawn for `TRUNK_TILT` findings (mid-shoulders → mid-hips), tilt angle overlaid
- Bone connections drawn between adjacent landmarks in light blue
- Unit: synthetic frame with `POSTURAL_DEVIATION` knee finding → output PNG has yellow knee markers + angle text
- Unit: synthetic frame with `TRUNK_TILT` finding → output PNG has spine line + tilt angle
- Unit: output PNG is valid image file (cv2.imread succeeds)
- Existing `test_pose_detector.py` (using `draw_keypoints`) still passes
- `ruff check backend/pipelines/video/pose_evidence.py` clean

**Tests**: unit
**Gate**: quick

**Commit**: `feat(video-pose): add annotated evidence drawing with joint highlights and angles`

---

### T9: Expanded evidence metadata

**What**: Update `save_fall_evidence` in `pose_detector.py` to include `finding_type`, `persistence_frames`, `description` in metadata. Add `save_postural_evidence` for physiotherapy findings (`POSTURAL_DEVIATION`, `TRUNK_TILT`). Both use `draw_annotated_frame` from T8.
**Where**: `backend/pipelines/video/pose_detector.py` (modify `save_fall_evidence`, append `save_postural_evidence`)
**Depends on**: T8 (`draw_annotated_frame`), T1 (`PosturalFinding`)
**Reuses**: `common.evidence.save_evidence`, `common.evidence.evidence_dir`
**Requirement**: POSE-05, POSE-10, POSE-12 (multi-finding evidence)

**Done when**:
- `save_fall_evidence` metadata expanded: `finding_type: "FALL_DETECTED"`, `persistence_frames`, `description`
- `save_fall_evidence` uses `draw_annotated_frame` instead of `draw_keypoints`
- New `save_postural_evidence(finding, frame_path, pose_frame, run_id, root) -> Evidence` — same contract, different metadata
- Postural evidence metadata: `finding_type`, `joint_name`, `measured_angle`, `expected_angle`, `duration_s`, `frame_index`, `score`, `description`
- Evidence artifact uses `draw_annotated_frame` with appropriate highlighting
- Unit: `save_fall_evidence` produces sidecar JSON with `finding_type: "FALL_DETECTED"`
- Unit: `save_postural_evidence` for `POSTURAL_DEVIATION` produces sidecar with joint_name + measured angle
- Unit: `save_postural_evidence` for `TRUNK_TILT` produces sidecar with trunk angle + duration
- Existing tests using `save_fall_evidence` still pass (metadata expanded, not broken)
- `ruff check backend/pipelines/video/pose_detector.py` clean

**Tests**: unit
**Gate**: quick

**Commit**: `feat(video-pose): expand evidence metadata and add postural evidence function`

---

### T10: Unified pipeline wiring in cli.py

**What**: Rewrite `cli.py:run()` to execute both detectors in sequence on the same extracted keypoints: `extract_all_keypoints` → `select_ground_person` → `windowed_features` → `classify_with_persistence` + `detect_postural_deviations` + `detect_trunk_tilt` → generate evidence for every finding. All findings go to same `output/video_pose/<run_id>/`.
**Where**: `backend/pipelines/video/cli.py` (rewrite `run()`)
**Depends on**: T2 (Config), T3 (extract_all_keypoints), T4 (select_ground_person), T5 (classify_with_persistence), T6 (postural_deviations), T7 (trunk_tilt), T8 (draw_annotated_frame), T9 (evidence functions)
**Reuses**: `pose_loader.load_sequence`, `pose.py`, `pose_features`, `pose_detector`, `pose_evidence`, `common.evidence`
**Requirement**: POSE-11, POSE-12, POSE-15, POSE-17

**Done when**:
- `run()` extracts keypoints once via `extract_all_keypoints` → `select_ground_person`
- Computes `windowed_features` once
- Runs `classify_with_persistence` → if `FALL_DETECTED`, calls `save_fall_evidence`
- Runs `detect_postural_deviations` → for each finding, calls `save_postural_evidence`
- Runs `detect_trunk_tilt` → for each finding, calls `save_postural_evidence`
- Logs: number of people detected, number of windows, number of findings per type, duration
- Zero findings → `SequenceVerdict(predicted="adl")` saved, no evidence, metrics.json still written
- Integration: full pipeline on synthetic video with both fall + bad knee → 2 evidence artifacts produced
- Integration: URFD fall sequence → FALL_DETECTED evidence (backward compat verified)
- Integration: URFD adl sequence + no joint config → zero findings, metrics.json only
- Existing `check` integration test still passes (unified pipeline, same contract)
- `ruff check backend/pipelines/video/cli.py` clean

**Tests**: integration
**Gate**: full

**Commit**: `feat(video-pose): wire unified pipeline with fall and physio detectors in sequence`

---

## Phase Execution Map

```
Phase 1: Foundation       T1 ──→ T2
Phase 2: Multi-Person     T3 ──→ T4
Phase 3: Detection        T5 ──→ T6 ──→ T7
Phase 4: Evidence         T8 ──→ T9
Phase 5: Integration      T10
```

## Granularity Check

| Task | Scope | Status |
| --- | --- | --- |
| T1: models.py dataclasses | 2 dataclasses, 1 file | ✅ Granular |
| T2: Config expansion | 1 file, ~10 new fields | ✅ Granular |
| T3: num_poses + extract_all | 1 function new, 1 modified, 1 file | ✅ Granular |
| T4: 4 feature functions | 4 functions, 1 file (same module) | ⚠️ Cohesive — all are geometric calculations on same landmarks |
| T5: classify_with_persistence | 1 function, 1 file | ✅ Granular |
| T6: detect_postural_deviations | 1 function, 1 file | ✅ Granular |
| T7: detect_trunk_tilt | 1 function, 1 file | ✅ Granular |
| T8: pose_evidence.py | 1 new file, 1 main function + helpers | ✅ Granular |
| T9: evidence functions | 2 functions, 1 file | ✅ Granular |
| T10: unified pipeline | 1 function rewrite, 1 file | ✅ Granular |

## Diagram-Definition Cross-Check

| Task | Depends On (body) | Diagram Shows | Status |
| --- | --- | --- | --- |
| T1 | None | (root) | ✅ Match |
| T2 | T1 | T1 → T2 | ✅ Match |
| T3 | None | (parallel to T1-T2) | ✅ Match |
| T4 | T1, T3 | T3 → T4 | ✅ Match |
| T5 | T4 | T4 → T5 | ✅ Match |
| T6 | T4, T1 | T4 → T6 | ✅ Match |
| T7 | T4, T1 | T6 → T7 (same phase) | ✅ Match |
| T8 | T1, T3 | T7 → T8 | ✅ Match |
| T9 | T8, T1 | T8 → T9 | ✅ Match |
| T10 | T2-T9 (all prior) | T9 → T10 | ✅ Match |

## Test Co-location Validation

| Task | Code Layer | Matrix Requires | Task Says | Status |
| --- | --- | --- | --- | --- |
| T1: models.py | Entity/Config | none | none | ✅ OK |
| T2: Config | Entity/Config | none | none | ✅ OK |
| T3: pose.py | Domain | unit | unit | ✅ OK |
| T4: pose_features.py | Domain | unit | unit | ✅ OK |
| T5: pose_detector.py | Domain | unit | unit | ✅ OK |
| T6: pose_detector.py | Domain | unit | unit | ✅ OK |
| T7: pose_detector.py | Domain | unit | unit | ✅ OK |
| T8: pose_evidence.py | Domain | unit | unit | ✅ OK |
| T9: pose_detector.py | Domain | unit | unit | ✅ OK |
| T10: cli.py run() | Integration | integration | integration | ✅ OK |
