"""App FastAPI -- expõe o motor de fusão de risco (`pipelines/fusion/`) para a
interface web via HTTP. Sem autenticação: é uma aplicação de demonstração local.

As rotas ficam em `routes.py` (que importa e decora este `app`) -- este módulo só
instancia o app, mantendo a criação da aplicação separada do registro de rotas.
"""

import logging

from fastapi import FastAPI

# Rebaixa as linhas de acesso HTTP do servidor (uma por requisição) para que não
# afoguem o registro de atividade da aplicação no terminal durante a demonstração.
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

app = FastAPI(title="Monitoramento Multimodal -- API de Fusão e Alerta")
