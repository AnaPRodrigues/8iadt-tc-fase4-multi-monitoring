PY := .venv/bin/python

.PHONY: install test test-unit lint fmt demo clean

install:
	$(PY) -m pip install -e ".[dev]"

test:
	$(PY) -m pytest -q

test-unit:
	$(PY) -m pytest -q -m "not integration"

lint:
	$(PY) -m ruff check src tests

fmt:
	$(PY) -m ruff format src tests

demo:
	PYTHONPATH=src $(PY) -m vitals.cli --config configs/demo.yaml

clean:
	rm -rf output/* .pytest_cache
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
