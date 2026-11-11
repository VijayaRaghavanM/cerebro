from dataclasses import fields
from typing import TYPE_CHECKING, Any, get_origin

from cerebro.application.tools import (
    FIELD_LIMIT,
    PAGE_LIMIT,
    SEARCH_LIMIT,
    read_page,
    search_pages,
)
from cerebro.domain.answers import Source
from cerebro.domain.comicvine import (
    ComicVineCharacter,
    ComicVineDetail,
    ComicVineIssue,
)
from cerebro.domain.pages import Category
from cerebro.domain.records import (
    Character,
    Comic,
    Credits,
    PageHit,
    Record,
    Story,
    Team,
)
from cerebro.ports.records import RecordLookup

if TYPE_CHECKING:
    from _typeshed import DataclassInstance


def blank[T: DataclassInstance](cls: type[T], **values: Any) -> T:
    """A record with only `values` filled: None for text, () for lists."""
    empty = {
        field.name: () if get_origin(field.type) is tuple else None
        for field in fields(cls)
    }
    return cls(**(empty | values))


class FakeLookup(RecordLookup):
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


def character(**values: Any) -> Character:
    return blank(Character, pageid=1, title="Ann Doe (Earth-1)", revid=7, **values)


def detail(**values: Any) -> ComicVineDetail:
    return blank(ComicVineDetail, **values)


def vine(detail: ComicVineDetail | None = None) -> ComicVineCharacter:
    return ComicVineCharacter(
        5, "Weather Witch", "Ann Doe", (), 321, "https://vine.example/5", detail
    )


def test_a_search_lists_numbered_pages_with_their_appearances() -> None:
    hits = [
        PageHit("Ann Doe (Earth-1)", Category.CHARACTERS, 4990),
        PageHit("Storm Club (Earth-1)", Category.TEAMS, 12),
        PageHit("Storm Tales Vol 1 1", Category.COMICS, 0),
    ]

    result = search_pages(FakeLookup(hits), "storm")

    assert result.text == (
        '1. "Ann Doe (Earth-1)": character, in 4,990 comics\' cast lists\n'
        '2. "Storm Club (Earth-1)": team, in 12 comics\' cast lists\n'
        '3. "Storm Tales Vol 1 1": comic'
    )


def test_a_search_asks_for_a_limited_number_of_pages() -> None:
    hits = [PageHit(f"Page {n}", Category.COMICS, 0) for n in range(SEARCH_LIMIT + 5)]
    lookup = FakeLookup(hits)

    result = search_pages(lookup, "page")

    assert lookup.limits == [SEARCH_LIMIT]
    assert len(result.text.splitlines()) == SEARCH_LIMIT


def test_a_search_is_not_a_source() -> None:
    hits = [PageHit("Ann Doe (Earth-1)", Category.CHARACTERS, 3)]

    assert search_pages(FakeLookup(hits), "ann").sources == ()


def test_a_search_with_no_hits_says_so() -> None:
    result = search_pages(FakeLookup(), "nobody")

    assert result.text == 'No pages match "nobody".'
    assert result.sources == ()


def test_a_character_reads_as_its_filled_fields_in_order() -> None:
    ann = character(
        name="Ann Doe",
        base_of_operations="Storm Tower",
        powers="Weather control",
        categories=("Flyers",),
    )

    result = read_page(FakeLookup(records=[ann]), ann.title)

    assert result.text == (
        "Ann Doe (Earth-1) (character)\n"
        "name: Ann Doe\n"
        "base of operations: Storm Tower\n"
        "powers: Weather control"
    )
    assert result.sources == (
        Source(ann.title, "https://wiki.example/Ann_Doe_(Earth-1)"),
    )


def test_a_tuple_field_is_joined_with_commas() -> None:
    comic = blank(
        Comic,
        pageid=2,
        title="Storm Tales Vol 1 1",
        revid=1,
        events=("Big Storm", "Calm"),
    )

    result = read_page(FakeLookup(records=[comic]), comic.title)

    assert "events: Big Storm, Calm" in result.text


def test_a_long_field_is_cut() -> None:
    ann = character(name="Ann Doe", history="x" * (FIELD_LIMIT + 1))

    result = read_page(FakeLookup(records=[ann]), ann.title)

    assert f"history: {'x' * FIELD_LIMIT} [cut]" in result.text


def test_a_long_page_is_cut() -> None:
    # Each story is under the field limit, but together they pass the page limit.
    stories = tuple(
        blank(Story, number=n, credits=blank(Credits), synopsis="s" * FIELD_LIMIT)
        for n in range(1, 12)
    )
    comic = blank(
        Comic, pageid=2, title="Storm Tales Vol 1 1", revid=1, stories=stories
    )

    result = read_page(FakeLookup(records=[comic]), comic.title)

    assert len(result.text) == PAGE_LIMIT + len(" [cut]")
    assert result.text.endswith(" [cut]")


def test_a_matched_character_adds_a_comic_vine_block_and_source() -> None:
    ann = character(name="Ann Doe")
    died = (
        ComicVineIssue("Storm Tales", "9", "1990-05-01"),
        ComicVineIssue("Storm Tales", "10", None),
    )
    matched = vine(
        detail(
            issues=(ComicVineIssue("Storm Tales", "1", "1990-01-01"),),
            deck="Controls the weather.",
            powers=("Flight", "Wind"),
            died_in=died,
        )
    )

    result = read_page(FakeLookup(records=[ann], comicvine=matched), ann.title)

    assert result.text.split("\n\n")[1] == (
        "Comic Vine:\n"
        "name: Weather Witch\n"
        "real name: Ann Doe\n"
        "appearances: 321\n"
        "deck: Controls the weather.\n"
        "powers: Flight, Wind\n"
        "died in: Storm Tales #9 (1990-05-01), Storm Tales #10"
    )
    assert result.sources == (
        Source(ann.title, "https://wiki.example/Ann_Doe_(Earth-1)"),
        Source("Comic Vine: Weather Witch", "https://vine.example/5"),
    )


def test_a_cut_page_still_shows_its_comic_vine_block() -> None:
    # Nine full fields pass the page limit on their own.
    names = (
        "history powers notes abilities weaknesses trivia equipment weapons origin"
    ).split()
    ann = character(name="Ann Doe", **{name: "x" * FIELD_LIMIT for name in names})
    matched = vine(detail(issues=(), deck="Controls the weather."))

    result = read_page(FakeLookup(records=[ann], comicvine=matched), ann.title)

    assert " [cut]\n\nComic Vine:" in result.text
    assert result.text.endswith("deck: Controls the weather.")


def test_a_character_without_a_match_cites_only_its_page() -> None:
    ann = character(name="Ann Doe")

    result = read_page(FakeLookup(records=[ann]), ann.title)

    assert "Comic Vine" not in result.text
    assert len(result.sources) == 1


def test_a_comic_reads_its_stories_with_credits_and_cast() -> None:
    credits = blank(Credits, writers=("Wes Writer",), adapted_from=("A Novel",))
    story = blank(
        Story,
        number=1,
        title="Rain Check",
        credits=credits,
        appearing="Ann Doe and Bob Roe",
        synopsis="Rain falls.",
    )
    comic = blank(
        Comic,
        pageid=2,
        title="Storm Tales Vol 1 1",
        revid=1,
        year="1990",
        stories=(story,),
    )

    result = read_page(FakeLookup(records=[comic]), comic.title)

    assert result.text == (
        "Storm Tales Vol 1 1 (comic)\n"
        "year: 1990\n\n"
        "Story 1: Rain Check\n"
        "writers: Wes Writer\n"
        "adapted from: A Novel\n"
        "appearing: Ann Doe and Bob Roe\n"
        "synopsis: Rain falls."
    )


def test_a_team_reads_like_a_character() -> None:
    team = blank(
        Team,
        pageid=3,
        title="Storm Club (Earth-1)",
        revid=1,
        name="Storm Club",
        leaders="Ann Doe",
    )

    result = read_page(FakeLookup(records=[team], comicvine=vine()), team.title)

    assert result.text == (
        "Storm Club (Earth-1) (team)\nname: Storm Club\nleaders: Ann Doe"
    )
    assert len(result.sources) == 1


def test_an_unknown_title_says_to_search() -> None:
    result = read_page(FakeLookup(), "Nobody")

    assert result.text == 'No page is titled "Nobody". Search for it first.'
    assert result.sources == ()
