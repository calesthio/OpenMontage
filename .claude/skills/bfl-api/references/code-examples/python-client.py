"""
BFL FLUX API Python Client

A complete, production-ready Python client for the BFL FLUX API.
Includes rate limiting, retry logic, webhook support, and async operations.

Usage:
    from bfl_client import BFLClient

    client = BFLClient("your-api-key")
    result = client.generate("flux-2-pro", "A beautiful sunset")
    print(f"Image URL: {result['url']}")
"""

import os
import time
import hmac
import hashlib
import logging
from typing import Dict, Any, List
from dataclasses import dataclass
from threading import Semaphore
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# --- Exceptions ---

class BFLError(Exception):
    """Base exception for BFL API errors."""
    def __init__(self, message: str, status_code: int = None, error_code: str = None):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        super().__init__(message)


class AuthenticationError(BFLError):
    """API key or authentication issue."""
    pass


class InsufficientCreditsError(BFLError):
    """Account needs more credits."""
    pass


class RateLimitError(BFLError):
    """Too many concurrent requests."""
    def __init__(self, message: str, retry_after: int = 5):
        super().__init__(message, 429, "rate_limit_exceeded")
        self.retry_after = retry_after


class ValidationError(BFLError):
    """Invalid request parameters."""
    pass


class GenerationError(BFLError):
    """Generation failed."""
    pass


# --- Data Classes ---

@dataclass
class GenerationResult:
    """Result of a successful generation."""
    id: str
    url: str
    width: int
    height: int
    raw: Dict[str, Any]


# --- Client ---

class BFLClient:
    """
    Production-ready BFL FLUX API client.

    Features:
    - Rate limiting with semaphore
    - Automatic retries with exponential backoff
    - Webhook support
    - Batch processing
    - Async operations

    Example:
        client = BFLClient("your-api-key")
        result = client.generate("flux-2-pro", "A sunset over mountains")
        client.download(result.url, "sunset.png")
    """

    BASE_URLS = {
        "global": "https://api.bfl.ai",
        "eu": "https://api.eu.bfl.ai",
        "us": "https://api.us.bfl.ai",
    }

    RATE_LIMITS = {
        "default": 24,
        "flux-kontext-max": 6,
    }

    def __init__(
        self,
        api_key: str,
        region: str = "global",
        max_concurrent: int = None,
        timeout: int = 120,
    ):
        """
        Initialize the BFL client.

        Args:
            api_key: Your BFL API key
            region: API region ("global", "eu", "us")
            max_concurrent: Max concurrent requests (default: 24)
            timeout: Default polling timeout in seconds
        """
        self.api_key = api_key
        self.base_url = self.BASE_URLS.get(region, self.BASE_URLS["global"])
        self.timeout = timeout
        self.max_concurrent = max_concurrent or self.RATE_LIMITS["default"]
        self.semaphore = Semaphore(self.max_concurrent)

        self.headers = {
            "x-key": api_key,
            "Content-Type": "application/json",
        }

    def generate(
        self,
        model: str,
        prompt: str,
        width: int = 1024,
        height: int = 1024,
        seed: int = None,
        safety_tolerance: int = 2,
        output_format: str = "png",
        webhook_url: str = None,
        webhook_secret: str = None,
        timeout: int = None,
        **kwargs,
    ) -> GenerationResult:
        """
        Generate an image from a text prompt.

        Args:
            model: Model to use (e.g., "flux-2-pro", "flux-2-max")
            prompt: Text description of the image
            width: Image width (multiple of 16)
            height: Image height (multiple of 16)
            seed: Random seed for reproducibility
            safety_tolerance: 0 (strict) to 5 (permissive)
            output_format: "png" or "jpeg"
            webhook_url: URL for async notification
            webhook_secret: Secret for webhook signature
            timeout: Polling timeout override
            **kwargs: Additional model-specific parameters

        Returns:
            GenerationResult with image URL and metadata
        """
        # Validate dimensions
        self._validate_dimensions(width, height)

        # Build payload
        payload = {
            "prompt": prompt,
            "width": width,
            "height": height,
            "safety_tolerance": safety_tolerance,
            "output_format": output_format,
            **kwargs,
        }

        if seed is not None:
            payload["seed"] = seed
        if webhook_url:
            payload["webhook_url"] = webhook_url
        if webhook_secret:
            payload["webhook_secret"] = webhook_secret

        # Rate-limited request
        with self.semaphore:
            return self._submit_and_poll(model, payload, timeout or self.timeout)

    def generate_i2i(
        self,
        model: str,
        prompt: str,
        input_image: str,
        additional_images: List[str] = None,
        **kwargs,
    ) -> GenerationResult:
        """
        Generate an image from another image (image-to-image).

        Preferred: Pass image URLs directly - simpler and more convenient than base64.
        The API fetches URLs automatically. Both URL and base64 work.

        Args:
            model: Model to use (e.g., "flux-2-pro", "flux-2-max")
            prompt: Edit instructions
            input_image: Image URL (preferred) or base64
            additional_images: List of additional reference image URLs or base64
            **kwargs: Additional parameters

        Returns:
            GenerationResult with edited image

        Example:
            result = client.generate_i2i(
                "flux-2-pro",
                "Change the background to a sunset",
                "https://example.com/photo.jpg"  # URL is simpler!
            )
        """
        payload = {
            "prompt": prompt,
            "input_image": input_image,
            **kwargs,
        }

        # Add additional images
        if additional_images:
            for i, img in enumerate(additional_images[:7], start=2):
                payload[f"input_image_{i}"] = img

        with self.semaphore:
            return self._submit_and_poll(model, payload, self.timeout)

    def generate_batch(
        self,
        model: str,
        prompts: List[str],
        max_workers: int = None,
        **kwargs,
    ) -> List[GenerationResult]:
        """
        Generate multiple images concurrently.

        Args:
            model: Model to use
            prompts: List of prompts
            max_workers: Number of concurrent workers
            **kwargs: Parameters applied to all generations

        Returns:
            List of GenerationResult objects
        """
        max_workers = max_workers or min(len(prompts), self.max_concurrent)
        results = []

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(self.generate, model, prompt, **kwargs): prompt
                for prompt in prompts
            }

            for future in as_completed(futures):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    logger.error(f"Generation failed: {e}")
                    results.append(None)

        return results

    def download(self, url: str, output_path: str) -> str:
        """
        Download a generated image.

        Args:
            url: Image URL (expires in 10 minutes)
            output_path: Local path to save the image

        Returns:
            Path to saved file
        """
        response = requests.get(url, timeout=60)
        response.raise_for_status()

        with open(output_path, "wb") as f:
            f.write(response.content)

        return output_path

    def _submit_and_poll(
        self,
        model: str,
        payload: Dict[str, Any],
        timeout: int,
    ) -> GenerationResult:
        """Submit request and poll for result."""
        endpoint = f"{self.base_url}/v1/{model}"

        # Submit with retry
        response = self._request_with_retry(
            "POST",
            endpoint,
            json=payload,
        )

        polling_url = response["polling_url"]
        generation_id = response.get("id", polling_url.split("=")[-1])

        # Poll for result
        result = self._poll(polling_url, timeout)

        return GenerationResult(
            id=generation_id,
            url=result["sample"],
            width=result.get("width", payload.get("width")),
            height=result.get("height", payload.get("height")),
            raw=result,
        )

    def _poll(self, polling_url: str, timeout: int) -> Dict[str, Any]:
        """Poll until completion or timeout."""
        start_time = time.time()
        delay = 1.0

        while time.time() - start_time < timeout:
            response = self._request_with_retry("GET", polling_url)

            status = response.get("status")
            if status == "Ready":
                return response.get("result", response)
            elif status == "Error":
                error = response.get("error", "Generation failed")
                raise GenerationError(error)

            # Exponential backoff (cap at 5 seconds)
            time.sleep(delay)
            delay = min(delay * 1.5, 5.0)

        raise TimeoutError(f"Generation timed out after {timeout}s")

    def _request_with_retry(
        self,
        method: str,
        url: str,
        max_retries: int = 3,
        **kwargs,
    ) -> Dict[str, Any]:
        """Make HTTP request with retry logic."""
        last_exception = None

        for attempt in range(max_retries):
            try:
                response = requests.request(
                    method,
                    url,
                    headers=self.headers,
                    timeout=30,
                    **kwargs,
                )

                return self._handle_response(response)

            except RateLimitError as e:
                logger.warning(f"Rate limited, waiting {e.retry_after}s")
                time.sleep(e.retry_after * (attempt + 1))
                last_exception = e

            except BFLError as e:
                if e.status_code and e.status_code >= 500:
                    wait_time = 2 ** attempt
                    logger.warning(f"Server error, retrying in {wait_time}s")
                    time.sleep(wait_time)
                    last_exception = e
                else:
                    raise

        raise last_exception

    def _handle_response(self, response: requests.Response) -> Dict[str, Any]:
        """Process API response and raise appropriate errors."""
        if response.status_code == 200:
            return response.json()

        try:
            error_data = response.json()
        except:
            error_data = {"message": response.text}

        error_code = error_data.get("error", "unknown")
        message = error_data.get("message", "Unknown error")

        if response.status_code == 401:
            raise AuthenticationError(message, 401, error_code)
        elif response.status_code == 402:
            raise InsufficientCreditsError(message, 402, error_code)
        elif response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 5))
            raise RateLimitError(message, retry_after)
        elif response.status_code == 400:
            raise ValidationError(message, 400, error_code)
        else:
            raise BFLError(message, response.status_code, error_code)

    def _validate_dimensions(self, width: int, height: int):
        """Validate image dimensions."""
        if width % 16 != 0:
            raise ValidationError(f"Width {width} must be a multiple of 16")
        if height % 16 != 0:
            raise ValidationError(f"Height {height} must be a multiple of 16")
        if width * height > 4_000_000:
            raise ValidationError(f"Total pixels ({width}x{height}) exceeds 4MP limit")
        if width < 64 or height < 64:
            raise ValidationError("Minimum dimension is 64 pixels")


# --- Webhook Verification ---

def verify_webhook_signature(payload: bytes, signature: str, secret: str) -> bool:
    """
    Verify a webhook signature from BFL.

    Args:
        payload: Raw request body
        signature: X-BFL-Signature header value
        secret: Your webhook secret

    Returns:
        True if signature is valid
    """
    if not signature or not signature.startswith("sha256="):
        return False

    expected = hmac.new(
        secret.encode("utf-8"),
        payload,
        hashlib.sha256,
    ).hexdigest()

    provided = signature[7:]  # Remove 'sha256=' prefix

    return hmac.compare_digest(expected, provided)


# --- Example Usage ---

if __name__ == "__main__":
    # Get API key from environment
    api_key = os.environ.get("BFL_API_KEY")
    if not api_key:
        print("Set BFL_API_KEY environment variable")
        exit(1)

    # Create client
    client = BFLClient(api_key)

    # Generate a single image
    print("Generating image...")
    result = client.generate(
        model="flux-2-pro",
        prompt="A serene mountain landscape at golden hour, dramatic lighting",
        width=1024,
        height=1024,
    )
    print(f"Generated: {result.url}")

    # Download the image
    client.download(result.url, "output.png")
    print("Saved to output.png")
