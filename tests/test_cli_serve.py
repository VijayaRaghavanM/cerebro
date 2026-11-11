import uvicorn
from pytest import MonkeyPatch
from typer.testing import CliRunner

from cerebro.interfaces.api import app as api
from cerebro.interfaces.cli import app


def test_serve_runs_the_api_on_this_machine_unless_told_otherwise(
    monkeypatch: MonkeyPatch,
) -> None:
    runs: list[tuple[object, str, int]] = []

    def run(served: object, host: str, port: int) -> None:
        runs.append((served, host, port))

    monkeypatch.setattr(uvicorn, "run", run)

    default = CliRunner().invoke(app, ["serve"])
    chosen = CliRunner().invoke(app, ["serve", "--host", "0.0.0.0", "--port", "9000"])

    assert default.exit_code == 0
    assert chosen.exit_code == 0
    assert runs == [(api, "127.0.0.1", 8000), (api, "0.0.0.0", 9000)]
