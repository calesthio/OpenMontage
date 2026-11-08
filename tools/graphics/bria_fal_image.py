"""Schema-backed bria_fal_image on fal; no automatic host/model fallback."""

from tools.fal_media import FalMedia


class BriaFalImage(FalMedia):
    name = "bria_fal_image"
    capability = "image_generation"
    routes = {
        "fibo-2": {"generate": "bria/fibo-2/generate", "edit": "bria/fibo-2/edit"}
    }
    capabilities = ["generate", "edit"]
    best_for = ["bria_fal_image"]

    def build_request(self, inputs):
        inputs = dict(inputs)
        operation = inputs.get("generation_mode") or inputs.get("operation")
        if operation is None and any(
            inputs.get(k)
            for k in ("image_paths", "image_path", "image_urls", "image_url")
        ):
            operation = "edit"
        if operation == "edit":
            if "prompt" in inputs and "instruction" not in inputs:
                inputs["instruction"] = inputs.pop("prompt")
        model, operation, endpoint, payload = super().build_request(inputs)
        if not (
            payload.get("prompt") or payload.get("instruction") or payload.get("vgl")
        ):
            raise ValueError("Fibo requires prompt/instruction or VGL")
        return model, operation, endpoint, payload
