import re

from helpers import character, real_character

from cerebro.application.chunking import (
    CHARS_PER_TOKEN,
    PROSE_FIELDS,
    TARGET_TOKENS,
    chunk_character,
)

TARGET_CHARS = TARGET_TOKENS * CHARS_PER_TOKEN


def prose(length: int) -> str:
    """One sentence of exactly this many characters."""
    return "B" + "a" * (length - 2) + "."


def sections(**values: str) -> list[tuple[str, str]]:
    return [
        (chunk.section, chunk.text) for chunk in chunk_character(character(**values))
    ]


def test_chunks_are_numbered_from_zero_in_page_order() -> None:
    chunks = chunk_character(character(name="Ann", overview="Hello.", trivia="World."))

    assert [chunk.number for chunk in chunks] == [0, 1, 2]
    assert [chunk.id for chunk in chunks] == ["1:7:0", "1:7:1", "1:7:2"]
    assert {(chunk.pageid, chunk.revid) for chunk in chunks} == {(1, 7)}
    assert {chunk.title for chunk in chunks} == {"Ann Doe (Earth-1)"}


def test_profile_lists_the_non_empty_facts_only() -> None:
    result = sections(
        name="Ann Doe",
        name_note="(Alias)",
        base_of_operations="Atlantis",
        eyes="",
        history="Prose.",
    )

    assert result[0] == ("Profile", "name: Ann Doe\nbase of operations: Atlantis")


def test_a_page_without_facts_has_no_profile() -> None:
    assert sections(overview="Hello.") == [("Overview", "Hello.")]


def test_prose_fields_come_in_page_order() -> None:
    values = {field: f"Text of {field}." for field in reversed(PROSE_FIELDS)}

    names = [name for name, _ in sections(**values)]

    assert names == [field.capitalize() for field in PROSE_FIELDS]


def test_headings_start_sections_named_after_their_field() -> None:
    history = "Intro.\n\n### Early Life\n\nBorn.\n\n## Later\nDied."

    assert sections(history=history) == [
        ("History", "Intro."),
        ("History > Early Life", "Born."),
        ("History > Later", "Died."),
    ]


def test_a_field_starting_with_a_heading_has_no_section_of_its_own() -> None:
    assert sections(history="# Start\n\nText.") == [("History > Start", "Text.")]


def test_short_paragraphs_share_a_chunk_until_one_would_overflow() -> None:
    paragraphs = [prose(800), prose(800), prose(800)]

    result = sections(overview="\n\n".join(paragraphs))

    assert [text for _, text in result] == [
        "\n\n".join(paragraphs[:2]),
        paragraphs[2],
    ]


def test_sections_never_share_a_chunk() -> None:
    result = sections(history="One.\n\n### Part\n\nTwo.", trivia="Three.")

    assert [text for _, text in result] == ["One.", "Two.", "Three."]


def test_a_long_paragraph_is_split_at_sentence_ends() -> None:
    sentences = [prose(700), prose(700), prose(700)]

    result = sections(overview=" ".join(sentences))

    assert [text for _, text in result] == [" ".join(sentences[:2]), sentences[2]]


def test_a_sentence_over_the_target_stays_whole() -> None:
    sentence = prose(TARGET_CHARS + 500)

    result = sections(overview=f"{sentence} {prose(50)}")

    assert [text for _, text in result] == [sentence, prose(50)]


def test_real_page_chunks_fit_and_keep_every_paragraph() -> None:
    record = real_character()
    chunks = chunk_character(record)

    for chunk in chunks:
        fits = len(chunk.text) / CHARS_PER_TOKEN <= TARGET_TOKENS
        one_sentence = not re.search(r"[.!?] +[A-Z\"']", chunk.text)
        assert fits or one_sentence

    def squash(text: str) -> str:
        return " ".join(text.split())

    kept = squash(" ".join(c.text for c in chunks if c.section == "History"))
    assert record.history
    for paragraph in record.history.split("\n\n"):
        if paragraph.strip():
            assert squash(paragraph) in kept
