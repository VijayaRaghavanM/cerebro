import json
from dataclasses import asdict
from pathlib import Path

from cerebro.adapters.fandom_wikitext import parse_comic
from cerebro.domain.pages import RawPage
from cerebro.domain.records import Comic, Link

REAL_PAGE = (
    Path(__file__).parent / "fixtures" / "fandom" / "marvel_comics_presents_170.json"
)

# Every issue field a comic record reads, and every story field and credit of two
# stories with two people each, named as the wiki numbers them.
ISSUE_FIELDS = """
    ReleaseDate Month Year Editor-in-Chief Pages OriginalPrice Rating ISBN ISSN UPC
    LegacyNumber Canceled PreviousIssue NextIssue Solicit Notes Trivia Accolades
    Event1 Event2 StoryArc1 Storyline1 Tie-in1 Image1_Artist1 Image1_Artist2
""".split()
STORY_FIELDS = [
    f"{field}{story}"
    for story in (1, 2)
    for field in "StoryTitle Synopsis Appearing ReprintOf ReprintOfStory".split()
]
CREDITS = [
    f"{job}{story}_{person}"
    for story in (1, 2)
    for job in "Writer Penciler Inker Colorist Letterer Editor AdaptedFrom".split()
    for person in (1, 2)
]
TRANSLATORS = ["Translator1_1", "TranslatorLetterer2_1"]


def real_page() -> RawPage:
    """Marvel Comics Presents Vol 1 170, saved from the crawl: four stories."""
    return RawPage(**json.loads(REAL_PAGE.read_text(encoding="utf-8")))


def comic_page(
    template: str = "Marvel Database:Comic Template", **fields: str
) -> RawPage:
    """A page titled X-Men Vol 1 1 that calls `template` with the given fields."""
    lines = [f"| {field} = {value}" for field, value in fields.items()]
    wikitext = "\n".join(["{{" + template, *lines, "}}"])
    return RawPage(
        pageid=1, title="X-Men Vol 1 1", revid=1, timestamp="", wikitext=wikitext
    )


def texts_of(record: Comic) -> list[str]:
    """Every text and list entry in the record, its stories' included."""
    issue = asdict(record)
    stories = issue.pop("stories")
    for key in ("pageid", "title", "revid", "categories", "links"):
        del issue[key]

    values = list(issue.values())
    for story in stories:
        values += [*story.pop("credits").values()]
        values += [
            value for key, value in story.items() if key not in ("number", "links")
        ]

    texts = []
    for value in values:
        texts += [value] if isinstance(value, str) else list(value or ())
    return texts


def test_reads_every_field_of_a_real_page() -> None:
    raw = real_page()
    record = parse_comic(raw)
    assert record is not None

    assert (record.pageid, record.title, record.revid) == (
        raw.pageid,
        raw.title,
        raw.revid,
    )
    assert record.release_date == "October 25, 1994"
    assert (record.month, record.year) == ("Late December", "1994")
    assert record.editor_in_chief == "Tom DeFalco"
    assert record.cover_artists == ("John Czop", "Tim Dzon", "Patrick Rolo")
    assert record.events == ("Hands of the Mandarin",)
    assert record.notes and "Iron Man Vol 1 307" in record.notes
    assert Link("notes", "Iron Man Vol 1 307", "Iron Man Vol 1 307") in record.links

    assert [story.number for story in record.stories] == [1, 2, 3, 4]
    first, second = record.stories[0], record.stories[1]
    assert first.title == "In the Hands of the Mandarin (Part 2)- Inner Demons"
    assert first.credits.writers == ("Len Kaminski", "Scott Benson")
    assert first.credits.pencilers == ("Patrick Rolo",)
    assert first.synopsis and "Heart of Darkness" in first.synopsis
    assert first.appearing and "Iron Man (Mentioned)" in first.appearing
    assert second.appearing and "Q'Wake" in second.appearing
    assert Link("appearing", "Suzi Endo (Earth-616)", "Suzi Endo") in second.links


def test_every_field_lands_in_exactly_one_place() -> None:
    # Each field holds its own name, so a misspelt, dropped or doubled field shows.
    fields = [*ISSUE_FIELDS, *STORY_FIELDS, *CREDITS, *TRANSLATORS]
    record = parse_comic(comic_page(**{field: field for field in fields}))
    assert record is not None

    expected = [*ISSUE_FIELDS, *STORY_FIELDS, *CREDITS]
    expected += [f"{field} (translation)" for field in TRANSLATORS]
    assert sorted(texts_of(record)) == sorted(expected)

    # A translator is listed with the credit translated.
    first, second = record.stories
    assert first.credits.writers[-1] == "Translator1_1 (translation)"
    assert second.credits.letterers[-1] == "TranslatorLetterer2_1 (translation)"


def test_cover_artists_come_cover_by_cover_once_each() -> None:
    page = comic_page(
        Image2_Artist1="Wein",
        Image1_Artist2="Austin",
        Image1_Artist1="Byrne",
        Image2_Artist2="Byrne",
    )
    record = parse_comic(page)

    assert record is not None
    assert record.cover_artists == ("Byrne", "Austin", "Wein")


def test_a_story_after_a_gap_counts_and_an_empty_cast_list_does_not() -> None:
    # The template fills a new story's cast list with section labels and nothing else.
    labels_only = "\n'''Featured Characters:'''\n* \n'''Locations:'''\n* <br/>"
    page = comic_page(StoryTitle1="First", Appearing2=labels_only, StoryTitle3="Third")
    record = parse_comic(page)

    assert record is not None
    assert [story.number for story in record.stories] == [1, 3]


def test_pages_without_the_comic_template_are_skipped() -> None:
    # Handbook and sourcebook pages are filed under Comics on the wiki.
    handbook = comic_page("Marvel Database:Handbook Template", Year="1983")

    assert parse_comic(handbook) is None
