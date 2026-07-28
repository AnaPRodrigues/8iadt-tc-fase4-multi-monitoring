"""App FastAPI -- expõe o motor de fusão de risco (`pipelines/fusion/`) para a
interface web via HTTP. Sem autenticação: é uma aplicação de demonstração local.

As rotas ficam em `routes.py` (que importa e decora este `app`) -- este módulo só
instancia o app, mantendo a criação da aplicação separada do registro de rotas.
"""

import logging

from dotenv import load_dotenv
from fastapi import FastAPI

# Carrega o ficheiro .env da raiz do projeto (ENV, AWS_REGION, …) antes de
# qualquer módulo tentar ler variáveis de ambiente. O find_dotenv sobe da
# diretoria do backend/ até encontrar o .env na raiz do repositório.
load_dotenv()

# Rebaixa as linhas de acesso HTTP do servidor (uma por requisição) para que não
# afoguem o registro de atividade da aplicação no terminal durante a demonstração.
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

app = FastAPI(title="Monitoramento Multimodal -- API de Fusão e Alerta")


@app.on_event("startup")
async def _log_modo():
    """Regista no terminal qual o modo ativo (local ou aws) ao arrancar."""
    from aws.clients import resolve_env

    env = resolve_env()
    if env == "aws":
        import os

        region = os.environ.get("AWS_REGION", "?")
        logging.getLogger("app").info(">>> MODO AWS ativo — região %s <<<", region)
    else:
        logging.getLogger("app").info(">>> MODO LOCAL ativo (sem nuvem) <<<")
