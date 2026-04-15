.PHONY: setup install install-dev install-gpu test test-contracts lint clean preflight demo demo-list

# ---- One-command setup ----

setup:
	@echo "==> Installing Python dependencies..."
	pip install -r requirements.txt
	@echo ""
	@echo "==> Installing Remotion composer..."
	cd remotion-composer && npm install
	@echo ""
	@echo "==> Installing free offline TTS (Piper)..."
	pip install piper-tts || echo "  [skip] piper-tts install failed — TTS will use cloud providers instead"
	@echo ""
	python -c "import shutil, os; e=os.path.exists('.env'); shutil.copy('.env.example','.env') if not e else None; print('==> Created .env from .env.example — add your API keys there.' if not e else '==> .env already exists — skipping.')"
	@echo ""
	@echo "Done! Open this project in your AI coding assistant and start creating."
	@echo "  Optional: add API keys to .env to unlock cloud providers."
	@echo "  Optional: run 'make install-gpu' if you have an NVIDIA GPU."

# ---- Individual installs ----

install:
	pip install -r requirements.txt

install-dev:
	pip install -r requirements-dev.txt

install-gpu:
	pip install -r requirements-gpu.txt
	pip install diffusers transformers accelerate

# ---- Testing ----

test:
	python -m pytest tests/ -v

test-contracts:
	python -m pytest tests/contracts/ -v

# ---- Utilities ----

preflight:
	python -c "from tools.tool_registry import registry; import json; registry.discover(); print(json.dumps(registry.provider_menu(), indent=2))"

demo:
	@echo "==> Rendering zero-key demo videos (no API keys needed)..."
	@echo "    These use only Remotion components — animated charts, text, data viz."
	@echo ""
	python render_demo.py

demo-list:
	@python render_demo.py --list

lint:
	python -m py_compile tools/base_tool.py
	python -m py_compile tools/tool_registry.py
	python -m py_compile tools/cost_tracker.py
	python -m py_compile tools/composition_validator.py

clean:
	python -c "import pathlib, shutil; [shutil.rmtree(p) for p in pathlib.Path('.').rglob('__pycache__')]; [p.unlink() for p in pathlib.Path('.').rglob('*.pyc')]"
