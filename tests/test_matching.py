from collections.abc import Iterable, Iterator
from dataclasses import fields
from typing import TYPE_CHECKING, Any, get_origin

import pytest

from cerebro.application.matching import MatchReport, match_characters, match_comicvine
from cerebro.domain.comicvine import (
    CharacterMatch,
    ComicVineCharacter,
    ComicVineDetail,
    ComicVineIssue,
)
from cerebro.domain.records import Character, Comic, Credits, Link, Story
from cerebro.ports.comicvine import ComicVineSource, MatchStore
from cerebro.ports.records import RecordReader

if TYPE_CHECKING:
    from _typeshed import DataclassInstance


def blank[T: DataclassInstance](cls: type[T], **values: Any) -> T:
    """A record with only `values` filled: None for text, () for lists."""
    empty = {
        field.name: () if get_origin(field.type) is tuple else None
        for field in fields(cls)
    }
    return cls(**(empty | values))


def page(pageid: int, title: str, name: str, **values: Any) -> Character:
    return blank(Character, pageid=pageid, title=title, revid=1, name=name, **values)


def comic(
    title: str, year: str, cast: Iterable[str], mentioned: Iterable[str] = ()
) -> Comic:
    """A comic whose one story has this cast and names `mentioned` in its synopsis."""
    links = (
        *(Link("appearing", title, title) for title in cast),
        *(Link("synopsis", title, title) for title in mentioned),
    )
    story = blank(Story, number=1, credits=blank(Credits), links=links)
    # Matching reads a comic's title, year and cast, not its page id.
    return blank(Comic, pageid=0, title=title, revid=1, year=year, stories=(story,))


def issues_of(casts: dict[str, list[int]]) -> list[Comic]:
    """Strange Tales comics from 1990, with the issues each page appears in."""
    numbers = sorted({n for issues in casts.values() for n in issues})
    return [
        comic(
            f"Strange Tales Vol 1 {n}",
            "1990",
            [title for title, issues in casts.items() if n in issues],
        )
        for n in numbers
    ]


def issue(number: int, cover_date: str | None = "1990-01-01") -> ComicVineIssue:
    return ComicVineIssue("Strange Tales", str(number), cover_date)


def comicvine(
    name: str,
    real_name: str | None,
    issues: tuple[ComicVineIssue, ...] | None,
    *,
    cvid: int = 1,
) -> ComicVineCharacter:
    detail = None if issues is None else ComicVineDetail(issues)
    return ComicVineCharacter(cvid, name, real_name, (), 10, detail)


def matched(
    pages: list[Character], comics: list[Comic], character: ComicVineCharacter
) -> int | None:
    """The page id the character matches, if any."""
    matches = match_characters(pages, comics, [character])
    return matches[0].pageid if matches else None


EARTH_616 = page(1, "Peter Parker (Earth-616)", "Peter Parker")
EARTH_1610 = page(2, "Peter Parker (Earth-1610)", "Peter Parker")
SPIDER_MAN = "Spider-Man", "Peter Parker"


def test_the_version_in_the_characters_issues_is_the_match() -> None:
    comics = issues_of({EARTH_616.title: [1, 2, 3], EARTH_1610.title: [4, 5]})
    character = comicvine(*SPIDER_MAN, (issue(1), issue(2)))

    assert matched([EARTH_616, EARTH_1610], comics, character) == 1


def test_a_co_star_without_a_shared_name_is_no_candidate() -> None:
    witch = page(1, "Ann Witch (Earth-616)", "Ann Witch")
    henchman = page(2, "Rootar (Earth-616)", "Rootar")
    # The henchman is in every issue; the witch misses one.
    comics = issues_of({witch.title: [1, 2], henchman.title: [1, 2, 3]})
    character = comicvine("Weather Witch", None, (issue(1), issue(2), issue(3)))

    assert matched([witch, henchman], comics, character) == 1


def test_overlap_beats_a_busier_page_in_the_same_issues() -> None:
    # Both share only the word "witch", and both are in issues 1 and 2.
    quiet = page(1, "Ann Witch (Earth-616)", "Ann Witch")
    busy = page(2, "Busy Witch (Earth-616)", "Busy Witch")
    # Busy is also in comics that aren't numbered issues, which still count.
    annuals = [comic(f"Witch Annual {n}", "1990", [busy.title]) for n in range(4)]
    comics = issues_of({quiet.title: [1, 2], busy.title: [1, 2]}) + annuals
    character = comicvine("Weather Witch", None, (issue(1), issue(2)))

    assert matched([quiet, busy], comics, character) == 1


def test_only_the_cast_list_counts_as_an_appearance() -> None:
    comics = [
        comic("Strange Tales Vol 1 1", "1990", [EARTH_616.title], [EARTH_1610.title]),
        comic("Strange Tales Vol 1 2", "1990", [], [EARTH_1610.title]),
    ]
    character = comicvine(*SPIDER_MAN, (issue(1), issue(2)))

    assert matched([EARTH_616, EARTH_1610], comics, character) == 1


@pytest.mark.parametrize(
    "names",
    [
        {"name": "Weather Witch"},
        {"current_alias": "Weather Witch"},
        {"title": "Weather Witch (Earth-616)"},
        {"aliases": "Stormy\nWeather Witch"},
        {"aliases": "Stormy, Weather Witch"},
        {"aliases": "Stormy; Weather Witch"},
    ],
)
def test_a_whole_name_anywhere_on_the_page_beats_a_shared_word(
    names: dict[str, str],
) -> None:
    witch = page(1, **({"title": "Ann Doe (Earth-616)", "name": "Ann Doe"} | names))
    rival = page(2, "Bob Witch (Earth-616)", "Bob Witch")
    comics = issues_of({witch.title: [1], rival.title: [1]})
    character = comicvine("Weather Witch", None, (issue(1),))

    assert matched([witch, rival], comics, character) == 1


@pytest.mark.parametrize(
    "character",
    [
        ComicVineCharacter(1, "Ann Doe", None, (), 10, ComicVineDetail((issue(1),))),
        ComicVineCharacter(
            1, "Weather Witch", "Ann Doe", (), 10, ComicVineDetail((issue(1),))
        ),
        ComicVineCharacter(
            1,
            "Weather Witch",
            None,
            ("Stormy", "Ann Doe"),
            10,
            ComicVineDetail((issue(1),)),
        ),
    ],
)
def test_every_comic_vine_name_counts(character: ComicVineCharacter) -> None:
    ann = page(1, "Ann Doe (Earth-616)", "Ann Doe")
    rival = page(2, "Bob Doe (Earth-616)", "Bob Doe")
    comics = issues_of({ann.title: [1], rival.title: [1]})

    assert matched([ann, rival], comics, character) == 1


def test_pages_the_issues_and_names_cant_tell_apart_match_nothing() -> None:
    comics = issues_of({EARTH_616.title: [1], EARTH_1610.title: [1]})
    character = comicvine(*SPIDER_MAN, (issue(1),))

    assert matched([EARTH_616, EARTH_1610], comics, character) is None


def test_an_issue_needs_the_same_cover_year() -> None:
    comics = [
        comic("Strange Tales Vol 2 1", "2010", [EARTH_1610.title]),
        comic("Strange Tales Vol 1 1", "1990", [EARTH_616.title]),
    ]
    # An issue with no cover date can't be placed, so it counts for nothing.
    character = comicvine(*SPIDER_MAN, (issue(1), issue(1, cover_date=None)))

    assert matched([EARTH_616, EARTH_1610], comics, character) == 1


def test_a_leading_the_in_a_comic_vine_series_is_ignored() -> None:
    comics = issues_of({EARTH_616.title: [1]})
    the_series = ComicVineIssue("The Strange Tales", "1", "1990-01-01")
    character = comicvine(*SPIDER_MAN, (the_series,))

    assert matched([EARTH_616], comics, character) == 1


def test_an_issue_two_comics_answer_to_counts_for_neither() -> None:
    # Fandom files a UK reprint under the same series name, parenthetical aside.
    comics = [
        comic("Strange Tales Vol 1 1", "1990", [EARTH_616.title]),
        comic("Strange Tales Vol 1 2", "1990", [EARTH_1610.title]),
        comic("Strange Tales (UK) Vol 1 2", "1990", [EARTH_1610.title]),
        comic("Strange Tales Vol 1 3", "1990", [EARTH_1610.title]),
        comic("Strange Tales (UK) Vol 1 3", "1990", [EARTH_1610.title]),
    ]
    character = comicvine(*SPIDER_MAN, (issue(1), issue(2), issue(3)))

    assert matched([EARTH_616, EARTH_1610], comics, character) == 1


def test_a_quoted_nickname_counts_as_a_whole_name() -> None:
    kitty = page(1, "Katherine Pryde (Earth-616)", 'Katherine Anne "Kitty" Pryde')
    kate = page(2, "Katherine Pryde (Earth-58163)", "Kate Pryde")
    comics = issues_of({kitty.title: [1, 2], kate.title: [1, 2]})
    character = comicvine("Kitty Pryde", None, (issue(1), issue(2)))

    assert matched([kitty, kate], comics, character) == 1


def test_a_character_without_an_issue_list_is_not_matched() -> None:
    comics = issues_of({EARTH_616.title: [1]})
    character = comicvine(*SPIDER_MAN, None)

    assert matched([EARTH_616], comics, character) is None


class FakeRecords(RecordReader):
    def __init__(self, pages: list[Character], comics: list[Comic]) -> None:
        self.pages = pages
        self.issues = comics

    def characters(self) -> Iterator[Character]:
        return iter(self.pages)

    def comics(self) -> Iterator[Comic]:
        return iter(self.issues)


class FakeComicVine(ComicVineSource):
    def __init__(self, characters: list[ComicVineCharacter]) -> None:
        self.listed = characters

    def characters(self) -> Iterator[ComicVineCharacter]:
        return iter(self.listed)


class FakeMatchStore(MatchStore):
    def __init__(self) -> None:
        self.matches: list[CharacterMatch] = []

    def replace_matches(self, matches: Iterable[CharacterMatch]) -> None:
        self.matches = list(matches)


def test_matches_are_stored_and_counted() -> None:
    records = FakeRecords([EARTH_616], issues_of({EARTH_616.title: [1, 2]}))
    # Two Comic Vine entries for one Fandom page, and one without an issue list.
    listed = [
        comicvine(*SPIDER_MAN, (issue(1),), cvid=10),
        comicvine("Peter Parker", None, (issue(2),), cvid=20),
        comicvine("Mary Jane", None, None, cvid=30),
    ]
    store = FakeMatchStore()

    report = match_comicvine(records, FakeComicVine(listed), store)

    assert store.matches == [CharacterMatch(1, 10, 0.5), CharacterMatch(1, 20, 0.5)]
    assert report == MatchReport(
        comicvine=3, with_issues=2, matched=2, pages_claimed_twice=1
    )
