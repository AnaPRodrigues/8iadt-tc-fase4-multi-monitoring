"""Métricas de movimento por janela, derivadas do centro de massa.

A fórmula exata de assimetria postural não é fixada a priori
("assimetria postural" é descrito só qualitativamente). Adotada a
diferença absoluta entre a altura (y) dos dois landmarks de quadril (23/24) --
mesmos landmarks usados para o centro de massa, sem introduzir um terceiro par
de pontos não mencionado no design. Calibrável na prática, mesmo princípio de
threshold usado para detecção de queda (ver `pose_detector.py`).
"""

import math

from pipelines.video.models import MovementWindow, PoseFrame

_LEFT_HIP = 23
_RIGHT_HIP = 24


def _center_of_mass(frame: PoseFrame) -> tuple[float, float]:
    lx, ly, _, _ = frame.landmarks[_LEFT_HIP]
    rx, ry, _, _ = frame.landmarks[_RIGHT_HIP]
    return ((lx + rx) / 2.0, (ly + ry) / 2.0)


def _asymmetry(frame: PoseFrame) -> float:
    _, ly, _, _ = frame.landmarks[_LEFT_HIP]
    _, ry, _, _ = frame.landmarks[_RIGHT_HIP]
    return abs(ly - ry)


def windowed_features(frames: list[PoseFrame | None], window_size: int) -> list[MovementWindow]:
    """Calcula amplitude/velocidade do centro de massa e assimetria por janela.

    Frames `None` (sem pessoa detectada) são excluídos do cálculo da
    janela em que caem, sem quebrar as demais. Uma janela sem nenhum frame
    válido não é gerada -- não existe `MovementWindow` com valores inventados.
    `end_frame` é inclusivo (último índice de frame coberto pela janela).
    """
    if window_size <= 0:
        raise ValueError("window_size precisa ser positivo")

    windows: list[MovementWindow] = []
    for start in range(0, len(frames), window_size):
        end = min(start + window_size, len(frames))
        indices_validos = [i for i in range(start, end) if frames[i] is not None]
        if not indices_validos:
            continue

        pontos = [_center_of_mass(frames[i]) for i in indices_validos]

        if len(pontos) >= 2:
            amplitude = max(
                math.dist(pontos[a], pontos[b])
                for a in range(len(pontos))
                for b in range(a + 1, len(pontos))
            )
            deslocamentos = [math.dist(pontos[i], pontos[i - 1]) for i in range(1, len(pontos))]
            velocidade = sum(deslocamentos) / len(deslocamentos)
        else:
            amplitude = 0.0
            velocidade = 0.0

        assimetria = sum(_asymmetry(frames[i]) for i in indices_validos) / len(indices_validos)

        windows.append(
            MovementWindow(
                start_frame=start,
                end_frame=end - 1,
                center_of_mass_amplitude=amplitude,
                velocity=velocidade,
                asymmetry=assimetria,
            )
        )

    return windows


# --------------------------------------------------------------------------- #
# Constantes compartilhadas
# --------------------------------------------------------------------------- #
_MIN_VISIBILITY = 0.4  # threshold unificado de visibilidade (lençóis/oclusão parcial)
_SHOULDER_LEFT = 11
_SHOULDER_RIGHT = 12
_HIP_LEFT = 23
_HIP_RIGHT = 24
_NOSE = 0
_EAR_LEFT = 7
_EAR_RIGHT = 8
_MIN_CONSECUTIVE_FRAMES = 2  # frames consecutivos mínimos para validar deteção


# --------------------------------------------------------------------------- #
# Velocidade vertical do centro de massa (filtro anti-estático de queda)
# --------------------------------------------------------------------------- #
def vertical_velocity(
    frames: list[PoseFrame | None],
) -> list[float | None]:
    """Velocidade vertical do centro de massa (quadril) por frame.

    Calcula $V_y = (Y_{atual} - Y_{anterior}) / 1$ frame. O eixo Y do
    MediaPipe cresce para baixo — uma queda real produz um pico positivo
    de $V_y$ (o quadril desce rapidamente na imagem).

    Devolve ``None`` para frames sem pessoa ou sem frame anterior válido.
    """
    velocities: list[float | None] = []
    prev_y: float | None = None

    for frame in frames:
        if frame is None:
            velocities.append(None)
            prev_y = None
            continue

        # Centro de massa: ponto médio dos quadris (23, 24)
        ly = frame.landmarks[23][1]
        ry = frame.landmarks[24][1]
        lv = frame.landmarks[23][3]
        rv = frame.landmarks[24][3]
        if lv < _MIN_VISIBILITY or rv < _MIN_VISIBILITY:
            velocities.append(None)
            prev_y = None
            continue

        current_y = (ly + ry) / 2.0

        vy = current_y - prev_y if prev_y is not None else None

        velocities.append(vy)
        prev_y = current_y

    return velocities


def _upper_body_center(frame: PoseFrame) -> tuple[float, float] | None:
    """Centro da parte superior do corpo (cabeça + ombros).

    Usado como fallback quando pernas/quadril estão ocluídos por lençóis.
    Requer pelo menos cabeça (nariz) e ombros com visibilidade mínima.
    """
    nose_v = frame.landmarks[_NOSE][3]
    sl_v = frame.landmarks[_SHOULDER_LEFT][3]
    sr_v = frame.landmarks[_SHOULDER_RIGHT][3]
    if nose_v < _MIN_VISIBILITY or sl_v < _MIN_VISIBILITY or sr_v < _MIN_VISIBILITY:
        return None
    cx = (
        frame.landmarks[_NOSE][0] + frame.landmarks[_SHOULDER_LEFT][0]
        + frame.landmarks[_SHOULDER_RIGHT][0]
    ) / 3.0
    cy = (
        frame.landmarks[_NOSE][1] + frame.landmarks[_SHOULDER_LEFT][1]
        + frame.landmarks[_SHOULDER_RIGHT][1]
    ) / 3.0
    return (cx, cy)


def hip_center(frame: PoseFrame) -> tuple[float, float] | None:
    """Centro do quadril (ponto médio dos landmarks 23/24).

    Devolve ``None`` se visibilidade insuficiente (oclusão por lençóis).
    """
    lv = frame.landmarks[_HIP_LEFT][3]
    rv = frame.landmarks[_HIP_RIGHT][3]
    if lv < _MIN_VISIBILITY or rv < _MIN_VISIBILITY:
        return None
    return (
        (frame.landmarks[_HIP_LEFT][0] + frame.landmarks[_HIP_RIGHT][0]) / 2.0,
        (frame.landmarks[_HIP_LEFT][1] + frame.landmarks[_HIP_RIGHT][1]) / 2.0,
    )


def vertical_velocity_robust(
    frames: list[PoseFrame | None],
) -> list[float | None]:
    """Velocidade vertical com fallback para oclusão parcial.

    Tenta usar o quadril primeiro. Se o quadril estiver ocluído (lençóis),
    usa a parte superior do corpo (cabeça + ombros). Devolve ``None`` se
    nenhuma das duas estiver disponível.

    Uma transição rápida da cabeça/ombro para a borda inferior da imagem
    é suficiente para disparar a queda (Requisito 2).
    """
    velocities: list[float | None] = []
    prev_y: float | None = None

    for frame in frames:
        if frame is None:
            velocities.append(None)
            prev_y = None
            continue

        # Tenta quadril primeiro; fallback para upper body
        center = hip_center(frame)
        if center is None:
            center = _upper_body_center(frame)

        if center is None:
            velocities.append(None)
            prev_y = None
            continue

        current_y = center[1]
        if prev_y is not None:
            vy = current_y - prev_y
        else:
            vy = None
        velocities.append(vy)
        prev_y = current_y

    return velocities


def lateral_displacement(
    frames: list[PoseFrame | None],
) -> list[float | None]:
    """Deslocamento lateral ($\\Delta X$) do centro de massa por frame.

    Usado para detectar rolamento/escorregamento: o corpo desliza para fora
    do leito enquanto o tronco inclina.
    """
    displacements: list[float | None] = []
    prev_x: float | None = None

    for frame in frames:
        if frame is None:
            displacements.append(None)
            prev_x = None
            continue
        center = hip_center(frame)
        if center is None:
            center = _upper_body_center(frame)
        if center is None:
            displacements.append(None)
            prev_x = None
            continue
        current_x = center[0]
        if prev_x is not None:
            displacements.append(abs(current_x - prev_x))
        else:
            displacements.append(None)
        prev_x = current_x

    return displacements


def total_displacement(
    velocities: list[float | None],
) -> float:
    """Deslocamento vertical total acumulado ($\\Delta Y$) durante a descida.

    Soma todos os $V_y$ positivos (descida). Uma acompanhante sentada pode
    mexer os braços (jitter), mas seu tronco nunca acumula $\\Delta Y \\ge 0.20$.
    Uma queda real do leito produz $\\Delta Y \\ge 0.20$ facilmente.

    Devolve 0.0 se não houver dados suficientes.
    """
    valid = [v for v in velocities if v is not None and v > 0.0]
    if not valid:
        return 0.0
    return sum(valid)


def max_vertical_velocity(
    velocities: list[float | None], window_frames: int = 15
) -> float:
    """Maior velocidade vertical no sinal (pico de descida).

    Aceita frames isolados acima do piso — o filtro anti-jitter é feito
    pelo ``total_displacement``, não por consecutividade. Para CCTV/15fps,
    o pico de descida pode durar apenas 1-2 frames.

    Devolve 0.0 se nenhum valor ultrapassar o piso.
    """
    valid = [v for v in velocities if v is not None and v > 0.01]
    if not valid:
        return 0.0
    return max(valid)


def max_consecutive_above(
    values: list[float | None], threshold: float,
) -> int:
    """Maior número de valores consecutivos acima de ``threshold``.

    Usado para distinguir descidas sustentadas (queda real) de picos
    isolados de velocidade (glitch de detecção em ADL). Uma queda real
    mantém Vy elevado por vários frames consecutivos; um glitch aparece
    como um único frame isolado.

    Devolve 0 se a lista estiver vazia ou sem valores acima do threshold.
    """
    max_streak = 0
    current = 0
    for v in values:
        if v is not None and v > threshold:
            current += 1
            max_streak = max(max_streak, current)
        else:
            current = 0
    return max_streak


def _min_visibility(frame: PoseFrame, indices: list[int]) -> float:
    """Menor visibilidade entre os landmarks pedidos — gate de qualidade.

    Qualquer landmark com visibilidade < 0.5 invalida o cálculo (POSE-19).
    """
    return min(frame.landmarks[i][3] for i in indices)


def _landmark_xy(frame: PoseFrame, idx: int) -> tuple[float, float]:
    return (frame.landmarks[idx][0], frame.landmarks[idx][1])


# Estado de persistência do ground person (ITER2-01)
_ground_person_state: dict = {
    "dominant_tid": None,     # track_id dominante (int | None)
    "frames_absent": 0,       # frames consecutivos sem o dominant_tid
}
_MAX_ABSENT_FRAMES = 30       # frames antes de recalcular o dominante
_DOMINANT_WINDOW = 60         # frames iniciais para determinar o dominante


def reset_ground_person_state() -> None:
    """Reinicia o estado de persistência do ground person (entre sequências)."""
    global _ground_person_state
    _ground_person_state = {
        "dominant_tid": None,
        "frames_absent": 0,
    }


def select_ground_person(
    all_poses: list[list[PoseFrame | None]],
) -> tuple[list[PoseFrame | None], list[int | None]]:
    """Seleciona a pessoa ground-track com persistência de track_id (ITER2-01).

    Com tracking ativo, uma vez identificado o track_id dominante, mantém-no
    ao longo da sequência — evitando saltos de identidade que geram amplitude
    artificial no centro de massa. Recalcula o dominante apenas se a pessoa
    desaparecer por > ``_MAX_ABSENT_FRAMES`` frames consecutivos.

    Sem tracking (todos track_id=None), mantém o comportamento original:
    seleção por Y máximo em cada frame.

    Aplica filtros anti-alucinação:
    1. Visibilidade média ≥ ``_MIN_VISIBILITY`` (pessoa real vs. objeto)
    2. Consistência temporal ≥ ``_MIN_CONSECUTIVE_FRAMES`` frames consecutivos

    Devolve ``(frames, track_ids)`` — ambos com o mesmo comprimento.
    """
    global _ground_person_state

    n = len(all_poses)
    result: list[PoseFrame | None] = [None] * n
    track_ids: list[int | None] = [None] * n

    # Detecta se há tracking ativo
    has_tracking = any(
        p is not None and p.track_id is not None
        for poses in all_poses if poses
        for p in poses if p is not None
    )

    # Fallback: sem tracking → comportamento original
    if not has_tracking:
        _ground_person_state["dominant_tid"] = None
        _ground_person_state["frames_absent"] = 0

    # Primeiro, computa a "qualidade" de cada pose por frame
    scored: list[list[tuple[PoseFrame, float, float, int | None]]] = []
    for poses in all_poses:
        frame_scores: list[tuple[PoseFrame, float, float, int | None]] = []
        for p in poses:
            if p is None:
                continue
            avg_vis = sum(lm[3] for lm in p.landmarks) / len(p.landmarks)
            avg_y = sum(lm[1] for lm in p.landmarks) / len(p.landmarks)
            if avg_vis >= _MIN_VISIBILITY:
                frame_scores.append((p, avg_y, avg_vis, p.track_id))
        scored.append(frame_scores)

    # Filtro temporal
    for i in range(n):
        if not scored[i]:
            continue
        streak = 0
        for j in range(max(0, i - 5), min(n, i + 6)):
            if scored[j]:
                streak += 1
                if streak >= _MIN_CONSECUTIVE_FRAMES:
                    break
            else:
                streak = 0
        if streak < _MIN_CONSECUTIVE_FRAMES:
            scored[i] = []

    if not has_tracking:
        # Comportamento original: Y máximo por frame
        for i in range(n):
            if not scored[i]:
                result[i] = None
                track_ids[i] = None
            else:
                best = max(scored[i], key=lambda x: x[1])
                result[i] = best[0]
                track_ids[i] = best[0].track_id
        return result, track_ids

    # --- Persistência de track_id ---

    # Determina o track_id dominante se ainda não foi definido
    state = _ground_person_state
    if state["dominant_tid"] is None:
        # Conta frequência de cada track_id como "ground person" nos primeiros _DOMINANT_WINDOW frames
        tid_y_sum: dict[int, tuple[float, int]] = {}
        for i in range(min(_DOMINANT_WINDOW, n)):
            if not scored[i]:
                continue
            best = max(scored[i], key=lambda x: x[1])
            tid = best[3]
            if tid is not None:
                curr_sum, count = tid_y_sum.get(tid, (0.0, 0))
                tid_y_sum[tid] = (curr_sum + best[1], count + 1)

        if tid_y_sum:
            # Escolhe o track_id com maior Y médio
            dominant = max(tid_y_sum.items(), key=lambda kv: kv[1][0] / kv[1][1])
            state["dominant_tid"] = dominant[0]

    dominant_tid = state["dominant_tid"]

    for i in range(n):
        if not scored[i]:
            result[i] = None
            track_ids[i] = None
            continue

        # Procura a pose com o track_id dominante neste frame
        dominant_pose = None
        best_fallback = None
        best_fallback_y = -1.0

        for p, y, _vis, tid in scored[i]:
            if tid == dominant_tid:
                dominant_pose = p
                break
            if y > best_fallback_y:
                best_fallback_y = y
                best_fallback = p

        if dominant_pose is not None:
            result[i] = dominant_pose
            track_ids[i] = dominant_tid
            state["frames_absent"] = 0
        elif best_fallback is not None:
            # Dominante ausente neste frame
            result[i] = best_fallback
            track_ids[i] = best_fallback.track_id
            state["frames_absent"] += 1

            # Recalcula se ausente por muitos frames
            if state["frames_absent"] > _MAX_ABSENT_FRAMES:
                state["dominant_tid"] = None
                state["frames_absent"] = 0
        else:
            result[i] = None
            track_ids[i] = None

    return result, track_ids


def find_pose_by_track_id(
    all_poses: list[list[PoseFrame | None]],
    frame_idx: int,
    track_id: int,
) -> PoseFrame | None:
    """Encontra o ``PoseFrame`` com um ``track_id`` específico em ``all_poses[frame_idx]``.

    Útil para desenhar evidência da pessoa exata que disparou o evento de queda,
    eliminando a dependência do índice posicional da lista (que muda entre frames).
    Devolve ``None`` se o track_id não estiver presente nesse frame (ex.: oclusão).
    """
    if frame_idx < 0 or frame_idx >= len(all_poses):
        return None
    poses = all_poses[frame_idx]
    if not poses:
        return None
    for p in poses:
        if p is not None and p.track_id == track_id:
            return p
    return None


def dominant_track_id(
    track_ids: list[int | None],
    window_start: int,
    window_end: int,
) -> int | None:
    """Determina o ``track_id`` dominante numa janela temporal.

    Conta a frequência de cada track_id (ignorando ``None``) e devolve o mais
    frequente. Usado para identificar qual pessoa disparou a queda quando o
    ``select_ground_person`` alterna entre track_ids ao longo da sequência.

    Devolve ``None`` se não houver track_ids válidos na janela.
    """
    from collections import Counter

    subset = [
        tid
        for tid in track_ids[window_start:window_end]
        if tid is not None
    ]
    if not subset:
        return None
    return Counter(subset).most_common(1)[0][0]


def is_recumbent(
    person_frames: list[PoseFrame | None],
    window_frames: int = 90,
    min_valid_frames: int = 10,
    y_threshold: float = 0.45,
) -> bool:
    """Determina se uma pessoa já está deitada com base numa janela deslizante.

    Examina os últimos ``window_frames`` frames válidos (não-None) da timeline
    da pessoa e calcula a posição Y média dos quadris. Se a média for superior
    a ``y_threshold``, a pessoa é classificada como recumbent (já deitada).

    Usa ``hip_center`` primeiro; se o quadril estiver ocluído (visibilidade
    < 0.5), faz fallback para ``_upper_body_center`` (cabeça + ombros).

    Devolve ``False`` se houver menos de ``min_valid_frames`` frames válidos
    na janela — dados insuficientes para classificar, não se assume deitada.

    Args:
        person_frames: Timeline de uma única pessoa (por track_id).
        window_frames: Tamanho da janela deslizante (default 90 ≈ 3s a 30fps).
        min_valid_frames: Mínimo de frames válidos para classificar.
        y_threshold: Y médio acima do qual a pessoa é considerada deitada.
    """
    recent = person_frames[-window_frames:] if len(person_frames) > window_frames else person_frames

    y_values: list[float] = []
    for f in recent:
        if f is None:
            continue
        center = hip_center(f)
        if center is None:
            center = _upper_body_center(f)
        if center is not None:
            y_values.append(center[1])

    if len(y_values) < min_valid_frames:
        return False

    return (sum(y_values) / len(y_values)) > y_threshold


def was_initially_recumbent(
    person_frames: list[PoseFrame | None],
    initial_window: int = 30,
    min_valid_frames: int = 5,
    y_threshold: float = 0.65,
) -> bool:
    """Verifica se a pessoa já estava deitada no INÍCIO da sequência.

    Diferente de ``is_recumbent()``, que olha para os últimos 90 frames
    (janela deslizante no final), esta função examina apenas os primeiros
    ``initial_window`` frames. Se a pessoa já está com Y > ``y_threshold``
    no início, é porque entrou na cena já deitada — não sofreu uma queda
    durante este vídeo.

    Usada como gate para pular a detecção de queda em pessoas que já
    estavam no chão/cama antes da gravação começar. Pessoas que começam
    de pé (Y < threshold) e depois caem NÃO são filtradas por esta função.

    Devolve ``False`` se houver menos de ``min_valid_frames`` frames
    válidos no início — conservador: na dúvida, executa o detector.
    """
    initial = person_frames[:initial_window]

    y_values: list[float] = []
    for f in initial:
        if f is None:
            continue
        center = hip_center(f)
        if center is None:
            center = _upper_body_center(f)
        if center is not None:
            y_values.append(center[1])

    if len(y_values) < min_valid_frames:
        return False

    return (sum(y_values) / len(y_values)) > y_threshold


def group_poses_by_track_id(
    all_poses_per_frame: list[list[PoseFrame | None]],
) -> dict[int, list[PoseFrame | None]]:
    """Agrupa poses por ``track_id`` ao longo de todos os frames.

    Constrói uma timeline independente para cada identidade rastreada,
    preenchendo com ``None`` os frames em que o track_id não está presente.
    Poses com ``track_id=None`` (sem tracking ativo) são excluídas.

    Usar esta função em vez de iterar por índice posicional (``p_idx``)
    garante que as métricas de movimento de cada pessoa são computadas
    apenas sobre os frames em que a sua identidade está presente, sem
    contaminação cruzada entre pessoas diferentes.

    Args:
        all_poses_per_frame: Lista de frames, cada um com uma lista de
            ``PoseFrame | None`` (uma por pessoa detetada).

    Returns:
        Dicionário ``track_id → timeline``, onde a timeline é uma lista
        de ``PoseFrame | None`` com o mesmo comprimento que
        ``all_poses_per_frame``.
    """
    from collections import defaultdict

    if not all_poses_per_frame:
        return {}

    n_frames = len(all_poses_per_frame)
    person_timeline: dict[int, list[PoseFrame | None]] = defaultdict(
        lambda: [None] * n_frames
    )

    for frame_idx, poses in enumerate(all_poses_per_frame):
        if not poses:
            continue
        for p in poses:
            if p is not None and p.track_id is not None:
                person_timeline[p.track_id][frame_idx] = p

    return dict(person_timeline)


def classify_person_role(
    person_frames: list[PoseFrame | None],
    standing_y_threshold: float = 0.35,
    min_valid_frames: int = 10,
    standing_window: int = 30,
) -> str:
    """Classifica o papel de uma pessoa com base na posição Y dos quadris.

    Usa ``is_recumbent()`` (janela deslizante de 90 frames, Y > 0.45) para
    a classe "recumbent". Para "standing", verifica a média de Y nos últimos
    ``standing_window`` frames; se < ``standing_y_threshold``, a pessoa está
    de pé. Caso contrário, está em transição ("transitioning").

    Devolve "unknown" se houver menos de ``min_valid_frames`` frames válidos.

    Returns:
        "recumbent" | "standing" | "transitioning" | "unknown"
    """
    valid_count = sum(1 for f in person_frames if f is not None)
    if valid_count < min_valid_frames:
        return "unknown"

    if is_recumbent(person_frames):
        return "recumbent"

    # Y médio dos últimos standing_window frames válidos
    recent = person_frames[-standing_window:] if len(person_frames) > standing_window else person_frames
    y_values: list[float] = []
    for f in recent:
        if f is None:
            continue
        center = hip_center(f)
        if center is None:
            center = _upper_body_center(f)
        if center is not None:
            y_values.append(center[1])

    if len(y_values) >= min_valid_frames:
        avg_y = sum(y_values) / len(y_values)
        if avg_y < standing_y_threshold:
            return "standing"

    return "transitioning"


def joint_angle(
    frame: PoseFrame, a: int, b: int, c: int
) -> float | None:
    """Ângulo no landmark ``b`` formado pelos vetores ``a→b`` e ``c→b``.

    Usa o produto escalar: θ = arccos((v1·v2) / (|v1|·|v2|)). Devolve graus.
    ``None`` se qualquer um dos 3 landmarks tiver visibilidade < 0.5.
    """
    if _min_visibility(frame, [a, b, c]) < _MIN_VISIBILITY:
        return None

    ax, ay = _landmark_xy(frame, a)
    bx, by = _landmark_xy(frame, b)
    cx, cy = _landmark_xy(frame, c)

    v1 = (ax - bx, ay - by)
    v2 = (cx - bx, cy - by)

    dot = v1[0] * v2[0] + v1[1] * v2[1]
    mag1 = (v1[0] ** 2 + v1[1] ** 2) ** 0.5
    mag2 = (v2[0] ** 2 + v2[1] ** 2) ** 0.5

    if mag1 == 0 or mag2 == 0:
        return None

    cos_theta = max(-1.0, min(1.0, dot / (mag1 * mag2)))
    return math.degrees(math.acos(cos_theta))


def trunk_tilt(frame: PoseFrame) -> float | None:
    """Ângulo do eixo da espinha em relação à vertical Y.

    O eixo da espinha vai do ponto médio dos ombros (11/12) ao ponto médio
    dos quadris (23/24). Devolve o ângulo absoluto em graus; ``None`` se
    visibilidade insuficiente.
    """
    if _min_visibility(frame, [_SHOULDER_LEFT, _SHOULDER_RIGHT,
                                  _HIP_LEFT, _HIP_RIGHT]) < _MIN_VISIBILITY:
        return None

    sx = (frame.landmarks[_SHOULDER_LEFT][0] + frame.landmarks[_SHOULDER_RIGHT][0]) / 2
    sy = (frame.landmarks[_SHOULDER_LEFT][1] + frame.landmarks[_SHOULDER_RIGHT][1]) / 2
    hx = (frame.landmarks[_HIP_LEFT][0] + frame.landmarks[_HIP_RIGHT][0]) / 2
    hy = (frame.landmarks[_HIP_LEFT][1] + frame.landmarks[_HIP_RIGHT][1]) / 2

    spine = (hx - sx, hy - sy)
    vertical = (0.0, 1.0)

    dot = spine[0] * vertical[0] + spine[1] * vertical[1]
    mag_spine = (spine[0] ** 2 + spine[1] ** 2) ** 0.5

    if mag_spine == 0:
        return None

    cos_theta = max(-1.0, min(1.0, dot / mag_spine))
    return math.degrees(math.acos(cos_theta))


def joint_angles_per_frame(
    frame: PoseFrame, joints: list[tuple[str, int, int, int]]
) -> dict[str, float | None]:
    """Calcula todos os ângulos configurados para um frame.

    ``joints`` é uma lista de ``(nome, a, b, c)`` — mesma estrutura de
    ``JointTarget``, mas em tupla para esta função não depender do dataclass.
    """
    result: dict[str, float | None] = {}
    for name, a, b, c in joints:
        result[name] = joint_angle(frame, a, b, c)
    return result
