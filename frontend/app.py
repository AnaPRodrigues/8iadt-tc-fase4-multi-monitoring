"""Dashboard Streamlit de F5 (fusion-and-alerting) -- timeline unificada, replay
controlado e drill-down de evidência do paciente-demo (FUSION-10, FUSION-11, FUSION-12).

Consome só a API fina do backend (`backend/app/`) via HTTP (`requests`) -- nenhum
import direto de `backend/pipelines/fusion/` ou `backend/common/` (AD-044,
design.md § `frontend/`). Roda com `streamlit run frontend/app.py` contra a API
já de pé (`uvicorn app.routes:app`, ver `frontend/README.md`).
"""

import os
import time

import pandas as pd
import requests
import streamlit as st

API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")
DEFAULT_PATIENT_DEMO_ID = "demo"

_NIVEL_RENDERER = {"verde": st.success, "amarelo": st.warning, "vermelho": st.error}

st.set_page_config(
    page_title="Monitoramento Multimodal -- Fusão e Alerta", page_icon="🩺", layout="wide"
)


def _fetch_timeline(patient_demo_id: str) -> list[dict] | None:
    """Busca `GET /patients/{id}/timeline` uma única vez (guardado em
    `st.session_state` pelo chamador) -- nunca re-chamado a cada passo do replay.

    `None` sinaliza paciente-demo não configurado (404 da API), distinto de uma
    timeline vazia (`[]`: paciente configurado, mas nenhum evento resolvido).
    """
    try:
        response = requests.get(
            f"{API_BASE_URL}/patients/{patient_demo_id}/timeline", timeout=10
        )
    except requests.exceptions.RequestException as exc:
        st.error(f"Não foi possível conectar à API em {API_BASE_URL}: {exc}")
        return []
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return response.json()


def _unique_events(timeline: list[dict]) -> list[dict]:
    """Eventos reais distintos (por `evidence_id`) que compõem a timeline, ordenados
    por instante. Um mesmo evento aparece em `contributing_events` de vários pontos
    (o decaimento reduz o peso, não a presença), então dedupe é necessário para
    listar cada evento real uma única vez."""
    by_id: dict[str, dict] = {}
    for point in timeline:
        for event in point["contributing_events"]:
            by_id[event["evidence_id"]] = event
    return sorted(by_id.values(), key=lambda e: e["demo_timestamp_s"])


def _render_nivel(level: str, score: float) -> None:
    renderer = _NIVEL_RENDERER.get(level, st.info)
    renderer(f"Nível: **{(level or 'desconhecido').upper()}** (score={score:.3f})")


def _render_score_chart(timeline: list[dict]) -> None:
    df = pd.DataFrame(
        {"t (s)": [p["t"] for p in timeline], "score": [p["score"] for p in timeline]}
    )
    st.line_chart(df.set_index("t (s)"))


def _fetch_evidence(evidence_id: str) -> requests.Response | None:
    """Busca `GET /evidence/{id}` para o drill-down do evento selecionado (FUSION-12).

    `None` sinaliza falha de rede ou `evidence_id` inexistente (404) -- o chamador já
    mostra a mensagem de erro correspondente, não há tela em branco nesse caso.
    """
    try:
        response = requests.get(f"{API_BASE_URL}/evidence/{evidence_id}", timeout=10)
    except requests.exceptions.RequestException as exc:
        st.error(f"Não foi possível buscar a evidência '{evidence_id}': {exc}")
        return None
    if response.status_code == 404:
        st.error(f"Evidência inexistente: {evidence_id}")
        return None
    response.raise_for_status()
    return response


def _render_evidence(response: requests.Response, evidence_id: str) -> None:
    """Renderiza o artefato conforme o `content-type` devolvido pela API -- imagem
    (frame anotado/gráfico da janela anômala) ou texto (transcript/prescrição
    anotada), com os metadados do sidecar (headers `X-Evidence-*`) como legenda."""
    content_type = response.headers.get("content-type", "")
    st.caption(
        f"feature={response.headers.get('x-evidence-feature', '?')} · "
        f"run_id={response.headers.get('x-evidence-run-id', '?')} · "
        f"source_record_id={response.headers.get('x-evidence-source-record-id', '?')}"
    )
    if content_type.startswith("image/"):
        st.image(response.content)
    elif content_type.startswith("text/"):
        st.text(response.text)
    else:
        st.write(f"Artefato do tipo `{content_type or 'desconhecido'}` ({len(response.content)} bytes).")
        st.download_button(
            "Baixar artefato", data=response.content, file_name=evidence_id, key=f"dl-{evidence_id}"
        )


def _render_drilldown(timeline: list[dict]) -> None:
    """Seleção de evento -> evidência correspondente renderizada pelo tipo (FUSION-12)."""
    eventos = _unique_events(timeline)
    opcoes = {
        f"t={e['demo_timestamp_s']:.0f}s · {e['modality']} · {e['summary'][:60]}": e["evidence_id"]
        for e in eventos
    }
    escolha = st.selectbox("Evento", list(opcoes))
    if escolha is None:
        return
    evidence_id = opcoes[escolha]
    response = _fetch_evidence(evidence_id)
    if response is not None:
        _render_evidence(response, evidence_id)


def _render_events_table(events: list[dict]) -> None:
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "t (s)": e["demo_timestamp_s"],
                    "modalidade": e["modality"],
                    "resumo": e["summary"],
                    "evidence_id": e["evidence_id"],
                }
                for e in events
            ]
        ),
        hide_index=True,
        width="stretch",
    )


def _replay_controls(n_points: int) -> int:
    """Slider + navegação passo a passo + reprodução automática (velocidade
    configurável) sobre os pontos JÁ carregados em `st.session_state` -- nunca
    dispara nova chamada HTTP por passo, nunca espera a duração real do cenário
    (FUSION-11)."""
    st.session_state.setdefault("replay_idx", 0)
    st.session_state["replay_idx"] = min(st.session_state["replay_idx"], n_points - 1)

    col_prev, col_slider, col_next = st.columns([1, 6, 1])
    with col_prev:
        if st.button("◀", help="Passo anterior") and st.session_state["replay_idx"] > 0:
            st.session_state["replay_idx"] -= 1
    with col_next:
        if (
            st.button("▶", help="Próximo passo")
            and st.session_state["replay_idx"] < n_points - 1
        ):
            st.session_state["replay_idx"] += 1
    with col_slider:
        st.session_state["replay_idx"] = st.slider(
            "Posição no replay", 0, n_points - 1, st.session_state["replay_idx"]
        )

    auto = st.checkbox("Reprodução automática")
    speed_s = st.slider(
        "Intervalo entre passos (s)", 0.1, 2.0, 0.5, step=0.1, disabled=not auto
    )
    if auto and st.session_state["replay_idx"] < n_points - 1:
        time.sleep(speed_s)
        st.session_state["replay_idx"] += 1
        st.rerun()

    return st.session_state["replay_idx"]


def main() -> None:
    st.title("Monitoramento Multimodal -- Fusão e Alerta")

    patient_demo_id = st.sidebar.text_input("Paciente-demo", value=DEFAULT_PATIENT_DEMO_ID)
    if st.sidebar.button("Carregar") or "timeline" not in st.session_state:
        st.session_state["timeline"] = _fetch_timeline(patient_demo_id)
        st.session_state["replay_idx"] = 0

    timeline = st.session_state.get("timeline")

    if timeline is None:
        st.info(
            f"**Nenhum paciente-demo configurado para '{patient_demo_id}'.**\n\n"
            f"Crie `backend/pipelines/fusion/configs/{patient_demo_id}.yaml` "
            "(ver `pipelines/fusion/config.py` para o formato) e clique em "
            "'Carregar' na barra lateral."
        )
        return

    if not timeline:
        st.info("Paciente-demo configurado, mas nenhum evento foi resolvido para a timeline.")
        return

    st.subheader("Risk score ao longo do tempo")
    _render_score_chart(timeline)

    st.subheader("Replay")
    idx = _replay_controls(len(timeline))
    ponto = timeline[idx]
    _render_nivel(ponto["level"], ponto["score"])
    if ponto["missing_modalities"]:
        st.caption(
            f"Modalidades sem dado até t={ponto['t']:.0f}s: "
            f"{', '.join(ponto['missing_modalities'])}"
        )

    st.subheader("Eventos das 4 modalidades")
    _render_events_table(_unique_events(timeline))

    st.subheader("Drill-down de evidência")
    _render_drilldown(timeline)


if __name__ == "__main__":
    main()
