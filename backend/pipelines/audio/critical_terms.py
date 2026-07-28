"""Termos críticos configuráveis: busca + evidência.

``normalize_text`` também é reusada por ``sentiment.py``.
"""

import unicodedata
from pathlib import Path

import yaml

from common.evidence import Evidence, evidence_dir, save_evidence
from pipelines.audio.models import CriticalTermHit, Transcript, TranscriptSegment

_FEATURE = "audio"
_CONTEXT_CHARS = 40

# Termos clínicos padrão com cobertura de domínios relevantes para
# monitoramento hospitalar: dor, respiratório, mobilidade, neurológico,
# cardiovasculares e estado geral. A lista pode ser estendida via YAML
# (``critical_terms_path`` na config do pipeline).
_DEFAULT_TERMS = [
    # Dor — substantivo, verbo (infinitivo e gerúndio) e flexões comuns
    "dor",
    "doendo",
    "doer",
    "dói",
    "dolor",
    "dolorido",
    "dolorida",
    # Respiratório
    "falta de ar",
    "dificuldade para respirar",
    "chiado",
    "cansaço",
    "cansaço excessivo",
    "fôlego curto",
    # Mobilidade / fisioterapia
    "não consigo dobrar",
    "não consigo mexer",
    "travado",
    "travada",
    "inchado",
    "inchada",
    "inflamado",
    "inflamada",
    "rigidez",
    "rígido",
    # Neurológico
    "tontura",
    "tonto",
    "tonta",
    "desmaio",
    "desmaiar",
    "formigamento",
    "dormência",
    "convulsão",
    # Cardiovasculares
    "dor no peito",
    "palpitação",
    "coração acelerado",
    "pressão alta",
    "pressão baixa",
    # Estado geral
    "febre",
    "febril",
    "náusea",
    "vômito",
    "vomitar",
    "suor frio",
    "mal-estar",
    "fraqueza",
]


def normalize_text(s: str) -> str:
    """Minúsculas + remoção de acento (via ``unicodedata``), para casar termos robustamente."""
    decomposed = unicodedata.normalize("NFKD", s.lower())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def load_terms(path: Path | None) -> list[str]:
    """Lê a lista de termos do YAML; ausente/vazio usa a lista padrão embutida."""
    if not path:
        return list(_DEFAULT_TERMS)

    path = Path(path)
    if not path.is_file():
        return list(_DEFAULT_TERMS)

    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not raw:
        return list(_DEFAULT_TERMS)
    return list(raw)


def _segment_spans(segments: list[TranscriptSegment]) -> list[tuple[int, int, TranscriptSegment]]:
    """Faixa de offsets `[start, end)` de cada segmento dentro do texto concatenado."""
    spans = []
    offset = 0
    for seg in segments:
        length = len(seg.text)
        spans.append((offset, offset + length, seg))
        offset += length
    return spans


def _timestamp_for(spans: list[tuple[int, int, TranscriptSegment]], idx: int) -> float | None:
    for start, end, seg in spans:
        if start <= idx < end:
            return seg.start_s
    return None


def find_terms(transcript: Transcript, terms: list[str]) -> list[CriticalTermHit]:
    """Busca cada termo (normalizado) no transcript, com contexto e timestamp aproximado."""
    normalized_text = normalize_text(transcript.text)
    spans = _segment_spans(transcript.segments)

    hits: list[CriticalTermHit] = []
    for term in terms:
        norm_term = normalize_text(term)
        if not norm_term:
            continue

        start = 0
        while True:
            idx = normalized_text.find(norm_term, start)
            if idx == -1:
                break
            end = idx + len(norm_term)
            ctx_start = max(idx - _CONTEXT_CHARS, 0)
            ctx_end = min(end + _CONTEXT_CHARS, len(transcript.text))
            hits.append(
                CriticalTermHit(
                    term=term,
                    context=transcript.text[ctx_start:ctx_end],
                    approx_timestamp_s=_timestamp_for(spans, idx),
                )
            )
            start = end

    return hits


def _highlight(text: str, term: str) -> str:
    """Envolve a primeira ocorrência (case/acento-insensível) de ``term`` em ``text`` com `**`."""
    normalized_text = normalize_text(text)
    norm_term = normalize_text(term)
    idx = normalized_text.find(norm_term)
    if idx == -1:
        return text
    end = idx + len(norm_term)
    return f"{text[:idx]}**{text[idx:end]}**{text[end:]}"


def save_term_evidence(
    hit: CriticalTermHit,
    transcript: Transcript,
    run_id: str,
    output_root: str | Path = "output",
) -> Evidence:
    """Grava o transcript (termo destacado com `**`) como artefato `.txt` + sidecar de metadados."""
    stem = Path(transcript.audio_path).stem
    ts = hit.approx_timestamp_s if hit.approx_timestamp_s is not None else 0.0
    term_slug = normalize_text(hit.term).replace(" ", "-")
    evidence_id = f"{stem}-term-{term_slug}-{ts:.0f}s"

    dest_dir = evidence_dir(_FEATURE, run_id, output_root)
    dest_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = dest_dir / f"{evidence_id}.txt"
    artifact_path.write_text(_highlight(transcript.text, hit.term), encoding="utf-8")

    return save_evidence(
        feature=_FEATURE,
        run_id=run_id,
        evidence_id=evidence_id,
        source_record_id=stem,
        artifact_path=artifact_path,
        metadata={
            "term": hit.term,
            "context": hit.context,
            "approx_timestamp_s": hit.approx_timestamp_s,
        },
        root=output_root,
    )
