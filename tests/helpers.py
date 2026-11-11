"""Helpers that more than one test file uses."""

import json
from dataclasses import fields
from pathlib import Path
from typing import TYPE_CHECKING, Any, get_origin

from cerebro.adapters.fandom_wikitext import parse_character, parse_comic, parse_team
from cerebro.domain.comicvine import (
    ComicVineCharacter,
    ComicVineDetail,
    ComicVineIssue,
)
from cerebro.domain.pages import RawPage
from cerebro.domain.records import Character, Comic, PageHit, Record, Team
from cerebro.ports.records import RecordLookup

if TYPE_CHECKING:
    from _typeshed import DataclassInstance

FIXTURES = Path(__file__).parent / "fixtures" / "fandom"


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
    """A record lookup that answers from the hits, records and match it was given."""

    def __init__(
        self,
        hits: list[PageHit] | None = None,
        records: list[Record] | None = None,
        comicvine: ComicVineCharacter | None = None,
    ) -> None:
        self.hits = hits or []
        self.records = {record.title: record for record in records or []}
        self.matched = comicvine
        self.limits: list[int] = []

    def find(self, name: str, limit: int) -> list[PageHit]:
        self.limits.append(limit)
        return self.hits[:limit]

    def record(self, title: str) -> Record | None:
        return self.records.get(title)

    def comicvine(self, pageid: int) -> ComicVineCharacter | None:
        return self.matched

    def url(self, title: str) -> str:
        return f"https://wiki.example/{title.replace(' ', '_')}"
