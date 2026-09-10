.PHONY: check public-audit schema-check test demo bench paper paper-check package-check

PYTHON ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)

check: public-audit schema-check bench

public-audit:
	$(PYTHON) tools/audit_public.py

schema-check:
	$(PYTHON) tools/validate_schemas.py

test:
	$(PYTHON) -m pytest

demo:
	$(PYTHON) -m arcana.demo --scenario synthetic_prompt_injection > /dev/null

bench:
	mkdir -p build
	$(PYTHON) -m arcana.bench_runner --output build/arcana-bench-report.json
	$(PYTHON) -m arcana.bench_runner --verify build/arcana-bench-report.json

paper:
	$(PYTHON) tools/build_paper.py --pdf

paper-check:
	$(PYTHON) tools/build_paper.py --check

package-check:
	$(PYTHON) tools/check_package.py
