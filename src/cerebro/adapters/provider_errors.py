"""The port's errors for a model provider's failures."""

import httpx
import openai

from cerebro.ports.agent import ModelTimeout, ProviderError, RateLimited


def port_error(error: httpx.HTTPError | openai.APIError) -> Exception:
    """The port's error for a failed model call. The message names the status, never
    the URL or a key.
    """
    if isinstance(error, (httpx.TimeoutException, openai.APITimeoutError)):
        return ModelTimeout("The model did not reply in time.")

    status = None
    if isinstance(error, httpx.HTTPStatusError):
        status = error.response.status_code
    if isinstance(error, openai.APIStatusError):
        status = error.status_code

    if status == 429:
        return RateLimited("The model provider is rate limiting us.")
    if status is not None:
        return ProviderError(f"The model provider returned HTTP {status}.")
    return ProviderError("The model provider could not be reached.")
