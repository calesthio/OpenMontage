# OpenMontage Custom GPT Gateway

This folder exposes OpenMontage through a small authenticated FastAPI service so a Custom GPT can act as the video-production agent while OpenMontage remains the execution engine.

## Architecture

`Custom GPT -> GPT Actions -> gpt_gateway -> OpenMontage pipelines/tools/checkpoints -> final MP4`

The gateway intentionally does not replace OpenMontage's agent-first architecture. The GPT reads the native agent contract, selects a pipeline, reads each stage-director skill, checks the live tool/provider registry, runs tools, and writes native checkpoints.

## Run locally

From the OpenMontage repository root:

```bash
python -m pip install -r gpt_gateway/requirements.txt
export GPT_GATEWAY_API_KEY='replace-with-a-long-random-secret'
uvicorn gpt_gateway.main:app --host 0.0.0.0 --port 8000
```

Windows PowerShell:

```powershell
python -m pip install -r gpt_gateway/requirements.txt
$env:GPT_GATEWAY_API_KEY='replace-with-a-long-random-secret'
uvicorn gpt_gateway.main:app --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000/health` to confirm the gateway is running.

## Custom GPT setup

1. Deploy the OpenMontage host behind HTTPS.
2. Replace the placeholder server URL in `openapi.yaml` with the deployed HTTPS URL.
3. Add `openapi.yaml` as the GPT Action schema.
4. Configure API-key authentication using the `X-API-Key` header.
5. Put the contents of `GPT_INSTRUCTIONS.md` into the GPT instructions.

## Production flow

A normal video request should follow this order:

1. Read the OpenMontage core instructions.
2. Discover pipelines and choose one.
3. Read the selected pipeline manifest.
4. Inspect live capabilities/providers.
5. Create a project.
6. Read the exact stage-director instructions before each stage.
7. Dry-run paid or consequential tools before execution.
8. Ask for user approval when required by OpenMontage.
9. Execute the tool and write the native checkpoint.
10. Continue until `renders/final.mp4` exists.

## Security

Do not deploy the service without `GPT_GATEWAY_API_KEY`. Use HTTPS. For a multi-user deployment, add per-user authentication, quotas, job isolation, object storage, and a queue before allowing public access.

## Next milestone

The next layer is an asynchronous production-job API with media uploads, progress reporting, persistent object storage and signed result URLs so long OpenMontage renders can run safely without keeping one GPT Action request open.
