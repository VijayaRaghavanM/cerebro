import json
from pathlib import Path

import pytest

from cerebro.adapters.fandom_records import FandomRecordParser
from cerebro.domain.pages import Category, RawPage
from cerebro.domain.records import Character, Comic, Team

FIXTURES = Path(__file__).parent / "fixtures" / "fandom"


@pytest.mark.parametrize(
    ("category", "fixture", "kind"),
    [
        (Category.CHARACTERS, "daniel_berkhart.json", Character),
        (Category.TEAMS, "livewires.json", Team),
        (Category.COMICS, "marvel_comics_presents_170.json", Comic),
    ],
)
def test_each_category_reads_its_own_kind_of_record(
    category: Category, fixture: str, kind: type
) -> None:
    page = RawPage(**json.loads((FIXTURES / fixture).read_text(encoding="utf-8")))

    assert isinstance(FandomRecordParser(category).parse(page), kind)
