"""MAI Voice 2.1 and Flash over the Azure Speech SSML transport."""

from copy import deepcopy
from jsonschema import validate
from tools.audio.azure_tts import AzureTTS
from tools.provider_pricing import PriceQuoteRequired
from tools.base_tool import ToolResult, Determinism


class MAITTS(AzureTTS):
    determinism = Determinism.STOCHASTIC
    name = "mai_tts"
    provider = "microsoft_mai"
    agent_skills = ["provider-refresh-oct23", "azure-text-to-speech"]
    input_schema = deepcopy(AzureTTS.input_schema)
    input_schema["properties"].update(
        {
            "model_id": {"enum": ["MAI-Voice-2.1", "MAI-Voice-2.1-Flash"]},
            "voice_id": {"type": "string"},
        }
    )
    DEFAULT_VOICE = "en-US-Harper"
    idempotency_key_fields = AzureTTS.idempotency_key_fields + ["model_id", "voice_id"]

    def estimate_cost(self, inputs):
        raise PriceQuoteRequired(
            "Quote MAI Voice pricing for your Azure region/account"
        )

    def _resolve_voice(self, inputs):
        voice = inputs.get("voice_id") or inputs.get("voice") or self.DEFAULT_VOICE
        model = inputs.get("model_id", "MAI-Voice-2.1")
        if ":" in voice:
            base, selected = voice.rsplit(":", 1)
            if selected != model:
                raise ValueError("Voice model suffix conflicts with model_id")
            return voice
        return voice + ":" + model

    def execute(self, inputs):
        import os

        try:
            validate(inputs, self.input_schema)
            key = os.getenv("AZURE_SPEECH_KEY")
            if not key or not (
                os.getenv("AZURE_SPEECH_REGION") or os.getenv("AZURE_TTS_ENDPOINT")
            ):
                raise ValueError(self.install_instructions)
            result = self._synthesize(inputs, key)
            result.model = inputs.get("model_id", "MAI-Voice-2.1")
            result.cost_usd = None
            result.data.update(
                provider=self.provider, model=result.model, cost_status="unquoted"
            )
            return result
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))
