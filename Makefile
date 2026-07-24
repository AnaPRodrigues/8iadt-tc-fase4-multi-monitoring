PY := .venv/bin/python

# Repositório de modelo público no Hugging Face Hub onde o peso treinado é
# publicado (ver training/README.md). Repo público -- não precisa de token.
MODEL_HF_REPO := AnaPRodrigues/endoscapes-surgical-detector
MODEL_HF_FILE := best.pt

.PHONY: install data demo bidmc-scan test test-unit lint fmt clean models-fetch serve-api serve-front frontend-install

install:
	$(PY) -m pip install -e ".[dev]"

# Baixa os datasets públicos usados pelo sistema.
data:
	./backend/scripts/download_datasets.sh

# Baixa o peso já treinado do detector de objetos (o treino em si roda em
# training/, com GPU) direto do Hugging Face Hub. Antes do primeiro upload, o
# curl abaixo falha com 404 -- ver training/README.md para publicar o peso.
models-fetch:
	mkdir -p models
	curl -fL -o models/best.pt "https://huggingface.co/$(MODEL_HF_REPO)/resolve/main/$(MODEL_HF_FILE)"

demo:
	PYTHONPATH=backend $(PY) -m pipelines.vitals.cli --config backend/pipelines/vitals/configs/demo.yaml

# Varre os registros de internação (BIDMC) e lista quais têm eventos clínicos
# (HR fora de 60-100 bpm; SpO2 sustentada < 90%) -- útil para escolher casos de demo.
bidmc-scan:
	PYTHONPATH=backend $(PY) -m pipelines.vitals.bidmc --dataset-dir data/bidmc

# --- Painel web -- dois processos, um por terminal ---
# 1) suba a API:      make serve-api      (fica em http://localhost:8000)
# 2) suba o painel:   make serve-front    (abre em http://localhost:5173)
# Na primeira vez, instale as dependências do painel: make frontend-install
# O painel só fala HTTP com a API; sem a API de pé, ele mostra erro de conexão.
# API_HOST/API_PORT/FRONT_PORT são sobrescrevíveis: `make serve-api API_PORT=9000`.
API_HOST ?= 127.0.0.1
API_PORT ?= 8000
FRONT_PORT ?= 5173

# Sobe a API (FastAPI/uvicorn). `--reload` recarrega ao salvar código.
# É `app.routes:app` (não `app.main:app`): routes.py registra as rotas sobre o
# app instanciado em main.py -- apontar para main sobe a API sem rota nenhuma.
serve-api:
	PYTHONPATH=backend $(PY) -m uvicorn app.routes:app --app-dir backend \
	  --host $(API_HOST) --port $(API_PORT) --reload

# Instala as dependências do painel web (só na primeira vez).
frontend-install:
	cd frontend && npm install

# Sobe o painel web (React/Vite). O Vite faz proxy das chamadas de API para a API
# local (API_BASE_URL). Ajuste se subir a API noutra porta: `make serve-front API_PORT=9000`.
serve-front:
	cd frontend && API_BASE_URL=http://$(API_HOST):$(API_PORT) FRONT_PORT=$(FRONT_PORT) npm run dev

test:
	$(PY) -m pytest -q

test-unit:
	$(PY) -m pytest -q -m "not integration"

lint:
	$(PY) -m ruff check backend

fmt:
	$(PY) -m ruff format backend

clean:
	rm -rf output/* .pytest_cache
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
