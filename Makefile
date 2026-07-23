PY := .venv/bin/python

# Repositório de modelo público no Hugging Face Hub onde o peso treinado é
# publicado (ver training/README.md). Repo público -- não precisa de token.
MODEL_HF_REPO := AnaPRodrigues/endoscapes-surgical-detector
MODEL_HF_FILE := best.pt

.PHONY: install data demo test test-unit lint fmt clean localstack-up localstack-down infra-local infra-cloud infra-prescription-local infra-prescription-cloud infra-video-local infra-video-cloud models-fetch

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

test:
	$(PY) -m pytest -q

test-unit:
	$(PY) -m pytest -q -m "not integration"

lint:
	$(PY) -m ruff check backend

fmt:
	$(PY) -m ruff format backend

# --- Simulador local da nuvem (LocalStack) -- roda tudo sem precisar de uma conta AWS ---
localstack-up:
	docker compose up -d localstack

localstack-down:
	docker compose down

# --- Provisiona os recursos de nuvem compartilhados (bucket, tópico de alerta, tabela) ---
# Sourcing do .env.* é opcional: se ausente, usa o que já estiver no ambiente
# (útil em testes que exportam as variáveis diretamente).
infra-local:
	bash -c 'set -a; [ -f .env.local ] && source .env.local; set +a; \
	  PYTHONPATH=backend ENV=local $(PY) -m aws.provision'

infra-cloud:
	bash -c 'set -a; [ -f .env.cloud ] && source .env.cloud; set +a; \
	  PYTHONPATH=backend ENV=cloud $(PY) -m aws.provision'

# --- Função de nuvem da análise de prescrições + gatilho de upload (sobre a infra acima) ---
infra-prescription-local:
	bash -c 'set -a; [ -f .env.local ] && source .env.local; set +a; \
	  PYTHONPATH=backend ENV=local $(PY) -m aws.provision && \
	  PYTHONPATH=backend ENV=local $(PY) -m pipelines.prescription.infra'

infra-prescription-cloud:
	bash -c 'set -a; [ -f .env.cloud ] && source .env.cloud; set +a; \
	  PYTHONPATH=backend ENV=cloud $(PY) -m aws.provision && \
	  PYTHONPATH=backend ENV=cloud $(PY) -m pipelines.prescription.infra'

# --- Função de nuvem complementar da análise de vídeo + gatilho de upload (sobre a infra acima) ---
infra-video-local:
	bash -c 'set -a; [ -f .env.local ] && source .env.local; set +a; \
	  PYTHONPATH=backend ENV=local $(PY) -m aws.provision && \
	  PYTHONPATH=backend ENV=local $(PY) -m pipelines.video.infra'

infra-video-cloud:
	bash -c 'set -a; [ -f .env.cloud ] && source .env.cloud; set +a; \
	  PYTHONPATH=backend ENV=cloud $(PY) -m aws.provision && \
	  PYTHONPATH=backend ENV=cloud $(PY) -m pipelines.video.infra'

clean:
	rm -rf output/* .pytest_cache
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
