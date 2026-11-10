"""Raw pages on disk: a JSONL file of pages and a JSON list of titles per category."""

import json
from collections.abc import Iterable, Iterator
from dataclasses import asdict
from pathlib import Path

from cerebro.domain.pages import Category, PageRef, RawPage
from cerebro.ports.pages import PageReader, PageStore


class JsonlPageStore(PageStore, PageReader):
    """Raw pages in one folder, e.g. `characters.jsonl` and `characters-titles.json`.

    Pages are only ever appended, so an interrupted crawl resumes where it stopped.
    """

    def __init__(self, root: Path) -> None:
        self.root = root

    # Titles: every page in the category, saved once so reruns skip asking the wiki.

    def load_titles(self, category: Category) -> list[PageRef] | None:
        path = self._titles_path(category)
        if not path.exists():
            return None

        items = json.loads(path.read_text())
        return [PageRef(**item) for item in items]

    def save_titles(self, category: Category, refs: Iterable[PageRef]) -> None:
        items = [asdict(ref) for ref in refs]

        self.root.mkdir(parents=True, exist_ok=True)
        self._titles_path(category).write_text(json.dumps(items))

    # Pages: one JSON object per line, in the order they were fetched.

    def read(self, category: Category) -> Iterator[RawPage]:
        path = self._pages_path(category)
        if not path.exists():
            return

        with path.open(encoding="utf-8") as fh:
            for line in fh:
                yield RawPage(**json.loads(line))

    def saved_ids(self, category: Category) -> set[int]:
        return {page.pageid for page in self.read(category)}

    def append(self, category: Category, pages: Iterable[RawPage]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)

        # Append mode: pages already in the file are never rewritten.
        with self._pages_path(category).open("a", encoding="utf-8") as fh:
            for page in pages:
                fh.write(json.dumps(asdict(page)) + "\n")

    def _pages_path(self, category: Category) -> Path:
        return self.root / f"{category}.jsonl"

    def _titles_path(self, category: Category) -> Path:
        return self.root / f"{category}-titles.json"
