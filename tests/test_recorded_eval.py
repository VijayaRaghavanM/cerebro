"""CI's check on the tools: a recorded evaluation of a small wiki, replayed offline.

The replay runs the real tools over the saved model replies, so a tool that
changes what the model sees makes the replay differ from the recording.

To record again (about a cent, needs OPENROUTER_API_KEY):
    CEREBRO_RECORD_EVAL=1 uv run pytest -m live tests/test_recorded_eval.py
"""

import os
import shutil
from pathlib import Path

import pytest
from helpers import real_character, real_comic, real_team

from cerebro import bootstrap
from cerebro.adapters.jsonl_evaluation import JsonlRunStore
from cerebro.adapters.sqlite_records import SqliteRecordStore
from cerebro.bootstrap import Contestant
from cerebro.domain.answers import Answer
from cerebro.domain.pages import Category

EVAL = Path(__file__).parent / "fixtures" / "eval"
RUN = "recorded"


@pytest.fixture
def small_wiki(data_dir: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A records file of the three saved wiki pages, chunked, and the golden file
    in the place the commands read it. The tmp folder is the working folder.
    """
    # With a vector server set, the agent would search by meaning as well.
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)

    records = SqliteRecordStore(data_dir / bootstrap.RECORDS_FILE)
    records.replace(Category.CHARACTERS, [real_character()])
    records.replace(Category.TEAMS, [real_team()])
    records.replace(Category.COMICS, [real_comic()])
    bootstrap.chunk_records()

    bootstrap.GOLDEN_FILE.parent.mkdir()
    shutil.copy(EVAL / "golden.jsonl", bootstrap.GOLDEN_FILE)

    return data_dir


def test_the_recorded_evaluation_replays_exactly(small_wiki: Path) -> None:
    shutil.copytree(EVAL / RUN, bootstrap.RUNS_DIR / RUN)

    report = bootstrap.replay_run(RUN)

    assert report.checked == 4
    assert report.mismatches == ()


@pytest.mark.live
@pytest.mark.skipif(
    os.environ.get("CEREBRO_RECORD_EVAL") != "1",
    reason="set CEREBRO_RECORD_EVAL=1 to record",
)
def test_record_the_evaluation(small_wiki: Path) -> None:
    report = bootstrap.run_eval(Contestant.MINISTRAL_14B_OPENROUTER, run_name=RUN)

    store = JsonlRunStore(bootstrap.RUNS_DIR / RUN)
    answered = [r for r in store.results() if isinstance(r.final, Answer)]
    # A question the model failed on would make the recording useless.
    assert (report.failed, len(answered)) == (0, 4)

    shutil.rmtree(EVAL / RUN, ignore_errors=True)
    shutil.copytree(bootstrap.RUNS_DIR / RUN, EVAL / RUN)
