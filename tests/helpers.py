"""Helpers that more than one test file uses."""

import json
import sqlite3
from dataclasses import fields
from pathlib import Path
from typing import TYPE_CHECKING, Any, get_origin

import httpx

from cerebro.adapters.fandom_wikitext import parse_character, parse_comic, parse_team
from cerebro.domain.answers import Answer
from cerebro.domain.chunks import Chunk, ChunkHit
from cerebro.domain.comicvine import (
    ComicVineCharacter,
    ComicVineDetail,
    ComicVineIssue,
)
from cerebro.domain.pages import RawPage
from cerebro.domain.records import (
    Appearance,
    Appearances,
    Character,
    Comic,
    PageHit,
    Record,
    Team,
)
from cerebro.ports.agent import Agent
from cerebro.ports.chunks import ChunkSearch
from cerebro.ports.records import RecordLookup

if TYPE_CHECKING:
    from _typeshed import DataclassInstance

FIXTURES = Path(__file__).parent / "fixtures" / "fandom"


def rows(path: Path, sql: str, *params: object) -> list[tuple[object, ...]]:
    """What a query returns from the SQLite file at `path`."""
    with sqlite3.connect(path) as db:
        return db.execute(sql, params).fetchall()


def blank[T: DataclassInstance](cls: type[T], **values: Any) -> T:
    """A record with only `values` filled: None for text, () for lists."""
    empty = {
        field.name: () if get_origin(field.type) is tuple else None
        for field in fields(cls)
    }
    return cls(**(empty | values))


# Saved wiki pages


def fixture(name: str) -> RawPage:
    """The saved wiki page in tests/fixtures/fandom with this file name."""
    return RawPage(**json.loads((FIXTURES / name).read_text(encoding="utf-8")))


def real_character() -> Character:
    """The Daniel Berkhart page, parsed."""
    record = parse_character(fixture("daniel_berkhart.json"))
    assert record is not None
    return record


def real_team() -> Team:
    """The Livewires page, parsed."""
    record = parse_team(fixture("livewires.json"))
    assert record is not None
    return record


def real_comic() -> Comic:
    """The Marvel Comics Presents #170 page, parsed."""
    record = parse_comic(fixture("marvel_comics_presents_170.json"))
    assert record is not None
    return record


# Made-up records


def character(**values: Any) -> Character:
    """A made-up character with only `values` filled besides its page and title."""
    return blank(Character, pageid=1, title="Ann Doe (Earth-1)", revid=7, **values)


def detail(**values: Any) -> ComicVineDetail:
    """A Comic Vine detail with only `values` filled."""
    return blank(ComicVineDetail, **values)


def vine(detail: ComicVineDetail | None = None) -> ComicVineCharacter:
    """A made-up Comic Vine character, with this detail if it has one."""
    return ComicVineCharacter(
        5, "Weather Witch", "Ann Doe", (), 321, "https://vine.example/5", detail
    )


def comicvine_characters() -> list[ComicVineCharacter]:
    """Made-up characters: one fetched in detail, one only listed."""
    detail = ComicVineDetail(
        issues=(ComicVineIssue("Strange Tales", "3", "1951-05-01"),),
        deck="Controls the weather.",
        birth=None,
        gender="female",
        origin="Mutant",
        powers=("Flight", "Lightning"),
        creators=(),
        teams=("Storm Watch",),
        team_friends=(),
        team_enemies=(),
        friends=(),
        enemies=(),
        volumes=("Strange Tales",),
        movies=(),
        died_in=(ComicVineIssue("Strange Tales", "4", None),),
        story_arcs=(),
        updated="2020-01-02 03:04:05",
    )
    witch = ComicVineCharacter(
        1,
        "Weather Witch",
        "Ann Doe",
        ("Stormcaller",),
        12,
        "https://cv.example/1",
        detail,
    )
    nobody = ComicVineCharacter(2, "Nobody", None, (), 0, "https://cv.example/2", None)
    return [witch, nobody]


# Fakes


class FakeLookup(RecordLookup):
    """A record lookup that answers from the hits, records, match and casts given."""

    def __init__(
        self,
        hits: list[PageHit] | None = None,
        records: list[Record] | None = None,
        comicvine: ComicVineCharacter | None = None,
        casts: dict[str, list[Appearance]] | None = None,
    ) -> None:
        self.casts = casts or {}
        self.hits = hits or []
        self.records = {record.title: record for record in records or []}
        self.matched = comicvine
        self.limits: list[int] = []

    def find(self, name: str, limit: int) -> list[PageHit]:
        self.limits.append(limit)
        return self.hits[:limit]

    def record(self, title: str) -> Record | None:
        return self.records.get(title)

    def appearances(self, title: str, limit: int) -> Appearances:
        self.limits.append(limit)
        found = self.casts.get(title, [])
        return Appearances(len(found), tuple(found[:limit]))

    def comicvine(self, pageid: int) -> ComicVineCharacter | None:
        return self.matched

    def url(self, title: str) -> str:
        return f"https://wiki.example/{title.replace(' ', '_')}"


def passage(title: str, section: str, text: str) -> ChunkHit:
    """A made-up search hit: a chunk of this page and section."""
    chunk = Chunk("1:7:0", 1, 7, 0, title, section, "", text)
    return ChunkHit(chunk, 1.0)


class FakeChunkSearch(ChunkSearch):
    """A chunk search that answers the hits it was given, up to the limit."""

    def __init__(self, hits: list[ChunkHit] | None = None) -> None:
        self.hits = hits or []
        self.limits: list[int] = []

    def search(self, query: str, limit: int) -> list[ChunkHit]:
        self.limits.append(limit)
        return self.hits[:limit]


# Running an agent


def final_answer(agent: Agent, question: str) -> Answer:
    """The answer the agent gives last, after all its steps."""
    steps = list(agent.steps(question))

    last = steps[-1]
    assert isinstance(last, Answer), "steps must end with the answer"
    return last


# Recorded Mistral exchanges


def _contract(body: dict[str, Any]) -> tuple[Any, list[str]]:
    """What a request must keep matching: the model and the tools it offers."""
    tools = [tool["function"]["name"] for tool in body.get("tools", [])]
    return body.get("model"), tools


def replay(path: Path) -> httpx.MockTransport:
    """Answers each request with the next recorded reply, in order.

    A request whose model or tool names differ from the recording fails: our
    requests have drifted, so the recording needs redoing.
    """
    exchanges = iter(json.loads(path.read_text(encoding="utf-8")))

    def answer(request: httpx.Request) -> httpx.Response:
        exchange = next(exchanges, None)
        assert exchange is not None, "more requests than recorded exchanges"

        sent = json.loads(request.content)
        assert _contract(sent) == _contract(exchange["request"]), "re-record"

        reply = exchange["response"]
        return httpx.Response(reply["status"], json=reply["body"])

    return httpx.MockTransport(answer)


class RecordingTransport(httpx.BaseTransport):
    """Passes requests to the real API and keeps each body, never the headers."""

    def __init__(self) -> None:
        self.inner = httpx.HTTPTransport()
        self.exchanges: list[dict[str, Any]] = []

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        response = self.inner.handle_request(request)
        body = json.loads(response.read())
        self.exchanges.append(
            {
                "request": json.loads(request.content),
                "response": {"status": response.status_code, "body": body},
            }
        )
        return httpx.Response(response.status_code, json=body)

    def save(self, path: Path, last_only: bool = False) -> None:
        exchanges = self.exchanges[-1:] if last_only else self.exchanges
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(exchanges, indent=2) + "\n", encoding="utf-8")
