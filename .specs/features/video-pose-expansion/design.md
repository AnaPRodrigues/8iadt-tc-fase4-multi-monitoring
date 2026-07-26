# Video Pose Analysis Expansion — Design

**Spec**: `.specs/features/video-pose-expansion/spec.md`
**Status**: Draft

---

## Architecture Overview

O pipeline de pose atual é linear: `extract_keypoints → windowed_features → classify_sequence → evidence`. A expansão executa **dois detetores em sequência** sobre os mesmos frames extraídos: queda (melhorado) + fisioterapia (novo). Ambos produzem achados independentes no mesmo `output/video_pose/<run_id>/`.

```mermaid
graph TD
    VIDEO[Video .mp4 / URFD] --> FRAMES[extrair frames]
    FRAMES --> KP[extract_all_keypoints<br/>num_poses=3]
    KP --> SEL[select_ground_person]
    SEL --> WF[windowed_features]

    WF --> FALL[classify_with_persistence]
    WF --> PHYSIO_DISPATCH

    FALL --> |FALL_DETECTED| EVID_FALL[save_fall_evidence]

    PHYSIO_DISPATCH --> JA[joint_angles_per_frame]
    PHYSIO_DISPATCH --> TT[trunk_tilt]
    JA --> DEV[detect_postural_deviations]
    TT --> TILT[detect_trunk_tilt]
    DEV --> |POSTURAL_DEVIATION| EVID_PH[save_postural_evidence]
    TILT --> |TRUNK_TILT| EVID_PH

    EVID_FALL --> OUT[output/video_pose/run_id/<br/>N × {annotated.png + evidence.json}]
    EVID_PH --> OUT
```

**Princípio**: Extração de keypoints feita **uma vez**. Ambos os detetores consomem os mesmos frames. Cada finding gera o seu próprio artefato — uma run pode produzir 0, 1, ou N evidências.

---

## Code Reuse Analysis

### Existing Components to Leverage

| Component | Location | How to Use |
| --- | --- | --- |
| `extract_keypoints` | `pose.py:62` | Mantida; nova `extract_all_keypoints` devolve `list[PoseFrame]` |
| `ensure_pose_model` | `pose.py:29` | Inalterado |
| `create_landmarker` | `pose.py:51` | Parâmetro `num_poses` injetado (default 3) |
| `windowed_features` | `pose_features.py:31` | Inalterado |
| `draw_keypoints` | `pose_detector.py:43` | Mantida para retrocompatibilidade; nova `draw_annotated_frame` em `pose_evidence.py` |
| `save_fall_evidence` | `pose_detector.py:60` | Metadados expandidos com `finding_type: "FALL_DETECTED"` |
| `Evidence` / `save_evidence` | `common/evidence.py` | Inalterado — contrato AD-026 |
| `MovementWindow`, `PoseFrame` | `models.py` | Mantidos; novos dataclasses adicionados |

### Integration Points

| System | Integration Method |
| --- | --- |
| `app/analise.py` | O dispatch do app extrai frames e chama `extract_keypoints`; as melhorias (`num_poses=3`, `select_ground_person`) são transparentes para o app. A análise unificada é exposta via `cli.py`; integração com o app (upload pelo frontend) é follow-up. |

---

## Components

### 1. `pose.py` — Extração multi-pessoa

- **Purpose**: Extrair keypoints com suporte a múltiplas pessoas
- **Location**: `backend/pipelines/video/pose.py`
- **Changes**:
  - `create_landmarker` ganha `num_poses: int = 3`
  - Nova `extract_all_keypoints(frame_path, landmarker) -> list[PoseFrame]` — itera `result.pose_landmarks`
  - `extract_keypoints` mantida como wrapper (retrocompatível)
- **Dependencies**: `mediapipe`, `cv2`
- **Reuses**: `ensure_pose_model`, `PoseFrame`

### 2. `pose_features.py` — Features + ângulos + seleção multi-pessoa

- **Purpose**: Métricas de movimento (existente) + ângulos articulares + seleção de pessoa no solo
- **Location**: `backend/pipelines/video/pose_features.py`
- **New interfaces**:
  - `select_ground_person(all_poses: list[list[PoseFrame | None]]) -> list[PoseFrame | None]` — por frame, seleciona a pose com menor Y médio (pessoa mais próxima do chão); frames sem pessoa → `None`
  - `joint_angle(frame: PoseFrame, a: int, b: int, c: int) -> float | None` — ângulo em `b` via produto escalar; `None` se visibilidade < 0.5 em qualquer landmark
  - `trunk_tilt(frame: PoseFrame) -> float | None` — ângulo espinha vs. eixo Y vertical
  - `joint_angles_per_frame(frame: PoseFrame, joints: list[tuple[str, int, int, int]]) -> dict[str, float | None]`
- **Existing (unchanged)**: `windowed_features`, `_center_of_mass`, `_asymmetry`

**Landmark indices** (MediaPipe Pose):

| Articulação | Landmarks (a–b–c) |
|---|---|
| Joelho esquerdo | 23–25–27 |
| Joelho direito | 24–26–28 |
| Cotovelo esquerdo | 11–13–15 |
| Cotovelo direito | 12–14–16 |
| Tronco (espinha) | mid(11,12) → mid(23,24) |

### 3. `pose_detector.py` — Quedas com persistência + Desvios posturais

- **Purpose**: Deteção de queda com filtro temporal + desvios posturais + inclinação de tronco
- **Location**: `backend/pipelines/video/pose_detector.py`
- **New interfaces**:
  - `classify_with_persistence(windows: list[MovementWindow], threshold: float, persistence_frames: int) -> tuple[str, int | None]` — queda só se `persistence_frames` janelas consecutivas > threshold; reset quando cai abaixo
  - `detect_postural_deviations(frames: list[PoseFrame | None], joint_targets: dict[str, JointTarget], persistence_frames: int, fps: float) -> list[PosturalFinding]`
  - `detect_trunk_tilt(frames: list[PoseFrame | None], max_angle: float, persistence_frames: int, fps: float) -> list[PosturalFinding]`
- **Existing (unchanged)**: `classify_sequence`, `draw_keypoints`
- **Existing (modified)**: `save_fall_evidence` → metadados expandidos

**Default thresholds**:

| Parâmetro | Default |
|---|---|
| `fall_threshold` | `0.55` |
| `persistence_frames` | `30` (~1s) |
| `knee_flexion_min` | `70°` |
| `elbow_flexion_min` | `70°` |
| `trunk_tilt_max` | `30°` |
| `tilt_persistence_frames` | `90` (~3s) |

### 4. `pose_evidence.py` — Evidência anotada (NOVO)

- **Purpose**: Desenhar esqueleto + articulações destacadas + ângulos sobrepostos
- **Location**: `backend/pipelines/video/pose_evidence.py`
- **Interfaces**:
  - `draw_annotated_frame(frame_path: Path, pose_frame: PoseFrame, findings: list[PosturalFinding], output_path: Path) -> Path`
  - Esqueleto azul (todos os landmarks), articulações anómalas amarelo/vermelho, ângulos como texto
- **Dependencies**: `cv2`, `models.py`

### 5. `models.py` — Novos dataclasses

- **Location**: `backend/pipelines/video/models.py`
- **New** (aditivos, sem alterar existentes):

```python
@dataclass(frozen=True)
class JointTarget:
    joint_name: str
    landmark_a: int
    landmark_b: int
    landmark_c: int
    min_angle: float
    target_angle: float

@dataclass(frozen=True)
class PosturalFinding:
    finding_type: str  # "FALL_DETECTED" | "POSTURAL_DEVIATION" | "TRUNK_TILT"
    joint_name: str | None
    measured_angle: float
    expected_angle: float
    duration_s: float
    frame_index: int
    score: float
    description: str
```

### 6. `cli.py` — Pipeline unificado

- **Purpose**: Orquestrar ambos os detetores em sequência
- **Location**: `backend/pipelines/video/cli.py`
- **Changes**:
  - `DEFAULTS` expandido com todos os parâmetros (queda + fisio)
  - `run()`: extrai keypoints → `select_ground_person` → `windowed_features` → **`classify_with_persistence` + `detect_postural_deviations` + `detect_trunk_tilt`** em sequência → todos os findings geram evidência
- **Dependencies**: `pose_features`, `pose_detector`, `pose_evidence`

---

## Data Models

### Config YAML (exemplo completo)

```yaml
dataset_dir: data/urfd
window_size: 30
output_root: output
model_cache_dir: models

# Queda
fall_threshold: 0.55
persistence_frames: 30

# Fisioterapia
num_poses: 3
tilt_persistence_frames: 90
trunk_tilt_max: 30
joint_targets:
  - joint_name: knee_left
    landmark_a: 23
    landmark_b: 25
    landmark_c: 27
    min_angle: 70
    target_angle: 90
  - joint_name: knee_right
    landmark_a: 24
    landmark_b: 26
    landmark_c: 28
    min_angle: 70
    target_angle: 90
```

### Evidence sidecar JSON (expandido)

```json
{
  "evidence_id": "squat-knee-left-62deg",
  "feature": "video_pose",
  "run_id": "20260725-130000",
  "source_record_id": "squat-therapy",
  "artifact": "squat-knee-left-62deg.png",
  "metadata": {
    "finding_type": "POSTURAL_DEVIATION",
    "joint_name": "knee_left",
    "measured_angle": 62.0,
    "expected_angle": 70.0,
    "duration_s": 1.8,
    "frame_index": 95,
    "score": 0.42,
    "description": "Amplitude articular reduzida em flexão de joelho esquerdo (alcançado: 62°, esperado: >70°)."
  }
}
```

---

## Error Handling Strategy

| Error Scenario | Handling |
| --- | --- |
| Vídeo corrompido | `ErroDeAnalise` (POSE-16) |
| Nenhuma pessoa em todos os frames | "Nenhuma pessoa identificada", `pontuacao=None` (POSE-13) |
| Ângulo NaN | Frame descartado do contador (POSE-19) |
| `num_poses` > pessoas reais | Usa as que existem (POSE-18) |
| Campo desconhecido na config | `ValueError` (padrão do projeto) |
| Run sem findings | Pontuação 0.0, resumo "Nenhuma alteração detectada" |

---

## Risks & Concerns

| Concern | Location | Impact | Mitigation |
| --- | --- | --- | --- |
| `classify_sequence` usada por `app/analise.py` | `pose_detector.py:28` + `analise.py:131,262` | Mudar assinatura quebraria o app | Nova `classify_with_persistence` à parte; app continua com `classify_sequence` |
| `num_poses=3` aumenta latência | `pose.py:57` | ~2-3x mais lento por frame | Modelo lite; CPU-bound aceite (AD-012); configurável |
| `draw_annotated_frame` duplica `draw_keypoints` | `pose_detector.py:43` vs `pose_evidence.py` | Duplicação de código de desenho | `draw_keypoints` mantida para testes existentes; unificação follow-up |
| Testes existentes usam `DEFAULT_FALL_THRESHOLD = 0.3` | `tests/video/` | Subir para 0.55 quebraria testes | Constante antiga mantida; nova `DEFAULT_FALL_THRESHOLD_V2 = 0.55` |

---

## Tech Decisions

| Decision | Choice | Rationale |
| --- | --- | --- |
| Detetores em sequência vs. paralelo | Sequência | CPU-only (AD-012); paralelismo não traria ganho real. Os frames já estão em memória. |
| `num_poses` default | `3` | Cobre paciente + 2 profissionais no quarto |
| Ângulo via produto escalar | `arccos((v1·v2) / (\|v1\|*\|v2\|))` | Geometria padrão, sem dependência extra |
| Score `POSTURAL_DEVIATION` | `1.0 - (measured / expected)`, clamped [0,1] | Linear, explicável: 0 = atingiu target, 1 = sem amplitude |
| Score `TRUNK_TILT` | `min(1.0, tilt / (2 * max_angle))` | 0.5 no limiar, 1.0 no dobro |
| Evidência multi-finding | 1 artefato por finding | Contrato AD-026; cada `evidence_id` é único |
