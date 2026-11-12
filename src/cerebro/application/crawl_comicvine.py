"""Resumable crawl of Comic Vine's Marvel characters into the download."""

from collections.abc import Callable
from dataclasses import dataclass, field
from itertools import batched

from cerebro.domain.comicvine import DownloadPart, RawRecord
from cerebro.ports.comicvine import ComicVineAPI, DownloadStore

Progress = Callable[[str, int, int], None]  # called with (step, done, to do)


@dataclass(frozen=True)
class ComicVineCrawlReport:
    listed: int  # Marvel characters Comic Vine lists
    summaries: int  # fetched this run
    details: int  # fetched this run
    issues: int  # fetched this run
    calls: int  # API calls this run made
    stopped: bool  # the run hit `max_calls` before it finished


class _OutOfCalls(Exception):
    """The run used up `max_calls`."""


@dataclass
class _Run:
    """What one run has done so far, kept outside the steps so a stop loses nothing."""

    max_calls: int | None
    progress: Progress | None
    calls: int = 0
    listed: int = 0
    fetched: dict[DownloadPart, int] = field(
        default_factory=lambda: dict.fromkeys(DownloadPart, 0)
    )

    def spend_call(self) -> None:
        """Count one API call, or stop the crawl if the run may make no more."""
        if self.max_calls is not None and self.calls >= self.max_calls:
            raise _OutOfCalls

        self.calls += 1

    def show(self, part: DownloadPart, done: int, total: int) -> None:
        if self.progress is not None:
            self.progress(part.value, done, total)


def crawl_comicvine(
    api: ComicVineAPI,
    store: DownloadStore,
    *,
    top: int,
    max_calls: int | None = None,
    progress: Progress | None = None,
) -> ComicVineCrawlReport:
    """Download Marvel's characters, then the `top` in detail, then their issues.

    "Top" means most appearances. Each step skips what the store already holds, so a
    rerun resumes. `max_calls` stops the run cleanly after that many API calls.
    """
    run = _Run(max_calls, progress)

    try:
        listed = _list_characters(api, store, run)
        _fetch_summaries(api, store, run, listed)
        _fetch_details(api, store, run, top)
        _fetch_issues(api, store, run)
    except _OutOfCalls:
        stopped = True
    else:
        stopped = False

    return ComicVineCrawlReport(
        listed=run.listed,
        summaries=run.fetched[DownloadPart.CHARACTERS],
        details=run.fetched[DownloadPart.DETAILS],
        issues=run.fetched[DownloadPart.ISSUES],
        calls=run.calls,
        stopped=stopped,
    )


def _list_characters(
    api: ComicVineAPI, store: DownloadStore, run: _Run
) -> list[RawRecord]:
    # Ask Comic Vine for the list once; reruns reuse the saved one.
    listed = store.load_marvel_characters()
    if listed is None:
        run.spend_call()
        listed = api.marvel_characters()
        store.save_marvel_characters(listed)

    run.listed = len(listed)
    return listed


def _fetch_summaries(
    api: ComicVineAPI, store: DownloadStore, run: _Run, listed: list[RawRecord]
) -> None:
    saved = store.saved_ids(DownloadPart.CHARACTERS)
    todo = [record["id"] for record in listed if record["id"] not in saved]

    # Save after every batch, so an interruption loses at most one batch.
    for batch in batched(todo, api.batch_limit, strict=False):
        run.spend_call()
        records = api.character_summaries(batch)
        store.append(DownloadPart.CHARACTERS, records)

        run.fetched[DownloadPart.CHARACTERS] += len(records)
        run.show(
            DownloadPart.CHARACTERS, run.fetched[DownloadPart.CHARACTERS], len(todo)
        )


def _fetch_details(
    api: ComicVineAPI, store: DownloadStore, run: _Run, top: int
) -> None:
    summaries = list(store.read(DownloadPart.CHARACTERS))

    # Ties go to the lower id, so the same characters are picked on every run.
    ranked = sorted(
        summaries,
        key=lambda record: (
            -(record.get("count_of_issue_appearances") or 0),
            record["id"],
        ),
    )
    wanted = [record["id"] for record in ranked[:top]]
    saved = store.saved_ids(DownloadPart.DETAILS)
    todo = [character_id for character_id in wanted if character_id not in saved]

    for character_id in todo:
        run.spend_call()
        store.append(DownloadPart.DETAILS, [api.character_detail(character_id)])

        run.fetched[DownloadPart.DETAILS] += 1
        run.show(DownloadPart.DETAILS, run.fetched[DownloadPart.DETAILS], len(todo))


def _fetch_issues(api: ComicVineAPI, store: DownloadStore, run: _Run) -> None:
    # Characters share issues, so a set keeps each one to a single fetch.
    wanted = {
        issue_id
        for detail in store.read(DownloadPart.DETAILS)
        for issue_id in detail["issue_ids"]
    }
    todo = sorted(wanted - store.saved_ids(DownloadPart.ISSUES))

    for batch in batched(todo, api.batch_limit, strict=False):
        run.spend_call()
        records = api.issues(batch)
        store.append(DownloadPart.ISSUES, records)

        run.fetched[DownloadPart.ISSUES] += len(records)
        run.show(DownloadPart.ISSUES, run.fetched[DownloadPart.ISSUES], len(todo))
