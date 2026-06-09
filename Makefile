.PHONY: check public-audit schema-check

check: public-audit schema-check

public-audit:
	python3 tools/audit_public.py

schema-check:
	python3 tools/validate_schemas.py
