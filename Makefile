.PHONY: install run run-sedes run-category clean clean-output clean-all help

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install all dependencies with uv
	uv sync

run: ## Run full scraping of all sections
	uv run python main.py

run-sedes: ## Quick test: scrape only sedes (5 URLs)
	uv run python main.py --category sedes

run-category: ## Scrape a specific category (usage: make run-category CAT=servicios)
	uv run python main.py --category $(CAT)

resume: ## Resume interrupted scraping (skips existing files)
	uv run python main.py

clean-output: ## Delete all scraped output files
	@if exist output rmdir /s /q output
	@echo Output cleaned.

clean: ## Delete venv and cached files
	@if exist .venv rmdir /s /q .venv
	@if exist __pycache__ rmdir /s /q __pycache__
	@for /d %%d in (scraper\__pycache__) do @if exist "%%d" rmdir /s /q "%%d"
	@echo Cache cleaned.

clean-all: clean clean-output ## Delete everything (venv + output + cache)
	@echo All cleaned.
