import json
from dataclasses import replace
from pathlib import Path

import pytest

from cerebro.adapters.fandom_wikitext import parse_character, parse_comic, parse_team
from cerebro.adapters.sqlite_records import SqliteRecordStore
from cerebro.domain.comicvine import (
    CharacterMatch,
    ComicVineCharacter,
    ComicVineDetail,
    ComicVineIssue,
)
from cerebro.domain.pages import Category, RawPage
from cerebro.domain.records import Character, Comic, Link, PageHit, Team
from cerebro.ports.records import RecordsMissing

FIXTURES = Path(__file__).parent / "fixtures" / "fandom"


def fixture(name: str) -> RawPage:
    return RawPage(**json.loads((FIXTURES / name).read_text(encoding="utf-8")))


def character() -> Character:
    record = parse_character(fixture("daniel_berkhart.json"))
    assert record is not None
    return record


def team() -> Team:
    record = parse_team(fixture("livewires.json"))
    assert record is not None
    return record


def comic() -> Comic:
    record = parse_comic(fixture("marvel_comics_presents_170.json"))
    assert record is not None
    return record


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


def cast(issue: Comic, *titles: str) -> Comic:
    """The comic with each of its stories listing the pages in its cast."""
    links = tuple(Link("appearing", title, title) for title in titles)
    return replace(issue, stories=tuple(replace(s, links=links) for s in issue.stories))


def stored(tmp_path: Path) -> SqliteRecordStore:
    """A store with one character, one team and one comic, no cast links."""
    store = SqliteRecordStore(tmp_path / "records.sqlite")
    store.replace(Category.CHARACTERS, [character()])
    store.replace(Category.TEAMS, [team()])
    store.replace(Category.COMICS, [comic()])
    return store


def titles(hits: list[PageHit]) -> list[str]:
    return [hit.title for hit in hits]


# find


def test_a_character_is_found_by_part_of_its_name(tmp_path: Path) -> None:
    store = stored(tmp_path)

    hits = store.find("berkh", 10)

    assert hits == [PageHit(character().title, Category.CHARACTERS, 0)]


def test_words_match_in_any_order_and_across_names(tmp_path: Path) -> None:
    store = stored(tmp_path)

    # "mysterio" is the current alias, "daniel" is in the name.
    assert titles(store.find("berkhart daniel", 10)) == [character().title]
    assert titles(store.find("mysterio daniel", 10)) == [character().title]
    # Every word has to match: nothing is called Daniel Livewires.
    assert store.find("daniel livewires", 10) == []


def test_a_team_is_found_by_an_alias(tmp_path: Path) -> None:
    store = stored(tmp_path)

    hits = store.find("real aim", 10)

    assert hits == [PageHit(team().title, Category.TEAMS, 0)]


def test_a_comic_is_found_by_words_of_its_title(tmp_path: Path) -> None:
    store = stored(tmp_path)

    hits = store.find("marvel presents 170", 10)

    assert hits == [PageHit(comic().title, Category.COMICS, 0)]


def test_punctuation_around_a_word_is_ignored(tmp_path: Path) -> None:
    store = stored(tmp_path)

    # How people write an issue number; the title says "Vol 1 170".
    hits = store.find('"Marvel Comics Presents #170"?', 10)

    assert hits == [PageHit(comic().title, Category.COMICS, 0)]


def test_matching_ignores_case(tmp_path: Path) -> None:
    store = stored(tmp_path)

    assert titles(store.find("DANIEL berkhart", 10)) == [character().title]


def test_a_percent_sign_matches_itself(tmp_path: Path) -> None:
    store = stored(tmp_path)

    assert store.find("%", 10) == []
    assert store.find("daniel%", 10) == []


def test_a_search_with_no_words_finds_nothing(tmp_path: Path) -> None:
    store = stored(tmp_path)

    assert store.find("  ", 10) == []


def test_hits_are_ranked_by_appearances_with_comics_last(tmp_path: Path) -> None:
    store = SqliteRecordStore(tmp_path / "records.sqlite")
    berkhart = character()
    # A second Berkhart that no comic lists, and one that two comics list.
    unseen = replace(berkhart, pageid=1, title="Aaron Berkhart (Earth-616)")
    issue = comic()
    # Berkhart is in two stories of one comic: that is one appearance, not two.
    first = cast(issue, berkhart.title)
    second = replace(cast(issue, berkhart.title), pageid=2, title="Berkhart Vol 1 2")
    store.replace(Category.CHARACTERS, [unseen, berkhart])
    store.replace(Category.COMICS, [first, second])

    hits = store.find("berkhart", 10)

    assert hits == [
        PageHit(berkhart.title, Category.CHARACTERS, 2),
        PageHit(unseen.title, Category.CHARACTERS, 0),
        PageHit(second.title, Category.COMICS, 0),
    ]


def test_find_returns_at_most_the_limit_of_each_kind(tmp_path: Path) -> None:
    store = SqliteRecordStore(tmp_path / "records.sqlite")
    berkhart = character()
    others = [
        replace(berkhart, pageid=n, title=f"Berkhart {n} (Earth-616)")
        for n in range(1, 4)
    ]
    comics = [
        replace(comic(), pageid=n, title=f"Berkhart Vol 1 {n}") for n in (1, 2, 3)
    ]
    store.replace(Category.CHARACTERS, others)
    store.replace(Category.COMICS, comics)

    hits = store.find("berkhart", 2)

    # Characters filling the limit don't crowd out the comics.
    assert [hit.category for hit in hits] == [
        Category.CHARACTERS,
        Category.CHARACTERS,
        Category.COMICS,
        Category.COMICS,
    ]


def test_the_shortest_comic_title_comes_first(tmp_path: Path) -> None:
    store = SqliteRecordStore(tmp_path / "records.sqlite")
    titles = ["Berkhart Annual Vol 1 1", "Berkhart Vol 1 1", "Berkhart Vol 2 1"]
    comics = [replace(comic(), pageid=n, title=t) for n, t in enumerate(titles)]
    store.replace(Category.CHARACTERS, [character()])
    store.replace(Category.COMICS, comics)

    hits = store.find("berkhart vol 1", 10)

    assert [hit.title for hit in hits if hit.category is Category.COMICS] == [
        "Berkhart Vol 1 1",
        "Berkhart Vol 2 1",
        "Berkhart Annual Vol 1 1",
    ]


def test_a_comic_is_found_by_its_year(tmp_path: Path) -> None:
    store = stored(tmp_path)

    hits = store.find(f"marvel comics presents ({comic().year})", 10)

    assert hits == [PageHit(comic().title, Category.COMICS, 0)]


def test_find_without_stored_records_says_so(tmp_path: Path) -> None:
    store = SqliteRecordStore(tmp_path / "records.sqlite")

    with pytest.raises(RecordsMissing):
        store.find("berkhart", 10)


# record


def test_each_kind_of_record_is_read_back_by_title(tmp_path: Path) -> None:
    store = stored(tmp_path)

    assert store.record(character().title) == character()
    assert store.record(team().title) == team()
    assert store.record(comic().title) == comic()


def test_an_unknown_title_has_no_record(tmp_path: Path) -> None:
    store = stored(tmp_path)

    assert store.record("Nobody (Earth-616)") is None


def test_a_record_with_only_characters_stored_is_still_found(tmp_path: Path) -> None:
    store = SqliteRecordStore(tmp_path / "records.sqlite")
    store.replace(Category.CHARACTERS, [character()])

    assert store.record(character().title) == character()
    assert store.record(comic().title) is None


def test_a_title_in_two_tables_gives_the_character_first(tmp_path: Path) -> None:
    store = stored(tmp_path)
    same_title = replace(team(), title=character().title)
    store.replace(Category.TEAMS, [same_title])

    assert store.record(character().title) == character()


def test_record_without_stored_records_says_so(tmp_path: Path) -> None:
    store = SqliteRecordStore(tmp_path / "records.sqlite")

    with pytest.raises(RecordsMissing):
        store.record(character().title)


# comicvine


def matched(tmp_path: Path, *matches: CharacterMatch) -> SqliteRecordStore:
    store = SqliteRecordStore(tmp_path / "records.sqlite")
    store.replace_comicvine(comicvine_characters())
    store.replace_matches(matches)
    return store


def test_the_matched_comic_vine_character_is_read_back(tmp_path: Path) -> None:
    witch, _ = comicvine_characters()
    store = matched(tmp_path, CharacterMatch(10, witch.id, 0.5))

    assert store.comicvine(10) == witch
    assert witch.detail is not None
    assert witch.detail.issues and witch.detail.died_in


def test_a_character_without_detail_comes_back_without_it(tmp_path: Path) -> None:
    _, nobody = comicvine_characters()
    store = matched(tmp_path, CharacterMatch(10, nobody.id, 0.5))

    assert store.comicvine(10) == nobody


def test_two_matches_give_the_higher_overlap(tmp_path: Path) -> None:
    witch, nobody = comicvine_characters()
    store = matched(
        tmp_path,
        CharacterMatch(10, witch.id, 0.25),
        CharacterMatch(10, nobody.id, 0.75),
    )

    assert store.comicvine(10) == nobody


def test_an_unmatched_page_has_no_comic_vine_character(tmp_path: Path) -> None:
    witch, _ = comicvine_characters()
    store = matched(tmp_path, CharacterMatch(10, witch.id, 0.5))

    assert store.comicvine(11) is None


def test_without_comic_vine_data_there_is_no_character(tmp_path: Path) -> None:
    assert stored(tmp_path).comicvine(character().pageid) is None


# url


def test_a_url_has_underscores_and_keeps_punctuation_readable(tmp_path: Path) -> None:
    store = SqliteRecordStore(tmp_path / "records.sqlite")

    url = store.url("Jack O'Lantern (Daniel Berkhart) (Earth-616)")

    assert url == (
        "https://marvel.fandom.com/wiki/Jack_O'Lantern_(Daniel_Berkhart)_(Earth-616)"
    )


def test_a_url_encodes_what_is_not_safe(tmp_path: Path) -> None:
    store = SqliteRecordStore(tmp_path / "records.sqlite")

    assert store.url("Who? #1") == "https://marvel.fandom.com/wiki/Who%3F_%231"
