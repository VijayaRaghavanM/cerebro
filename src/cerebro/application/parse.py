"""Turn one category's saved pages into records and store them."""

from collections.abc import Callable, Iterator
from dataclasses import dataclass

from cerebro.domain.pages import Category
from cerebro.domain.records import Record
from cerebro.ports.pages import PageReader
from cerebro.ports.records import RecordParser, RecordStore

Progress = Callable[[int], None]  # called with the number of pages read so far


@dataclass(frozen=True)
class ParseReport:
    pages: int
    records: int  # pages without a record of the category's kind are skipped


def parse(
    pages: PageReader,
    parser: RecordParser,
    store: RecordStore,
    category: Category,
    *,
    progress: Progress | None = None,
) -> ParseReport:
    """Parse every saved page in the category and replace its stored records.

    Pages stream through one at a time, so a category is never held in memory whole.
    """
    read = kept = 0

    def records() -> Iterator[Record]:
        nonlocal read, kept
        for page in pages.read(category):
            read += 1
            record = parser.parse(page)
            if record is not None:
                kept += 1
                yield record
            if progress is not None:
                progress(read)

    store.replace(category, records())

    return ParseReport(pages=read, records=kept)
