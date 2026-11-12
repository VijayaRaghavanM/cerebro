from pathlib import Path

import pytest
from typer.testing import CliRunner

from cerebro import bootstrap
from cerebro.application.crawl_comicvine import ComicVineCrawlReport, Progress
from cerebro.interfaces.cli import app
from cerebro.ports.comicvine import ComicVineUnavailable


def test_crawl_comicvine_prints_what_was_fetched(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asked: dict[str, int | None] = {}

    def fake(
        *, top: int, max_calls: int | None, progress: Progress
    ) -> ComicVineCrawlReport:
        asked.update(top=top, max_calls=max_calls)
        progress("details", 1, 7)
        return ComicVineCrawlReport(1200, 1200, 7, 3000, 45, stopped=False)

    monkeypatch.setattr(bootstrap, "crawl_comicvine", fake)

    result = CliRunner().invoke(app, ["crawl", "comicvine", "--top", "7"])

    assert result.exit_code == 0
    assert asked == {"top": 7, "max_calls": None}
    assert result.output.endswith(
        "\r1,200 characters listed; fetched 1,200 summaries, 7 details, "
        "3,000 issues in 45 calls\n"
    )


def test_a_run_stopped_by_max_calls_says_to_rerun(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake(
        *, top: int, max_calls: int | None, progress: Progress
    ) -> ComicVineCrawlReport:
        assert (top, max_calls) == (300, 5)
        return ComicVineCrawlReport(10, 4, 0, 0, 5, stopped=True)

    monkeypatch.setattr(bootstrap, "crawl_comicvine", fake)

    result = CliRunner().invoke(app, ["crawl", "comicvine", "--max-calls", "5"])

    assert result.exit_code == 0
    assert "Stopped at --max-calls; rerun to resume." in result.output


def test_crawling_without_a_key_says_what_to_set(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("COMICVINE_API_KEY", raising=False)

    result = CliRunner().invoke(app, ["crawl", "comicvine"])

    assert result.exit_code == 1
    assert "Set COMICVINE_API_KEY to crawl Comic Vine." in result.output
    assert not (data_dir / "raw").exists()


def test_an_unavailable_comic_vine_keeps_saved_records_and_exits_cleanly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake(
        *, top: int, max_calls: int | None, progress: Progress
    ) -> ComicVineCrawlReport:
        raise ComicVineUnavailable("https://private.example/?api_key=secret")

    monkeypatch.setattr(bootstrap, "crawl_comicvine", fake)

    result = CliRunner().invoke(app, ["crawl", "comicvine"])

    assert result.exit_code == 1
    assert "Comic Vine is unavailable" in result.output
    assert "rerun to resume" in result.output
    assert "secret" not in result.output
    assert result.exception is None or isinstance(result.exception, SystemExit)
