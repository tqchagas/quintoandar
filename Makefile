PYTHON ?= python3
CITY ?= Belo Horizonte
CITY_SLUG ?= belo-horizonte
LIMIT ?= 0
OUTPUT ?= condominios-$(CITY_SLUG).jsonl
LIMIT_VALUE = $(if $(strip $(LIMIT)),$(strip $(LIMIT)),0)

.PHONY: help condominiums test

help:
	@printf '%s\n' \
	  'make condominiums [LIMIT=1] [OUTPUT=condominios.jsonl]' \
	  '  Coleta condomínios da cidade configurada e grava JSONL.' \
	  '  LIMIT=0 (padrão) coleta todos; use LIMIT=1 para experimentar.' \
	  '  CITY="São Paulo" CITY_SLUG=sao-paulo muda a cidade.' \
	  'make test  roda os testes automatizados.'

condominiums:
	PYTHONPATH=src $(PYTHON) scripts/collect_condominiums.py \
	  --city "$(CITY)" --city-slug "$(CITY_SLUG)" \
	  --limit "$(LIMIT_VALUE)" --output "$(OUTPUT)"

test:
	PYTHONPATH=src $(PYTHON) -m unittest discover -s tests -v
