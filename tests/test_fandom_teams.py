import json
from dataclasses import asdict
from pathlib import Path

from cerebro.adapters.fandom_wikitext import parse_team
from cerebro.domain.pages import RawPage
from cerebro.domain.records import Link

REAL_PAGE = Path(__file__).parent / "fixtures" / "fandom" / "livewires.json"

# Every template field a team record reads. OfficialName is left out: it only stands
# in for a missing Name.
WIKI_FIELDS = """
    Name Name2 Title EditorialNames Aliases Leaders CurrentMembers FormerMembers
    Identity Identity2 Affiliation Allies Enemies Origin Status Reality Reality2
    BaseOfOperations PlaceOfFormation PlaceOfDissolution Equipment Weapons
    Transportation Creators First First2 Last Last2 Death Death2 Destruction
    Destruction2 Overview History Notes Trivia
""".split()


def real_page() -> RawPage:
    """Livewires (Earth-616), saved from the crawl. It fills 21 of the fields."""
    return RawPage(**json.loads(REAL_PAGE.read_text(encoding="utf-8")))


def team_page(
    template: str = "Marvel Database:Team Template", **fields: str
) -> RawPage:
    """A page titled X-Men (Earth-616) that calls `template` with the given fields."""
    lines = [f"| {field} = {value}" for field, value in fields.items()]
    wikitext = "\n".join(["{{" + template, *lines, "}}"])
    return RawPage(
        pageid=1, title="X-Men (Earth-616)", revid=1, timestamp="", wikitext=wikitext
    )


def test_reads_every_field_of_a_real_page() -> None:
    raw = real_page()
    record = parse_team(raw)
    assert record is not None

    assert (record.pageid, record.title, record.revid) == (
        raw.pageid,
        raw.title,
        raw.revid,
    )
    assert record.name == "Livewires"
    assert record.leaders == "Stem Cell"
    assert record.former_members == "Homebrew"
    assert record.identity == "Known to Authorities"
    assert record.allies == '"Nick Fury"'
    assert record.origin == "Android"
    assert record.status == "Active"
    assert record.reality == "Earth-616"
    assert record.base_of_operations == "Mobile"
    assert record.equipment == "Disguises"
    assert record.transportation == "Van"
    assert record.creators == "Adam Warren"
    assert record.first_appearance == "Livewires Vol 1 1"

    # Lists and prose are checked for one entry or fact each, so a refreshed page
    # with a new member or reworded text still passes.
    assert (
        record.aliases
        and record.current_members
        and record.enemies
        and record.place_of_formation
        and record.weapons
        and record.history
        and record.notes
        and record.trivia
    )
    assert "Project Livewire" in record.aliases
    assert "Gothic Lolita" in record.current_members
    assert "Deadpool" in record.enemies
    assert "desert" in record.place_of_formation
    assert "Firearms" in record.weapons
    assert "black-ops" in record.history
    assert "Mannites" in record.notes
    assert "robota" in record.trivia

    assert "Artificial Intelligences" in record.categories
    assert Link("leaders", "Stem Cell (Earth-616)", "Stem Cell") in record.links


def test_every_template_field_lands_in_exactly_one_record_field() -> None:
    # Each field holds its own name, so a misspelt, dropped or doubled field shows.
    record = parse_team(team_page(**{field: field for field in WIKI_FIELDS}))
    assert record is not None

    texts = [
        value
        for key, value in asdict(record).items()
        if isinstance(value, str) and key != "title"
    ]
    assert sorted(texts) == sorted(WIKI_FIELDS)


def test_name_comes_from_name_then_official_name_then_the_title() -> None:
    named = parse_team(team_page(Name="X-Men", OfficialName="The X-Men"))
    officially_named = parse_team(team_page(OfficialName="The X-Men"))
    unnamed = parse_team(team_page())

    assert named is not None and officially_named is not None and unnamed is not None
    assert named.name == "X-Men"
    assert officially_named.name == "The X-Men"
    assert unnamed.name == "X-Men"


def test_pages_without_the_team_template_are_skipped() -> None:
    # Two pages filed under Teams on the wiki call another template.
    character = team_page("Marvel Database:Character Template", Name="Storm")

    assert parse_team(character) is None
