.PHONY: setup install install-dev install-gpu test test-contracts lint clean distclean preflight demo demo-list help

VENV      := .venv
PIP       := $(VENV)/bin/pip
PYTHON    := $(VENV)/bin/python
ACTIVATE  := source $(VENV)/bin/activate

# ---- Default target ----

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

# ---- Virtual environment ----

$(VENV)/bin/activate:
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip

# ---- One-command setup ----

setup: $(VENV)/bin/activate ## Install all dependencies (Python + Node + Piper TTS)
	@echo "==> Installing Python dependencies..."
	$(PIP) install -r requirements.txt
	@echo ""
	@echo "==> Installing Remotion composer..."
	cd remotion-composer && npm install
	@echo ""
	@echo "==> Installing free offline TTS (Piper)..."
	$(PIP) install piper-tts || echo "  [skip] piper-tts install failed — TTS will use cloud providers instead"
	@echo ""
	$(PYTHON) -c "import shutil, os; e=os.path.exists('.env'); shutil.copy('.env.example','.env') if not e else None; print('==> Created .env from .env.example — add your API keys there.' if not e else '==> .env already exists — skipping.')"
	@echo ""
	@echo "Done! Open this project in your AI coding assistant and start creating."
	@echo "  Activate the venv:  $(ACTIVATE)"
	@echo "  Optional: add API keys to .env to unlock cloud providers."
	@echo "  Optional: run 'make install-gpu' if you have an NVIDIA GPU."

# ---- Individual installs ----

install: $(VENV)/bin/activate ## Install core Python dependencies
	$(PIP) install -r requirements.txt

install-dev: $(VENV)/bin/activate ## Install dev/test dependencies
	$(PIP) install -r requirements-dev.txt

install-gpu: $(VENV)/bin/activate ## Install GPU-accelerated dependencies (NVIDIA)
	$(PIP) install -r requirements-gpu.txt
	$(PIP) install diffusers transformers accelerate

# ---- Testing ----

test: $(VENV)/bin/activate ## Run all tests
	$(PYTHON) -m pytest tests/ -v

test-contracts: $(VENV)/bin/activate ## Run contract tests only
	$(PYTHON) -m pytest tests/contracts/ -v

# ---- Utilities ----

preflight: $(VENV)/bin/activate ## Show available tools and provider status
	$(PYTHON) -c "from tools.tool_registry import registry; import json; registry.discover(); print(json.dumps(registry.provider_menu(), indent=2))"

demo: ## Render zero-key demo videos (no API keys needed)
	@echo "==> Rendering zero-key demo videos (no API keys needed)..."
	@echo "    These use only Remotion components — animated charts, text, data viz."
	@echo ""
	./render-demo.sh

demo-list: ## List available demo compositions
	@./render-demo.sh --list

lint: $(VENV)/bin/activate ## Syntax-check core Python modules
	$(PYTHON) -m py_compile tools/base_tool.py
	$(PYTHON) -m py_compile tools/tool_registry.py
	$(PYTHON) -m py_compile tools/cost_tracker.py
	$(PYTHON) -m py_compile tools/composition_validator.py

clean: ## Remove Python caches
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name '*.pyc' -delete 2>/dev/null || true

distclean: clean ## Remove caches and virtual environment
	rm -rf $(VENV)
