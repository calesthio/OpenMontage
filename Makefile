.PHONY: setup install install-dev install-gpu test test-contracts lint clean preflight demo demo-list hyperframes-doctor hyperframes-warm

VENV := venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

# ---- One-command setup ----

setup:
	@echo "==> Setting up Python virtual environment (venv)..."
	@test -d $(VENV) || python3 -m venv $(VENV)
	@echo "==> Installing Python dependencies..."
	$(PIP) install -r requirements.txt
	@echo ""
	@echo "==> Installing Remotion composer..."
	cd remotion-composer && npm install
	@echo ""
	@echo "==> Installing free offline TTS (Piper)..."
	$(PIP) install piper-tts || echo "  [skip] piper-tts install failed — TTS will use cloud providers instead"
	@echo ""
	@echo "==> Installing HyperFrames runtime (cache-warm via npx)..."
	@echo "    Pulls the 'hyperframes' npm package into the local npx cache so the"
	@echo "    first render doesn't pay a 30-60s cold-fetch penalty. ~20MB of disk."
	@npx --yes hyperframes --version >/dev/null 2>&1 && echo "    HyperFrames CLI cached (npx)" || echo "  [skip] HyperFrames cache-warm failed — offline or npm unavailable; first render will fetch on demand"
	@$(PYTHON) -c "from tools.video.hyperframes_compose import HyperFramesCompose; HyperFramesCompose._npm_resolve_cache=None; c=HyperFramesCompose()._runtime_check(); print(f'    HyperFrames runtime_available={c[\"runtime_available\"]}, npm={c.get(\"npm_package_version\") or c.get(\"npm_resolve_error\")}'); [print(f'    note: {r}') for r in c['reasons']]" || echo "  [skip] HyperFrames check failed — runtime can be set up later"
	@echo ""
	$(PYTHON) -c "import shutil, os; e=os.path.exists('.env'); shutil.copy('.env.example','.env') if not e else None; print('==> Created .env from .env.example — add your API keys there.' if not e else '==> .env already exists — skipping.')"
	@echo ""
	@echo "Done! Open this project in your AI coding assistant and start creating."
	@echo "  Activate the venv first: source venv/bin/activate"
	@echo "  Optional: add API keys to .env to unlock cloud providers."
	@echo "  Optional: run 'make install-gpu' if you have an NVIDIA GPU."
	@echo "  Optional: run 'make hyperframes-doctor' to fully validate the HyperFrames runtime."
	@echo "  Optional: run 'make hyperframes-warm' anytime to refresh the npx cache to the latest hyperframes version."

# ---- Individual installs ----

install:
	@test -d $(VENV) || python3 -m venv $(VENV)
	$(PIP) install -r requirements.txt

install-dev:
	@test -d $(VENV) || python3 -m venv $(VENV)
	$(PIP) install -r requirements-dev.txt

install-gpu:
	@test -d $(VENV) || python3 -m venv $(VENV)
	$(PIP) install -r requirements-gpu.txt
	$(PIP) install diffusers transformers accelerate

# ---- Testing ----

test:
	$(PYTHON) -m pytest tests/ -v

test-contracts:
	$(PYTHON) -m pytest tests/contracts/ -v

# ---- Utilities ----

preflight:
	$(PYTHON) -c "from tools.tool_registry import registry; import json; registry.discover(); print(json.dumps(registry.provider_menu(), indent=2))"

hyperframes-doctor:
	@echo "==> Probing HyperFrames runtime (node/ffmpeg/npx + hyperframes doctor)..."
	$(PYTHON) -c "from tools.video.hyperframes_compose import HyperFramesCompose; r=HyperFramesCompose().execute({'operation':'doctor'}); import json; print(json.dumps(r.data, indent=2)); print('OK' if r.success else f'FAIL: {r.error}')"

hyperframes-warm:
	@echo "==> Refreshing the HyperFrames npx cache to latest..."
	@echo "    Uses --prefer-online so npx picks up new releases since your last run."
	npx --yes --prefer-online hyperframes --version
	@echo "==> Cache warm complete."

demo:
	@echo "==> Rendering zero-key demo videos (no API keys needed)..."
	@echo "    These use only Remotion components — animated charts, text, data viz."
	@echo ""
	$(PYTHON) render_demo.py

demo-list:
	@$(PYTHON) render_demo.py --list

lint:
	$(PYTHON) -m py_compile tools/base_tool.py
	$(PYTHON) -m py_compile tools/tool_registry.py
	$(PYTHON) -m py_compile tools/cost_tracker.py
	$(PYTHON) -m py_compile tools/composition_validator.py

clean:
	$(PYTHON) -c "import pathlib, shutil; [shutil.rmtree(p) for p in pathlib.Path('.').rglob('__pycache__')]; [p.unlink() for p in pathlib.Path('.').rglob('*.pyc')]"