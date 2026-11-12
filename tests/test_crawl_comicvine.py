from collections.abc import Sequence
from pathlib import Path

from cerebro.adapters.comicvine_dump import ComicVineDump
from cerebro.application.crawl_comicvine import crawl_comicvine
from cerebro.domain.comicvine import DownloadPart, RawRecord
from cerebro.ports.comicvine import ComicVineAPI

# Made-up appearance counts. Characters 2 and 3 tie for the most.
APPEARANCES = {1: 10, 2: 50, 3: 50, 4: 5, 5: 30}

# Made-up issue lists, with issue 101 shared by characters 2 and 3.
ISSUES = {2: [100, 101], 3: [101, 102], 5: [103]}


class FakeComicVine(ComicVineAPI):
    """Comic Vine with five characters; it records each call it gets."""

    batch_limit = 2

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[int, ...]]] = []

    def marvel_characters(self) -> list[RawRecord]:
        self.calls.append(("list", ()))
        return [{"id": i, "name": f"Hero {i}"} for i in APPEARANCES]

    def character_summaries(self, ids: Sequence[int]) -> list[RawRecord]:
        self.calls.append(("summaries", tuple(ids)))
        return [
            {"id": i, "name": f"Hero {i}", "count_of_issue_appearances": APPEARANCES[i]}
            for i in ids
        ]

    def character_detail(self, character_id: int) -> RawRecord:
        self.calls.append(("detail", (character_id,)))
        return {"id": character_id, "issue_ids": ISSUES.get(character_id, [])}

    def issues(self, ids: Sequence[int]) -> list[RawRecord]:
        self.calls.append(("issues", tuple(ids)))
        return [{"id": i, "issue_number": "1"} for i in ids]

    def steps(self) -> list[str]:
        return [step for step, _ in self.calls]

    def asked_for(self, step: str) -> list[int]:
        return [i for name, ids in self.calls if name == step for i in ids]


def test_first_run_does_the_four_steps_in_order(tmp_path: Path) -> None:
    api = FakeComicVine()
    store = ComicVineDump(tmp_path)

    report = crawl_comicvine(api, store, top=2)

    assert api.steps() == [
        "list",
        *["summaries"] * 3,  # five characters, two to a call
        *["detail"] * 2,
        *["issues"] * 2,  # issues 100 to 102, two to a call
    ]
    assert store.saved_ids(DownloadPart.CHARACTERS) == {1, 2, 3, 4, 5}
    assert store.saved_ids(DownloadPart.DETAILS) == {2, 3}
    assert store.saved_ids(DownloadPart.ISSUES) == {100, 101, 102}
    assert (report.listed, report.summaries, report.details, report.issues) == (
        5,
        5,
        2,
        3,
    )
    assert report.calls == len(api.calls)
    assert not report.stopped


def test_rerun_makes_no_calls(tmp_path: Path) -> None:
    store = ComicVineDump(tmp_path)
    crawl_comicvine(FakeComicVine(), store, top=2)
    api = FakeComicVine()

    report = crawl_comicvine(api, store, top=2)

    assert api.calls == []
    assert (report.summaries, report.details, report.issues, report.calls) == (
        0,
        0,
        0,
        0,
    )


def test_top_picks_the_most_appearing_and_breaks_ties_by_id(tmp_path: Path) -> None:
    api = FakeComicVine()

    crawl_comicvine(api, ComicVineDump(tmp_path), top=3)

    assert api.asked_for("detail") == [2, 3, 5]


def test_an_issue_in_two_details_is_fetched_once(tmp_path: Path) -> None:
    api = FakeComicVine()

    crawl_comicvine(api, ComicVineDump(tmp_path), top=2)

    assert sorted(api.asked_for("issues")) == [100, 101, 102]


def test_raising_top_fetches_only_the_new_details(tmp_path: Path) -> None:
    store = ComicVineDump(tmp_path)
    crawl_comicvine(FakeComicVine(), store, top=2)
    api = FakeComicVine()

    crawl_comicvine(api, store, top=3)

    assert api.asked_for("detail") == [5]
    assert api.asked_for("issues") == [103]


def test_max_calls_stops_the_run_and_a_second_run_finishes_it(
    tmp_path: Path,
) -> None:
    api = FakeComicVine()
    store = ComicVineDump(tmp_path)

    first = crawl_comicvine(api, store, max_calls=3, top=2)

    assert first.stopped
    assert first.calls == 3
    assert api.steps() == ["list", "summaries", "summaries"]
    assert store.saved_ids(DownloadPart.CHARACTERS) == {1, 2, 3, 4}

    second = crawl_comicvine(api, store, top=2)

    assert not second.stopped
    assert api.steps().count("list") == 1
    assert api.asked_for("summaries") == [1, 2, 3, 4, 5]
    assert store.saved_ids(DownloadPart.ISSUES) == {100, 101, 102}


def test_progress_reports_each_step_with_its_total(tmp_path: Path) -> None:
    seen: list[tuple[str, int, int]] = []

    crawl_comicvine(
        FakeComicVine(),
        ComicVineDump(tmp_path),
        top=1,
        progress=lambda step, done, total: seen.append((step, done, total)),
    )

    assert seen == [
        ("characters", 2, 5),
        ("characters", 4, 5),
        ("characters", 5, 5),
        ("details", 1, 1),
        ("issues", 2, 2),
    ]
