"""Raw pages on disk: a JSONL file of pages and a JSON list of titles per category."""

import json
from collections.abc import Iterable, Iterator
from dataclasses import asdict
from pathlib import Path

from cerebro.domain.pages import PageRef, RawPage


class RawPageStore:
    """Raw pages for one category, e.g. `characters.jsonl` and `characters-titles.json`.

    Pages are only ever appended, so an interrupted crawl resumes where it stopped.
    """

    def __init__(self, root: Path, name: str) -> None:
        self.pages_path = root / f"{name}.jsonl"
        self.titles_path = root / f"{name}-titles.json"

    # Titles: every page in the category, saved once so reruns skip asking the wiki.

    def load_titles(self) -> list[PageRef] | None:
        """The saved titles, or None if they were never saved."""
        if not self.titles_path.exists():
            return None

        items = json.loads(self.titles_path.read_text())
        return [PageRef(**item) for item in items]

    def save_titles(self, refs: Iterable[PageRef]) -> None:
        items = [asdict(ref) for ref in refs]

        self.titles_path.parent.mkdir(parents=True, exist_ok=True)
        self.titles_path.write_text(json.dumps(items))

    # Pages: one JSON object per line, in the order they were fetched.

    def read(self) -> Iterator[RawPage]:
        if not self.pages_path.exists():
            return

        with self.pages_path.open(encoding="utf-8") as fh:
            for line in fh:
                yield RawPage(**json.loads(line))

    def saved_ids(self) -> set[int]:
        return {page.pageid for page in self.read()}

    def append(self, pages: Iterable[RawPage]) -> None:
        self.pages_path.parent.mkdir(parents=True, exist_ok=True)

        # Append mode: pages already in the file are never rewritten.
        with self.pages_path.open("a", encoding="utf-8") as fh:
            for page in pages:
                fh.write(json.dumps(asdict(page)) + "\n")
