import json
import sqlite3
from pathlib import Path

import pytest
from typer.testing import CliRunner

from cerebro.interfaces.cli import app

FIXTURES = Path(__file__).parent / "fixtures" / "fandom"


def test_parse_fandom_stores_the_records_of_the_saved_pages(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A team page and a handbook page filed under Teams, as the crawl saves them.
    team = json.loads((FIXTURES / "livewires.json").read_text(encoding="utf-8"))
    handbook = {
        **team,
        "pageid": 2,
        "wikitext": "{{Marvel Database:Handbook Template}}",
    }
    raw = tmp_path / "raw" / "fandom"
    raw.mkdir(parents=True)
    lines = [json.dumps(page) for page in (team, handbook)]
    (raw / "teams.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")

    # The real settings, pointed at the temp folder the way a user would point them.
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(app, ["parse", "fandom", "--category", "teams"])

    assert result.exit_code == 0
    assert result.output.split(":")[0] == "teams"  # only the category asked for
    assert "2 pages, 1 records" in result.output
    with sqlite3.connect(tmp_path / "records.sqlite") as db:
        assert db.execute("SELECT name FROM teams").fetchall() == [("Livewires",)]
