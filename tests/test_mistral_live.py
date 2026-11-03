"""Live check against the Mistral API.

Skipped in normal runs. Run with: uv run pytest -m live
"""

import json
import urllib.error
import urllib.request

import pytest

from cerebro.settings import Settings

MODELS_URL = "https://api.mistral.ai/v1/models"
MAIN_MODEL = "ministral-14b-2512"


@pytest.mark.live
def test_mistral_key_can_see_main_model() -> None:
    key = Settings().mistral_api_key
    if key is None:
        pytest.skip("MISTRAL_API_KEY is not set")

    request = urllib.request.Request(
        MODELS_URL,
        headers={"Authorization": f"Bearer {key.get_secret_value()}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            body = json.load(response)
    except urllib.error.HTTPError as error:
        # Status code only, no traceback: the request headers are never printed.
        pytest.fail(f"Mistral returned HTTP {error.code}", pytrace=False)

    model_ids = {model["id"] for model in body["data"]}
    assert MAIN_MODEL in model_ids
