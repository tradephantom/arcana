.PHONY: check public-audit schema-check test demo

PYTHON ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)

check: public-audit schema-check

public-audit:
	$(PYTHON) tools/audit_public.py

schema-check:
	$(PYTHON) tools/validate_schemas.py

test:
	$(PYTHON) -m pytest

demo:
	$(PYTHON) -m arcana.demo --scenario synthetic_prompt_injection > /dev/null
