PY := .venv/bin/python

.PHONY: install data demo test test-unit lint fmt clean

install:
	$(PY) -m pip install -e ".[dev]"

# F0 — aquisição de dados. O script é criado na feature data-acquisition (AD-031).
data:
	./backend/scripts/download_datasets.sh

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

clean:
	rm -rf output/* .pytest_cache
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
