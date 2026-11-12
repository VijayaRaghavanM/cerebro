"""The only place that picks concrete classes and wires them together."""

from collections.abc import Callable, Iterator
from enum import StrEnum
from pathlib import Path

import httpx
from langchain_core.language_models import BaseChatModel
from pydantic import SecretStr

from cerebro.adapters import llm_judge
from cerebro.adapters.comicvine_api import ComicVineClient
from cerebro.adapters.comicvine_dump import ComicVineDump
from cerebro.adapters.fandom import FandomClient
from cerebro.adapters.fandom_records import FandomRecordParser
from cerebro.adapters.http_recording import RecordingTransport, ReplayTransport
from cerebro.adapters.jsonl_evaluation import JsonlGoldenSet, JsonlRunStore
from cerebro.adapters.jsonl_pages import JsonlPageStore
from cerebro.adapters.langgraph_agent import LangGraphAgent
from cerebro.adapters.llm_judge import LlmJudge
from cerebro.adapters.mistral import ministral
from cerebro.adapters.numpy_vectors import NumpyVectorIndex, NumpyVectorStore
from cerebro.adapters.ollama import MODEL as EMBEDDING_MODEL
from cerebro.adapters.ollama import OllamaEmbedder
from cerebro.adapters.openai_chat import openai_chat
from cerebro.adapters.sqlite_chunks import SqliteChunkIndex
from cerebro.adapters.sqlite_comicvine import SqliteComicVineStore
from cerebro.adapters.sqlite_records import SqliteRecordStore
from cerebro.adapters.vector_chunks import VectorChunkSearch
from cerebro.application import (
    chunking,
    crawl,
    embedding,
    evaluation,
    judging,
    loading,
    matching,
    parse,
    scoring,
)
from cerebro.application import crawl_comicvine as comicvine_crawl
from cerebro.application.retrieval import FusedSearch
from cerebro.domain.answers import Step
from cerebro.domain.evaluation import Exchange, Split
from cerebro.domain.pages import Category
from cerebro.domain.scoring import Price
from cerebro.ports.chunks import ChunkSearch
from cerebro.settings import Settings

# The chunks share the records' file, so a search and the agent's tools read one file.
RECORDS_FILE = "records.sqlite"

# Both are relative to where the command runs, which is the repository.
GOLDEN_FILE = Path("evals/golden.jsonl")
RUNS_DIR = Path("runs")


OPENROUTER_URL = "https://openrouter.ai/api/v1"


class Contestant(StrEnum):
    """The models `ask` can run on. The values are what `--model` accepts."""

    MINISTRAL_14B = "ministral-14b"
    MINISTRAL_14B_OPENROUTER = "ministral-14b-openrouter"
    MINISTRAL_3B_OPENROUTER = "ministral-3b-openrouter"
    QWEN3_14B_OLLAMA = "qwen3-14b-ollama"
    GEMINI_FLASH_OPENROUTER = "gemini-3.8-flash-openrouter"


class MissingKey(Exception):
    """An API key the command needs is not set. The message is the variable's name."""


def crawl_fandom(
    category: Category,
    *,
    limit: int | None = None,
    progress: crawl.Progress | None = None,
) -> crawl.CrawlReport:
    """Crawl one Marvel Database category into DATA_DIR/raw/fandom/."""
    return crawl.crawl(
        FandomClient(), _pages(), category, limit=limit, progress=progress
    )


def crawl_comicvine(
    *,
    top: int,
    max_calls: int | None = None,
    progress: comicvine_crawl.Progress | None = None,
) -> comicvine_crawl.ComicVineCrawlReport:
    """Crawl Comic Vine's Marvel characters into DATA_DIR/raw/comicvine/."""
    key = Settings().comicvine_api_key
    if key is None:
        raise MissingKey("COMICVINE_API_KEY")

    return comicvine_crawl.crawl_comicvine(
        ComicVineClient(key),
        _comicvine_dump(),
        top=top,
        max_calls=max_calls,
        progress=progress,
    )


def parse_fandom(
    category: Category, *, progress: parse.Progress | None = None
) -> parse.ParseReport:
    """Parse one category's saved Marvel Database pages into DATA_DIR/records.sqlite."""
    return parse.parse(
        _pages(), FandomRecordParser(category), _records(), category, progress=progress
    )


def load_comicvine() -> loading.LoadReport:
    """Store Comic Vine's characters in DATA_DIR/raw/comicvine/ in the record store."""
    return loading.load_comicvine(_comicvine_dump(), _comicvine())


def match_comicvine() -> matching.MatchReport:
    """Match Comic Vine's characters in DATA_DIR/raw/comicvine/ to the stored ones."""
    return matching.match_comicvine(_records(), _comicvine_dump(), _comicvine())


def chunk_records() -> chunking.ChunkReport:
    """Cut the stored character pages into chunks in DATA_DIR/records.sqlite."""
    return chunking.chunk_records(_records(), _chunks())


def embed_chunks(progress: embedding.Progress | None = None) -> embedding.EmbedReport:
    """Embed the stored chunks on the Ollama server into DATA_DIR/embeddings/text/."""
    settings = Settings()
    if settings.ollama_base_url is None:
        raise MissingKey("OLLAMA_BASE_URL")

    embedder = OllamaEmbedder(settings.ollama_base_url)
    store = NumpyVectorStore(settings.data_dir / "embeddings" / "text")

    return embedding.embed_chunks(_chunks(), embedder, store, progress=progress)


def ask(question: str, model: Contestant = Contestant.MINISTRAL_14B) -> Iterator[Step]:
    """Answer a question from DATA_DIR/records.sqlite with the chosen model.

    Returns the agent's steps, ending with the answer. The key is checked here, not
    on the first step, so a missing key fails before any step is read.
    """
    return _agent(chat_model(model), chunk_search()).steps(question)


def search_label() -> str:
    """One line saying how `ask` searches the passages."""
    if Settings().ollama_base_url is None:
        return "Searching by keyword only (set OLLAMA_BASE_URL to add meaning)."

    return "Searching by keyword and meaning."


def chunk_search(transport: httpx.BaseTransport | None = None) -> ChunkSearch:
    """The agent's passage search: keyword and meaning fused when OLLAMA_BASE_URL is
    set, keyword alone when it is not. Query embeddings are sent through `transport`.
    """
    url = Settings().ollama_base_url
    if url is None:
        return _chunks()

    return _fused(url, transport)


def run_eval(
    model: Contestant,
    split: Split | None = None,
    *,
    limit: int | None = None,
    run_name: str | None = None,
    progress: evaluation.Progress | None = None,
) -> evaluation.RunReport:
    """Answer the golden questions with one model into runs/<run_name>/.

    The run is named after the model and split unless `run_name` says otherwise,
    so running the same command again resumes the same run. Every model exchange
    is kept in the run's folder, so `replay_run` can rerun it. That includes the
    query embeddings, which come from the same server as the search's meaning.
    """
    name = run_name or f"{model}-{split or 'all'}"
    questions = JsonlGoldenSet(GOLDEN_FILE).questions(split)

    def ask_model(question: str, exchanges: list[Exchange]) -> Iterator[Step]:
        recorder = RecordingTransport(exchanges=exchanges)
        return _agent(chat_model(model, recorder), chunk_search(recorder)).steps(
            question
        )

    return evaluation.run_eval(
        ask_model,
        questions,
        JsonlRunStore(RUNS_DIR / name),
        model=model.value,
        limit=limit,
        progress=progress,
    )


def replay_run(run_name: str) -> evaluation.ReplayReport:
    """Rerun runs/<run_name>/ from its saved exchanges, with no network and no keys,
    and compare each answered question with its saved result.
    """
    questions = JsonlGoldenSet(GOLDEN_FILE).questions(None)

    def reask(model: str, question: str, exchanges: list[Exchange]) -> Iterator[Step]:
        # One replayer serves the model and the embedder, because the exchanges
        # are kept in the order they were sent. The run decides which search is
        # replayed: one that embedded a query used the server, and one that did not
        # searched by keyword, so a replay needs neither the setting nor the server.
        replayer = ReplayTransport(exchanges)
        search: ChunkSearch = _chunks()
        if any(_embedded(exchange) for exchange in exchanges):
            search = _fused(_REPLAY_URL, replayer)

        chat = chat_model(Contestant(model), replayer, offline=True)
        return _agent(chat, search).steps(question)

    return evaluation.replay_run(reask, questions, JsonlRunStore(RUNS_DIR / run_name))


def score_run(run_name: str) -> str | None:
    """Score runs/<run_name>/ against the golden questions into scores.json and
    report.md in its folder. Returns the overall totals in one line, or None when
    the run has no results.
    """
    questions = JsonlGoldenSet(GOLDEN_FILE).questions(None)
    prices = {contestant.value: price for contestant, price in _PRICES.items()}

    return scoring.score_run(questions, JsonlRunStore(RUNS_DIR / run_name), prices)


def judge_run(
    run_name: str, progress: judging.Progress | None = None
) -> judging.JudgeReport:
    """Have the judge rule on the answers in runs/<run_name>/, into verdicts.jsonl
    in its folder. One judge serves every run, so their scores compare.

    Raises MissingKey if the judge's key is not set.
    """
    key = Settings().cerebras_api_key
    if key is None:
        raise MissingKey("CEREBRAS_API_KEY")

    judge = LlmJudge(
        openai_chat(
            llm_judge.BASE_URL,
            llm_judge.MODEL,
            api_key=key,
            extra_body=llm_judge.EXTRA_BODY,
            rate_limiter=llm_judge.PACE,
        )
    )
    questions = JsonlGoldenSet(GOLDEN_FILE).questions(None)

    return judging.judge_run(
        judge, questions, JsonlRunStore(RUNS_DIR / run_name), progress
    )


def chat_model(
    contestant: Contestant,
    transport: httpx.BaseTransport | None = None,
    *,
    offline: bool = False,
) -> BaseChatModel:
    """The contestant's model, sending through `transport` if given.

    Raises MissingKey if its key or server is not set. An offline model is for a
    replay: it needs no key, and does not wait between requests.
    """
    settings = Settings()
    if offline:
        settings = settings.model_copy(update=_PLACEHOLDERS)

    return _CONTESTANTS[contestant](settings, transport, offline)


# What an offline model is built with: nothing is sent, so no real key is needed.
_REPLAY_URL = "http://replay.invalid"
_PLACEHOLDERS = {
    "mistral_api_key": SecretStr("replay"),
    "openrouter_api_key": SecretStr("replay"),
    "ollama_base_url": _REPLAY_URL,
}

# Each contestant's builder takes the settings, the transport and whether the model
# is offline, and raises MissingKey for what it lacks.
Builder = Callable[[Settings, httpx.BaseTransport | None, bool], BaseChatModel]


def _mistral(
    settings: Settings, transport: httpx.BaseTransport | None, offline: bool
) -> BaseChatModel:
    if settings.mistral_api_key is None:
        raise MissingKey("MISTRAL_API_KEY")

    return ministral(settings.mistral_api_key, transport, paced=not offline)


def _openrouter(model: str, *, pin_to: str | None = None) -> Builder:
    """A builder for one OpenRouter model, optionally served only by one provider."""

    def build(
        settings: Settings, transport: httpx.BaseTransport | None, offline: bool
    ) -> BaseChatModel:
        if settings.openrouter_api_key is None:
            raise MissingKey("OPENROUTER_API_KEY")

        # Without the pin, OpenRouter may route to a provider that quantizes the model.
        extra_body = None
        if pin_to is not None:
            extra_body = {"provider": {"order": [pin_to], "allow_fallbacks": False}}

        return openai_chat(
            OPENROUTER_URL,
            model,
            api_key=settings.openrouter_api_key,
            extra_body=extra_body,
            transport=transport,
        )

    return build


def _ollama(model: str) -> Builder:
    def build(
        settings: Settings, transport: httpx.BaseTransport | None, offline: bool
    ) -> BaseChatModel:
        if settings.ollama_base_url is None:
            raise MissingKey("OLLAMA_BASE_URL")

        return openai_chat(
            f"{settings.ollama_base_url.rstrip('/')}/v1", model, transport=transport
        )

    return build


_CONTESTANTS: dict[Contestant, Builder] = {
    Contestant.MINISTRAL_14B: _mistral,
    Contestant.MINISTRAL_14B_OPENROUTER: _openrouter(
        "mistralai/ministral-14b-2512", pin_to="Mistral"
    ),
    Contestant.MINISTRAL_3B_OPENROUTER: _openrouter(
        "mistralai/ministral-3b-2512", pin_to="Mistral"
    ),
    Contestant.QWEN3_14B_OLLAMA: _ollama("qwen3:14b"),
    Contestant.GEMINI_FLASH_OPENROUTER: _openrouter("google/gemini-3.8-flash"),
}


# Dollars per million tokens, from OpenRouter's public model list on 2026-11-12.
# Mistral's free tier and a model on our own server cost nothing.
_PRICES: dict[Contestant, Price] = {
    Contestant.MINISTRAL_14B: Price(0, 0),
    Contestant.MINISTRAL_14B_OPENROUTER: Price(0.20, 0.20),
    Contestant.MINISTRAL_3B_OPENROUTER: Price(0.10, 0.10),
    Contestant.QWEN3_14B_OLLAMA: Price(0, 0),
    Contestant.GEMINI_FLASH_OPENROUTER: Price(0.825, 4.125),
}


def _agent(model: BaseChatModel, chunks: ChunkSearch) -> LangGraphAgent:
    return LangGraphAgent(model, _records(), chunks)


def _fused(url: str, transport: httpx.BaseTransport | None) -> FusedSearch:
    keyword = _chunks()
    embedder = OllamaEmbedder(url, transport=transport)
    vectors = NumpyVectorIndex(Settings().data_dir / "embeddings" / "text")

    return FusedSearch([keyword, VectorChunkSearch(embedder, vectors, keyword)])


def _embedded(exchange: Exchange) -> bool:
    """Whether the exchange is a query sent to the embedding server."""
    sent_to: object = exchange["request"].get("model")
    return sent_to == EMBEDDING_MODEL


def _pages() -> JsonlPageStore:
    return JsonlPageStore(Settings().data_dir / "raw" / "fandom")


def _comicvine_dump() -> ComicVineDump:
    return ComicVineDump(Settings().data_dir / "raw" / "comicvine")


def _records() -> SqliteRecordStore:
    return SqliteRecordStore(Settings().data_dir / RECORDS_FILE)


def _comicvine() -> SqliteComicVineStore:
    return SqliteComicVineStore(Settings().data_dir / RECORDS_FILE)


def _chunks() -> SqliteChunkIndex:
    return SqliteChunkIndex(Settings().data_dir / RECORDS_FILE)
