"""nomic-embed-text on an Ollama server."""

import math

import httpx

from cerebro.ports.embeddings import Embedder, EmbedderUnavailable

MODEL = "nomic-embed-text"
# The model card asks for a task prefix on every input; without one the
# vectors for documents and questions drift apart.
DOCUMENT_PREFIX = "search_document: "
QUERY_PREFIX = "search_query: "
# A first request makes the server load the model, which can take a while.
TIMEOUT_SECONDS = 120


def _unit(vector: list[float]) -> list[float]:
    """The vector scaled to length 1."""
    length = math.sqrt(sum(x * x for x in vector))
    return [x / length for x in vector]


class OllamaEmbedder(Embedder):
    """Embeds text with nomic-embed-text, in the batches the caller sends."""

    def __init__(
        self, url: str, *, transport: httpx.BaseTransport | None = None
    ) -> None:
        self.client = httpx.Client(
            base_url=url, timeout=TIMEOUT_SECONDS, transport=transport
        )

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embed([DOCUMENT_PREFIX + text for text in texts])

    def embed_query(self, text: str) -> list[float]:
        return self._embed([QUERY_PREFIX + text])[0]

    def _embed(self, inputs: list[str]) -> list[list[float]]:
        try:
            response = self.client.post(
                "/api/embed", json={"model": MODEL, "input": inputs}
            )
            response.raise_for_status()
        except httpx.HTTPError as error:
            # The error text carries the server's address, so say only its type.
            raise EmbedderUnavailable(
                f"The embedding server failed ({type(error).__name__})"
            ) from None

        return [_unit(vector) for vector in response.json()["embeddings"]]
