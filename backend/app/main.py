"""App FastAPI mínimo da API fina de F5 (AD-044) -- expõe o motor de fusão
(`pipelines/fusion/`) para o dashboard Streamlit via HTTP. Sem middleware de
autenticação: fora de escopo (demo local, ver `spec.md` § Out of Scope).

As rotas em si ficam em `routes.py` (que importa e decora este `app`) -- este
módulo só instancia o app, para manter a criação da aplicação separada do
registro de rotas.
"""

from fastapi import FastAPI

app = FastAPI(title="Monitoramento Multimodal -- API de Fusão e Alerta")
