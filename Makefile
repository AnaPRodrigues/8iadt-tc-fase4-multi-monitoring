PY := .venv/bin/python

# Repositório de modelo público no Hugging Face Hub onde o peso treinado é
# publicado (ver training/README.md). Repo público -- não precisa de token.
MODEL_HF_REPO := AnaPRodrigues/endoscapes-surgical-detector
MODEL_HF_FILE := best.pt

.PHONY: install data demo test test-unit lint fmt clean models-fetch serve-api serve-front

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

# --- Painel (dashboard) -- dois processos, um por terminal ---
# 1) suba a API:      make serve-api      (fica em http://localhost:8000)
# 2) suba o painel:   make serve-front    (abre em http://localhost:8501)
# O painel só fala HTTP com a API; sem a API de pé, ele mostra erro de conexão.
# API_HOST/API_PORT/FRONT_PORT são sobrescrevíveis: `make serve-api API_PORT=9000`.
API_HOST ?= 127.0.0.1
API_PORT ?= 8000
FRONT_PORT ?= 8501

# Sobe a API de fusão (FastAPI/uvicorn). `--reload` recarrega ao salvar código.
# É `app.routes:app` (não `app.main:app`): routes.py registra as 4 rotas sobre o
# app instanciado em main.py -- apontar para main sobe a API sem rota nenhuma.
serve-api:
	PYTHONPATH=backend $(PY) -m uvicorn app.routes:app --app-dir backend \
	  --host $(API_HOST) --port $(API_PORT) --reload

# Sobe o painel Streamlit. Lê a URL da API de API_BASE_URL (default coincide com
# serve-api); ajuste se subir a API noutra porta: `make serve-front API_PORT=9000`.
serve-front:
	API_BASE_URL=http://$(API_HOST):$(API_PORT) \
	  $(PY) -m streamlit run frontend/app.py --server.port $(FRONT_PORT)

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
