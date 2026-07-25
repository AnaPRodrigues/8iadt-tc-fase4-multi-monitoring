"""Gerador de prescrições sintéticas com ground truth conhecido.

Os PDFs contêm texto real embutido via ``reportlab`` (não uma imagem escaneada),
o que permite extração direta por ``pdfplumber`` sem OCR — verificado em REPL
durante o design (round-trip preserva a ordem das linhas).

O retorno inclui também os bytes do PDF —
``list[tuple[bytes, GroundTruthEntry]]`` — porque sem o PDF em mãos os testes
de integração não teriam como associar o rótulo esperado ao artefato
real; `generate_dataset` não tem responsabilidade de subir para o S3 (isso é do
chamador/teste).

``generate_dataset`` produz apenas o rótulo ``"dose_fora_de_faixa"``.
"Mudança abrupta" depende de uma sequência de dois registros do mesmo
paciente/medicamento — é exercida diretamente pelos testes de integração,
chamando ``generate_prescription`` duas vezes, não por um rótulo isolado
aqui.
"""

import dataclasses
import io
import json
import random
from datetime import datetime, timedelta
from pathlib import Path

from reportlab.pdfgen import canvas

from pipelines.prescription import catalog
from pipelines.prescription.models import GroundTruthEntry

_BASE_TIMESTAMP = datetime(2026, 1, 1)
_DEFAULT_UNIT = "mg"


def _timestamp_from_seed(seed: int) -> str:
    """Timestamp ISO-8601 determinístico a partir do seed (segundos após a base)."""
    return (_BASE_TIMESTAMP + timedelta(seconds=seed)).isoformat()


def generate_prescription(
    patient_id: str,
    drug: str,
    dose: float,
    frequency: str = "8/8h",
    seed: int | None = None,
) -> bytes:
    """Gera um PDF de prescrição com texto real embutido.

    ``seed`` determina o timestamp; se omitido, usa a data/hora atual.
    ``frequency`` tem default ``"8/8h"`` para uso avulso sem especificar.
    """
    drug_range = catalog.lookup(drug)
    unit = drug_range.unit if drug_range is not None else _DEFAULT_UNIT
    effective_seed = seed if seed is not None else random.randint(0, 2**31 - 1)
    timestamp = _timestamp_from_seed(effective_seed)

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer)
    lines = [
        f"Paciente: {patient_id}",
        f"Medicamento: {drug}",
        f"Dose: {dose} {unit}",
        f"Frequência: {frequency}",
        f"Data: {timestamp}",
    ]
    y = 800
    for line in lines:
        pdf.drawString(72, y, line)
        y -= 20
    pdf.save()
    return buffer.getvalue()


def generate_dataset(
    n: int, seed: int, anomaly_rate: float = 0.3
) -> list[tuple[bytes, GroundTruthEntry]]:
    """Gera ``n`` prescrições sintéticas com proporção conhecida de anomalias."""
    rng = random.Random(seed)
    drugs = catalog.all_drugs()
    dataset: list[tuple[bytes, GroundTruthEntry]] = []

    for i in range(n):
        drug = rng.choice(drugs)
        drug_range = catalog.lookup(drug)
        assert drug_range is not None  # vem do catálogo, sempre resolve

        is_anomalous = rng.random() < anomaly_rate
        if is_anomalous:
            dose = (
                drug_range.min_dose * rng.uniform(0.1, 0.5)
                if rng.random() < 0.5
                else drug_range.max_dose * rng.uniform(1.5, 3.0)
            )
            anomaly_type = "dose_fora_de_faixa"
        else:
            dose = rng.uniform(drug_range.min_dose, drug_range.max_dose)
            anomaly_type = None

        patient_id = f"patient-{seed}-{i:04d}"
        pdf_bytes = generate_prescription(
            patient_id=patient_id,
            drug=drug,
            dose=round(dose, 2),
            frequency="8/8h",
            seed=seed + i,
        )
        dataset.append(
            (
                pdf_bytes,
                GroundTruthEntry(
                    patient_id=patient_id,
                    drug=drug,
                    dose=round(dose, 2),
                    is_anomalous=is_anomalous,
                    anomaly_type=anomaly_type,
                    timestamp=_timestamp_from_seed(seed + i),
                ),
            )
        )

    return dataset


def generate_sequence_dataset(
    n_sequences: int, seed: int, abrupt_rate: float = 0.3
) -> list[tuple[bytes, GroundTruthEntry]]:
    """Gera pares (baseline, seguinte) do mesmo paciente/medicamento, para avaliar
    a regra de mudança abrupta — `generate_dataset` sozinho não produz
    sequências, só casos independentes de dose fora de faixa.

    Todo medicamento do catálogo tem `max_dose >= 2×min_dose`; usar os extremos da
    faixa como baseline/seguinte garante uma variação > 50% sem sair da faixa
    terapêutica (nunca contamina o rótulo com "dose_fora_de_faixa" também).
    """
    rng = random.Random(seed)
    drugs = catalog.all_drugs()
    dataset: list[tuple[bytes, GroundTruthEntry]] = []

    for i in range(n_sequences):
        drug = rng.choice(drugs)
        drug_range = catalog.lookup(drug)
        assert drug_range is not None  # vem do catálogo, sempre resolve
        patient_id = f"seq-{seed}-{i:04d}"

        baseline_seed = seed + 2 * i
        baseline_dose = round(drug_range.min_dose, 2)
        baseline_pdf = generate_prescription(
            patient_id=patient_id,
            drug=drug,
            dose=baseline_dose,
            frequency="8/8h",
            seed=baseline_seed,
        )
        dataset.append(
            (
                baseline_pdf,
                GroundTruthEntry(
                    patient_id=patient_id,
                    drug=drug,
                    dose=baseline_dose,
                    is_anomalous=False,
                    anomaly_type=None,
                    timestamp=_timestamp_from_seed(baseline_seed),
                ),
            )
        )

        is_abrupt = rng.random() < abrupt_rate
        followup_seed = seed + 2 * i + 1
        if is_abrupt:
            followup_dose = round(drug_range.max_dose, 2)
            anomaly_type = "mudanca_abrupta"
        else:
            followup_dose = round(baseline_dose * rng.uniform(0.95, 1.2), 2)
            anomaly_type = None

        followup_pdf = generate_prescription(
            patient_id=patient_id,
            drug=drug,
            dose=followup_dose,
            frequency="8/8h",
            seed=followup_seed,
        )
        dataset.append(
            (
                followup_pdf,
                GroundTruthEntry(
                    patient_id=patient_id,
                    drug=drug,
                    dose=followup_dose,
                    is_anomalous=is_abrupt,
                    anomaly_type=anomaly_type,
                    timestamp=_timestamp_from_seed(followup_seed),
                ),
            )
        )

    return dataset


def generate_dataset_to_disk(
    n: int, seed: int, anomaly_rate: float, output_dir: Path
) -> list[GroundTruthEntry]:
    """Gera o dataset e persiste os PDFs + o ground truth em arquivo separado."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    dataset = generate_dataset(n, seed, anomaly_rate)
    entries = []
    for pdf_bytes, entry in dataset:
        (output_dir / f"{entry.patient_id}.pdf").write_bytes(pdf_bytes)
        entries.append(entry)

    ground_truth_path = output_dir / "ground_truth.json"
    ground_truth_path.write_text(
        json.dumps([dataclasses.asdict(e) for e in entries], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return entries


# --------------------------------------------------------------------------- #
# Uso standalone: gera uma prescrição avulsa e grava o PDF em disco
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description="Gera uma prescrição avulsa em PDF e grava em disco."
    )
    parser.add_argument("--patient-id", required=True, help="ID do paciente")
    parser.add_argument("--drug", required=True, help="Nome do medicamento (ex.: paracetamol)")
    parser.add_argument("--dose", required=True, type=float, help="Dose numérica (ex.: 500)")
    parser.add_argument("--frequency", default="8/8h", help="Frequência (default: 8/8h)")
    parser.add_argument("--seed", type=int, default=None, help="Seed para timestamp determinístico")
    parser.add_argument("--output", default=None, help="Caminho do PDF de saída (default: <drug>_<dose>.pdf)")
    args = parser.parse_args()

    pdf_bytes = generate_prescription(
        patient_id=args.patient_id,
        drug=args.drug,
        dose=args.dose,
        frequency=args.frequency,
        seed=args.seed,
    )

    output = args.output or f"{args.drug}_{args.dose:.0f}.pdf"
    Path(output).write_bytes(pdf_bytes)
    print(f"Prescrição gerada: {output} ({len(pdf_bytes)} bytes)")
    sys.exit(0)
