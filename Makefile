PY := .venv/bin/python

# URL do asset `best.pt` no GitHub Release (AD-043) -- a definir quando o primeiro
# Release for publicado (ver training/README.md § Passo 3).
MODEL_RELEASE_URL :=

.PHONY: install data demo test test-unit lint fmt clean localstack-up localstack-down infra-local infra-cloud infra-prescription-local infra-prescription-cloud infra-video-local infra-video-cloud models-fetch

install:
	$(PY) -m pip install -e ".[dev]"

# F0 — aquisição de dados. O script é criado na feature data-acquisition (AD-031).
data:
	./backend/scripts/download_datasets.sh

# Baixa os pesos treinados (AD-043) -- treino real roda em training/ (Colab/GPU),
# não aqui. Sem MODEL_RELEASE_URL configurada (nenhum Release publicado ainda),
# falha com uma mensagem clara em vez de um erro obscuro do curl.
models-fetch:
	@if [ -z "$(MODEL_RELEASE_URL)" ]; then \
	  echo "MODEL_RELEASE_URL não configurada -- publique um Release (ver training/README.md) e defina a variável no Makefile."; \
	  exit 1; \
	fi
	mkdir -p models
	curl -L -o models/best.pt "$(MODEL_RELEASE_URL)"

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

# --- LocalStack (profile local, AD-034) ---
localstack-up:
	docker compose up -d localstack

localstack-down:
	docker compose down

# --- IaC idempotente (mesmos recursos nos dois ambientes, AD-034) ---
# Sourcing do .env.* é opcional: se ausente, usa o que já estiver no ambiente
# (útil em testes que exportam as variáveis diretamente).
infra-local:
	bash -c 'set -a; [ -f .env.local ] && source .env.local; set +a; \
	  PYTHONPATH=backend ENV=local $(PY) -m aws.provision'

infra-cloud:
	bash -c 'set -a; [ -f .env.cloud ] && source .env.cloud; set +a; \
	  PYTHONPATH=backend ENV=cloud $(PY) -m aws.provision'

# --- F4: Lambda de prescrições + gatilho S3 (específico da feature, sobre a IaC acima) ---
infra-prescription-local:
	bash -c 'set -a; [ -f .env.local ] && source .env.local; set +a; \
	  PYTHONPATH=backend ENV=local $(PY) -m aws.provision && \
	  PYTHONPATH=backend ENV=local $(PY) -m pipelines.prescription.infra'

infra-prescription-cloud:
	bash -c 'set -a; [ -f .env.cloud ] && source .env.cloud; set +a; \
	  PYTHONPATH=backend ENV=cloud $(PY) -m aws.provision && \
	  PYTHONPATH=backend ENV=cloud $(PY) -m pipelines.prescription.infra'

# --- F1: Lambda do complemento cloud de vídeo + gatilho S3 (sobre a IaC acima) ---
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
