"""The Ollama embedder: what it sends, what it returns, how it fails."""

import json
import math
from typing import Any

import httpx
import pytest

from cerebro.adapters.ollama import OllamaEmbedder
from cerebro.ports.embeddings import EmbedderUnavailable
from cerebro.settings import Settings


def embedder_over(
    handler: Any, sent: list[dict[str, Any]] | None = None
) -> OllamaEmbedder:
    """An embedder whose server is `handler`; request bodies are kept in `sent`."""

    def serve(request: httpx.Request) -> httpx.Response:
        if sent is not None:
            sent.append(json.loads(request.content))
        return handler(request)

    client = httpx.Client(
        base_url="http://ollama.test", transport=httpx.MockTransport(serve)
    )
    return OllamaEmbedder("http://ollama.test", client=client)


def reply(vectors: list[list[float]]) -> Any:
    return lambda request: httpx.Response(200, json={"embeddings": vectors})


def length(vector: list[float]) -> float:
    return math.sqrt(sum(x * x for x in vector))


def test_documents_are_sent_with_the_document_prefix() -> None:
    sent: list[dict[str, Any]] = []
    embedder = embedder_over(reply([[1.0, 0.0], [0.0, 1.0]]), sent)

    embedder.embed_documents(["Storm", "Cyclops"])

    assert sent == [
        {
            "model": "nomic-embed-text",
            "input": ["search_document: Storm", "search_document: Cyclops"],
        }
    ]


def test_a_query_is_sent_with_the_query_prefix() -> None:
    sent: list[dict[str, Any]] = []
    embedder = embedder_over(reply([[1.0, 0.0]]), sent)

    embedder.embed_query("Who is Storm?")

    assert sent == [
        {"model": "nomic-embed-text", "input": ["search_query: Who is Storm?"]}
    ]


def test_vectors_come_back_with_length_one() -> None:
    embedder = embedder_over(reply([[3.0, 4.0], [0.0, 2.0]]))

    documents = embedder.embed_documents(["a", "b"])
    query = embedder.embed_query("a")

    assert [length(v) for v in documents] == pytest.approx([1.0, 1.0])
    assert length(query) == pytest.approx(1.0)
    assert documents[0] == pytest.approx([0.6, 0.8])


def test_a_server_error_is_unavailable() -> None:
    embedder = embedder_over(lambda request: httpx.Response(500))

    with pytest.raises(EmbedderUnavailable):
        embedder.embed_query("Storm")


def test_a_refused_connection_is_unavailable() -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    with pytest.raises(EmbedderUnavailable) as raised:
        embedder_over(refuse).embed_documents(["Storm"])

    assert "ollama.test" not in str(raised.value)


@pytest.mark.live
def test_a_related_pair_scores_higher_than_an_unrelated_one() -> None:
    url = Settings().ollama_base_url
    if url is None:
        pytest.skip("OLLAMA_BASE_URL is not set")
    embedder = OllamaEmbedder(url)

    storm, weather, tax = embedder.embed_documents(
        [
            "Ann Doe controls lightning and storms.",
            "She can summon thunder and rain.",
            "The accountant filed the quarterly tax return.",
        ]
    )

    def cosine(a: list[float], b: list[float]) -> float:
        return sum(x * y for x, y in zip(a, b, strict=True))

    assert len(storm) == 768
    assert cosine(storm, weather) > cosine(storm, tax)
