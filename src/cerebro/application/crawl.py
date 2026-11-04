"""Resumable crawl of one wiki category into the raw page store."""

from collections.abc import Callable
from dataclasses import dataclass

from cerebro.domain.pages import Category
from cerebro.ports.pages import PageStore
from cerebro.ports.wiki import WikiSource


@dataclass(frozen=True)
class CrawlReport:
    listed: int
    already_saved: int
    fetched: int
    missing: int  # listed, but the wiki returned no revision


def crawl(
    source: WikiSource,
    store: PageStore,
    category: Category,
    *,
    limit: int | None = None,
    progress: Callable[[int, int], None] | None = None,
) -> CrawlReport:
    """Fetch every page in the category that is not saved yet.

    `limit` caps how many new pages this run fetches.
    """
    # Ask the wiki for the category's titles once; reruns reuse the saved ones.
    refs = store.load_titles(category)
    if refs is None:
        refs = list(source.category_titles(category))
        store.save_titles(category, refs)

    # Skip pages already saved. This is what lets a rerun resume.
    saved = store.saved_ids(category)
    todo = [ref.pageid for ref in refs if ref.pageid not in saved]
    if limit is not None:
        todo = todo[:limit]

    # Save after every batch, so an interruption loses at most one batch.
    size = source.batch_limit
    fetched = 0
    for start in range(0, len(todo), size):
        batch = todo[start : start + size]

        pages = source.fetch(batch)
        store.append(category, pages)
        fetched += len(pages)

        if progress is not None:
            progress(start + len(batch), len(todo))

    return CrawlReport(
        listed=len(refs),
        already_saved=len(saved),
        fetched=fetched,
        missing=len(todo) - fetched,
    )
