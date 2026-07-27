"""Gera áudios sintéticos de consulta médica em português brasileiro.

Usa o edge-tts (gratuito, sem API key) para sintetizar frases com vocabulário
clínico real — "falta de ar", "tontura", "dor no peito". Os áudios gerados
exercitam o pipeline completo de áudio: transcrição (faster-whisper) → termos
críticos → sentimento → fadiga vocal.

São gerados ≥ 2 áudios com tons diferentes para que o score de fadiga vocal
tenha baseline não degenerado (desvio-padrão > 0).

Uso::

    PYTHONPATH=backend python -m scripts.gerar_consulta_tts
    # ou
    make tts-consulta
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

logger = logging.getLogger("tts-consulta")

# Frases de consulta em pt-BR com vocabulário clínico.
# A primeira é mais calma/descritiva; a segunda é mais preocupada/ofegante,
# para gerar contraste de sentimento e fadiga entre as gravações.
_CONSULTAS: list[dict[str, str]] = [
    {
        "nome": "consulta_calma",
        "voz": "pt-BR-FranciscaNeural",
        "texto": (
            "Bom dia, doutora. Eu queria falar sobre uns sintomas que apareceram "
            "essa semana. Tive um pouco de falta de ar quando subi a escada de casa, "
            "e ontem senti uma tontura ao levantar da cama. Não senti dor no peito, "
            "mas fiquei preocupada. Também notei que ando mais cansada que o normal."
        ),
    },
    {
        "nome": "consulta_preocupada",
        "voz": "pt-BR-AntonioNeural",
        "texto": (
            "Doutor, estou muito mal. Sinto uma dor no peito forte desde ontem, "
            "e a falta de ar está piorando... mal consigo andar até a cozinha. "
            "Também tive tontura, quase desmaiei. Estou realmente assustado "
            "com isso, nunca senti nada assim antes."
        ),
    },
]


async def _gerar_audio(texto: str, voz: str, saida: Path) -> None:
    """Gera um arquivo WAV via edge-tts."""
    import edge_tts

    comunicador = edge_tts.Communicate(texto, voz)
    await comunicador.save(str(saida))


def gerar_consultas(data_dir: Path) -> int:
    """Gera todas as consultas sintéticas. Retorna 0 em sucesso, 1 em falha."""
    dest = data_dir / "consultas-tts"
    dest.mkdir(parents=True, exist_ok=True)

    geradas = 0
    for consulta in _CONSULTAS:
        saida = dest / f"{consulta['nome']}.wav"
        if saida.exists():
            logger.info("%s: já existe — pulando", saida.name)
            geradas += 1
            continue

        logger.info(
            "Gerando %s (voz=%s, %d chars)...",
            consulta["nome"], consulta["voz"], len(consulta["texto"]),
        )
        try:
            asyncio.run(_gerar_audio(consulta["texto"], consulta["voz"], saida))
            tamanho_kb = saida.stat().st_size / 1024
            logger.info("  → %s (%.1f KB)", saida.name, tamanho_kb)
            geradas += 1
        except Exception:
            logger.exception("Falha ao gerar %s", consulta["nome"])
            saida.unlink(missing_ok=True)

    if geradas < 2:
        logger.error(
            "Foram geradas apenas %d consultas — o score de fadiga vocal "
            "precisa de ≥ 2 áudios para baseline não degenerado",
            geradas,
        )
        return 1

    logger.info("OK — %d consultas sintéticas em %s/", geradas, dest)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Gera áudios sintéticos de consulta médica em pt-BR (edge-tts)",
    )
    parser.add_argument(
        "--data-dir", default="data",
        help="Diretório raiz dos dados (default: data/)",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="[tts] %(message)s",
        stream=sys.stderr,
    )

    data_dir = Path(args.data_dir).resolve()

    try:
        import edge_tts  # noqa: F401
    except ImportError:
        logger.error("edge-tts não instalado. Rode: pip install edge-tts")
        return 1

    return gerar_consultas(data_dir)


if __name__ == "__main__":
    sys.exit(main())
