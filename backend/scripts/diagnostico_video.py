"""Diagnóstico de features da pipeline de vídeo.

Extrai e exporta features intermédias para cada frame/track de um vídeo,
permitindo comparar objetivamente por que um vídeo detecta queda e outro não.

Uso:
    PYTHONPATH=backend python -m scripts.diagnostico_video <video_path> [--max-frames N] [--step N]
"""

import argparse
import json
import sys
from pathlib import Path

import cv2


def diagnostico(video_path: Path, max_frames: int = 0, step: int = 1) -> dict:
    """Extrai features diagnósticas de cada frame de um vídeo."""
    from pipelines.video.pose import (
        create_landmarker,
        ensure_pose_model,
        extract_all_keypoints,
        reset_person_tracker,
    )
    from pipelines.video.pose_features import (
        group_poses_by_track_id,
        hip_center,
        is_recumbent,
        torso_height,
        trunk_tilt,
        vertical_velocity,
        vertical_velocity_robust,
        was_initially_recumbent,
    )

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return {"error": f"não foi possível abrir: {video_path}"}

    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    if fps <= 0:
        fps = 30.0

    # Extrai frames
    frame_paths: list[Path] = []
    tmp_dir = Path("/tmp/video_diag")
    tmp_dir.mkdir(parents=True, exist_ok=True)
    for f in Path(tmp_dir).glob("frame_*.png"):
        f.unlink()

    idx = 0
    saved = 0
    limit = max_frames if max_frames > 0 else total_frames
    while saved < limit:
        ret, frame = cap.read()
        if not ret:
            break
        if idx % step == 0:
            out = tmp_dir / f"frame_{saved:06d}.png"
            cv2.imwrite(str(out), frame)
            frame_paths.append(out)
            saved += 1
        idx += 1
    cap.release()

    # Pipeline de pose
    model_path = ensure_pose_model(Path("models"))
    landmarker = create_landmarker(model_path, num_poses=3)
    reset_person_tracker()
    all_poses = [extract_all_keypoints(p, landmarker) for p in frame_paths]

    # Agrupa por track_id
    person_timelines = group_poses_by_track_id(all_poses)
    n_pessoas = len(person_timelines)

    # Features por pessoa
    pessoas: dict = {}
    for tid, person_frames in person_timelines.items():
        n_valid = sum(1 for f in person_frames if f is not None)
        if n_valid < 3:
            continue

        # Vy
        vy_list = vertical_velocity_robust(person_frames)
        vy_valid = [v for v in vy_list if v is not None]

        # Torso
        torso_vals = [torso_height(f) for f in person_frames if f is not None and torso_height(f) is not None]
        avg_torso = sum(torso_vals) / len(torso_vals) if torso_vals else 0.0

        # Tilt
        tilts = [trunk_tilt(f) for f in person_frames if f is not None and trunk_tilt(f) is not None]

        # Hip Y ao longo do tempo
        hip_y_vals: list[float | None] = []
        for f in person_frames:
            if f is None:
                hip_y_vals.append(None)
                continue
            hc = hip_center(f)
            hip_y_vals.append(hc[1] if hc else None)

        # Y range (amplitude do quadril)
        valid_hip_y = [y for y in hip_y_vals if y is not None]
        y_amplitude = max(valid_hip_y) - min(valid_hip_y) if valid_hip_y else 0.0

        # Vy normalizado por torso
        vy_norm = [v / max(avg_torso, 0.01) for v in vy_valid] if vy_valid else []

        # FPS scaling (120fps → multiplicar por 4)
        fps_scale = fps / 30.0
        vy_scaled = [v * fps_scale for v in vy_valid] if vy_valid else []

        pessoas[str(tid)] = {
            "n_frames_validos": n_valid,
            "n_frames_total": len(person_frames),
            "pct_validos": round(n_valid / max(len(person_frames), 1) * 100, 1),
            "avg_torso_height": round(avg_torso, 4),
            "hip_y_inicio": round(valid_hip_y[0], 4) if valid_hip_y else None,
            "hip_y_fim": round(valid_hip_y[-1], 4) if valid_hip_y else None,
            "hip_y_amplitude": round(y_amplitude, 4),
            "vy_max_raw": round(max(vy_valid), 4) if vy_valid else 0.0,
            "vy_max_scaled": round(max(vy_scaled), 4) if vy_scaled else 0.0,
            "vy_max_norm": round(max(vy_norm), 4) if vy_norm else 0.0,
            "vy_mean": round(sum(vy_valid) / len(vy_valid), 4) if vy_valid else 0.0,
            "tilt_max": round(max(tilts), 1) if tilts else 0.0,
            "tilt_p90": round(sorted(tilts)[int(len(tilts) * 0.9)], 1) if len(tilts) >= 10 else 0.0,
            "is_recumbent_final": is_recumbent(person_frames),
            "was_initially_recumbent": was_initially_recumbent(person_frames),
            "vy_streak_max": _max_consecutive_above(vy_valid, 0.02),
            "total_displacement": round(sum(v for v in vy_valid if v > 0), 4),
            "total_displacement_scaled": round(sum(v for v in vy_scaled if v > 0), 4),
        }

    # Cleanup
    for f in frame_paths:
        f.unlink(missing_ok=True)

    return {
        "video": str(video_path),
        "fps": fps,
        "total_frames": total_frames,
        "resolution": f"{w}x{h}",
        "frames_extraidos": len(frame_paths),
        "step": step,
        "n_pessoas_detectadas": n_pessoas,
        "pessoas": pessoas,
    }


def _max_consecutive_above(values: list[float], threshold: float) -> int:
    max_streak = 0
    current = 0
    for v in values:
        if v > threshold:
            current += 1
            max_streak = max(max_streak, current)
        else:
            current = 0
    return max_streak


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Diagnóstico de features da pipeline de vídeo")
    parser.add_argument("video", type=Path, help="Caminho para o ficheiro de vídeo")
    parser.add_argument("--max-frames", type=int, default=0, help="Nº máximo de frames a extrair (0=todos)")
    parser.add_argument("--step", type=int, default=1, help="Amostrar 1 a cada N frames")
    parser.add_argument("--output", type=Path, default=None, help="Ficheiro JSON de saída")
    args = parser.parse_args(argv)

    if not args.video.is_file():
        print(f"ERRO: vídeo não encontrado: {args.video}", file=sys.stderr)
        return 1

    print(f"Analisando {args.video.name}...", file=sys.stderr)
    result = diagnostico(args.video, args.max_frames, args.step)

    output = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output:
        args.output.write_text(output, encoding="utf-8")
        print(f"Resultado escrito em {args.output}", file=sys.stderr)
    else:
        print(output)

    return 0


if __name__ == "__main__":
    sys.exit(main())
