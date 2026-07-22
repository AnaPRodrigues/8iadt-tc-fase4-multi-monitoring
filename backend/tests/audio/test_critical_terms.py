"""Testes de termos críticos configuráveis (AUDIO-07, AUDIO-09)."""

import json
from pathlib import Path

import yaml

from pipelines.audio.critical_terms import find_terms, load_terms, save_term_evidence
from pipelines.audio.models import CriticalTermHit, Transcript, TranscriptSegment


def _transcript(segments_text: list[tuple[float, float, str]]) -> Transcript:
    segments = [
        TranscriptSegment(start_s=s, end_s=e, text=t, no_speech_prob=0.1)
        for s, e, t in segments_text
    ]
    return Transcript(
        audio_path=Path("101_1b1_Al_sc_Meditron.wav"),
        text="".join(t for _, _, t in segments_text),
        segments=segments,
        reliable=True,
    )


def test_termo_multipalavra_encontrado_com_acentuacao_e_caixa_diferentes():
    transcript = _transcript(
        [(0.0, 2.0, " Doutor, NAO CONSIGO RESPIRAR direito hoje.")]
    )

    hits = find_terms(transcript, ["não consigo respirar"])

    assert len(hits) == 1
    assert hits[0].term == "não consigo respirar"


def test_find_terms_sem_nenhum_termo_no_transcript_retorna_lista_vazia():
    transcript = _transcript([(0.0, 2.0, " Bom dia, tudo bem por aqui.")])

    hits = find_terms(transcript, ["dor no peito", "falta de ar", "tontura"])

    assert hits == []


def test_load_terms_none_retorna_lista_padrao_documentada():
    terms = load_terms(None)

    assert terms == ["dor no peito", "falta de ar", "tontura"]


def test_load_terms_arquivo_vazio_retorna_lista_padrao(tmp_path):
    vazio = tmp_path / "vazio.yaml"
    vazio.write_text("", encoding="utf-8")

    assert load_terms(vazio) == ["dor no peito", "falta de ar", "tontura"]


def test_load_terms_arquivo_valido_usa_os_termos_do_yaml(tmp_path):
    custom = tmp_path / "termos.yaml"
    custom.write_text(yaml.safe_dump(["febre alta", "convulsão"]), encoding="utf-8")

    assert load_terms(custom) == ["febre alta", "convulsão"]


def test_timestamp_aproximado_corresponde_ao_segmento_correto_com_multiplos_segmentos():
    transcript = _transcript(
        [
            (0.0, 2.0, " Bom dia, doutor."),
            (2.0, 5.0, " Sinto muita dor no peito agora."),
            (5.0, 7.0, " Isso é preocupante."),
        ]
    )

    hits = find_terms(transcript, ["dor no peito"])

    assert len(hits) == 1
    assert hits[0].approx_timestamp_s == 2.0  # início do 2º segmento, não do 1º ou 3º


def test_evidencia_tem_termo_destacado_no_artefato_e_metadados_no_sidecar(tmp_path):
    transcript = _transcript(
        [(0.0, 2.0, " Sinto muita dor no peito agora.")]
    )
    hit = CriticalTermHit(
        term="dor no peito", context="Sinto muita dor no peito agora", approx_timestamp_s=0.0
    )

    evidencia = save_term_evidence(hit, transcript, run_id="r1", output_root=tmp_path / "output")

    conteudo = evidencia.artifact_path.read_text(encoding="utf-8")
    assert "**dor no peito**" in conteudo

    sidecar = json.loads(evidencia.sidecar_path.read_text(encoding="utf-8"))
    assert sidecar["metadata"]["term"] == "dor no peito"
    assert sidecar["metadata"]["context"] == "Sinto muita dor no peito agora"
    assert sidecar["metadata"]["approx_timestamp_s"] == 0.0
