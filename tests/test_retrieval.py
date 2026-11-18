"""Fusing searches by reciprocal rank."""

import pytest
from helpers import FakeChunkSearch

from cerebro.application.retrieval import (
    CANDIDATES,
    RANK_OFFSET,
    FusedSearch,
    MainRealityFirst,
)
from cerebro.domain.chunks import Chunk, ChunkHit


def found(*ids: str) -> FakeChunkSearch:
    """A search that finds these chunks, best first, with scores that mean nothing
    to the fusion."""
    chunks = [Chunk(i, 1, 7, 0, "Ann Doe (Earth-1)", "History", "", i) for i in ids]
    return FakeChunkSearch([ChunkHit(c, 99.0 - n) for n, c in enumerate(chunks)])


def ids(hits: list[ChunkHit]) -> list[str]:
    return [hit.chunk.id for hit in hits]


def test_a_chunk_both_searches_rank_well_beats_one_that_only_one_does() -> None:
    fused = FusedSearch([found("a", "b", "c"), found("c", "d", "b")])

    hits = fused.search("storm", limit=10)

    # The offset keeps first place from counting double: b and c, each high in both
    # lists, pass a, which one list has first. With no offset a would beat b.
    assert ids(hits) == ["c", "b", "a", "d"]


def test_a_score_is_the_sum_of_the_reciprocal_ranks() -> None:
    fused = FusedSearch([found("a", "b"), found("b")])

    hits = fused.search("storm", limit=10)

    assert [hit.chunk.id for hit in hits] == ["b", "a"]
    assert hits[0].score == pytest.approx(1 / (RANK_OFFSET + 2) + 1 / (RANK_OFFSET + 1))
    assert hits[1].score == pytest.approx(1 / (RANK_OFFSET + 1))


def test_equal_scores_go_to_the_chunk_found_first() -> None:
    first_then_second = FusedSearch([found("a"), found("b")])
    second_then_first = FusedSearch([found("b"), found("a")])

    assert ids(first_then_second.search("storm", limit=10)) == ["a", "b"]
    assert ids(second_then_first.search("storm", limit=10)) == ["b", "a"]


def test_only_the_top_limit_chunks_are_returned() -> None:
    fused = FusedSearch([found("a", "b", "c"), found("a", "b", "c")])

    assert ids(fused.search("storm", limit=2)) == ["a", "b"]


def test_each_search_is_asked_for_its_candidates_not_the_limit() -> None:
    keyword, meaning = found("a"), found("b")

    FusedSearch([keyword, meaning]).search("storm", limit=5)

    assert keyword.limits == [CANDIDATES]
    assert meaning.limits == [CANDIDATES]


def test_a_search_that_finds_nothing_leaves_the_other_ranking_as_it_was() -> None:
    fused = FusedSearch([found(), found("a", "b")])

    assert ids(fused.search("storm", limit=10)) == ["a", "b"]


# Main reality first


def pages(*titles: str) -> FakeChunkSearch:
    """A search that finds one passage per title, best first."""
    chunks = [
        Chunk(str(n), n, 7, 0, title, "History", "", title)
        for n, title in enumerate(titles)
    ]
    return FakeChunkSearch([ChunkHit(c, 99.0 - n) for n, c in enumerate(chunks)])


def order(search: FakeChunkSearch, query: str = "storm", limit: int = 10) -> list[str]:
    return [hit.chunk.title for hit in MainRealityFirst(search).search(query, limit)]


def test_main_reality_passages_come_before_other_realities() -> None:
    search = pages(
        "Ann (Earth-1610)", "Ann (Earth-616)", "Bob (Mojoverse)", "Bob (Earth-616)"
    )

    assert order(search) == [
        "Ann (Earth-616)",
        "Bob (Earth-616)",
        "Ann (Earth-1610)",
        "Bob (Mojoverse)",
    ]


def test_comic_passages_take_turns_with_main_reality_ones() -> None:
    search = pages(
        "Storm Tales Vol 1 1",
        "Storm Tales Vol 1 2",
        "Storm Tales Vol 1 3",
        "Ann (Earth-616)",
        "Bob (Earth-616)",
    )

    assert order(search) == [
        "Ann (Earth-616)", "Storm Tales Vol 1 1", "Bob (Earth-616)",
        "Storm Tales Vol 1 2", "Storm Tales Vol 1 3",
    ]  # fmt: skip


def test_a_query_that_names_a_reality_keeps_the_ranking() -> None:
    search = pages("Ann (Earth-1610)", "Ann (Earth-616)")

    assert order(search, "Ultimate Ann") == ["Ann (Earth-1610)", "Ann (Earth-616)"]
    assert order(search, "Ann earth-1610") == ["Ann (Earth-1610)", "Ann (Earth-616)"]


def test_the_reordering_draws_on_the_candidates_and_returns_the_limit() -> None:
    search = pages(*(f"Other {n} (Earth-2)" for n in range(30)), "Ann (Earth-616)")

    assert order(search, limit=3) == [
        "Ann (Earth-616)",
        "Other 0 (Earth-2)",
        "Other 1 (Earth-2)",
    ]
    assert search.limits == [CANDIDATES]
