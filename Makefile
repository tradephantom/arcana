.PHONY: check public-audit

check: public-audit

public-audit:
	python3 tools/audit_public.py
