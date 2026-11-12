"""Command-line entry point: `cerebro <command>`."""

import logging
from typing import Annotated

import typer

from cerebro import bootstrap
from cerebro.domain.answers import Answer, Step, ToolCall, ToolReply
from cerebro.domain.evaluation import Failure, RunResult, Split, Verdict
from cerebro.domain.pages import Category
from cerebro.ports.agent import ModelTimeout, ProviderError, RateLimited
from cerebro.ports.comicvine import ComicVineUnavailable
from cerebro.ports.embeddings import EmbedderUnavailable, VectorsMissing
from cerebro.ports.evaluation import ExchangesMissing, VerdictUnreadable
from cerebro.ports.records import RecordsMissing
from cerebro.ports.wiki import WikiUnavailable

app = typer.Typer(no_args_is_help=True)

crawl_app = typer.Typer(no_args_is_help=True, help="Download raw source data.")
app.add_typer(crawl_app, name="crawl")

parse_app = typer.Typer(no_args_is_help=True, help="Turn raw pages into records.")
app.add_typer(parse_app, name="parse")

load_app = typer.Typer(
    no_args_is_help=True, help="Load other sources into the record store."
)
app.add_typer(load_app, name="load")

match_app = typer.Typer(no_args_is_help=True, help="Match records across sources.")
app.add_typer(match_app, name="match")

eval_app = typer.Typer(no_args_is_help=True, help="Measure a model on the golden set.")
app.add_typer(eval_app, name="eval")


@crawl_app.command("fandom")
def crawl_fandom(
    category: Annotated[
        list[Category] | None,
        typer.Option(help="Repeatable. Default: all."),
    ] = None,
    limit: Annotated[
        int | None,
        typer.Option(help="Fetch at most this many new pages per category."),
    ] = None,
) -> None:
    """Download raw Marvel Database pages. Safe to rerun: saved pages are skipped."""
    # Print the client's retry warnings; hide debug and info logs.
    logging.basicConfig(level=logging.WARNING, format="%(message)s")

    for name in category or list(Category):
        typer.echo(f"{name}:")

        try:
            report = bootstrap.crawl_fandom(name, limit=limit, progress=show_progress)
        except WikiUnavailable as error:
            typer.echo(f"\n{error}. Saved pages are kept; rerun to resume.", err=True)
            raise typer.Exit(1) from None

        # The leading \r writes the final counts over the progress line.
        typer.echo(
            f"\r  {report.listed} listed, {report.already_saved} already saved, "
            f"{report.fetched} fetched, {report.missing} missing"
        )


@crawl_app.command("comicvine")
def crawl_comicvine(
    top: Annotated[
        int,
        typer.Option(
            help="How many of the most-appearing characters to fetch in detail."
        ),
    ] = 300,
    max_calls: Annotated[
        int | None,
        typer.Option(help="Stop after this many API calls; the next run resumes."),
    ] = None,
) -> None:
    """Download Marvel characters from Comic Vine. Safe to rerun: saved records stay.

    Comic Vine allows about 200 calls an hour, so a big --top takes hours.
    """
    # Print the client's retry warnings; hide debug and info logs.
    logging.basicConfig(level=logging.WARNING, format="%(message)s")

    try:
        report = bootstrap.crawl_comicvine(
            top=top, max_calls=max_calls, progress=show_step_progress
        )
    except bootstrap.MissingSetting as error:
        typer.echo(f"Set {error} to crawl Comic Vine.", err=True)
        raise typer.Exit(1) from None
    except ComicVineUnavailable:
        # A fixed message: whatever the error carries never reaches the terminal, so
        # the key in Comic Vine's URLs cannot either.
        typer.echo(
            "\nComic Vine is unavailable. Saved records are kept; rerun to resume.",
            err=True,
        )
        raise typer.Exit(1) from None

    # The leading \r writes the final counts over the progress line.
    typer.echo(
        f"\r{report.listed:,} characters listed; fetched {report.summaries:,} "
        f"summaries, {report.details:,} details, {report.issues:,} issues "
        f"in {report.calls:,} calls"
    )
    if report.stopped:
        typer.echo("Stopped at --max-calls; rerun to resume.")


@parse_app.command("fandom")
def parse_fandom(
    category: Annotated[
        list[Category] | None,
        typer.Option(help="Repeatable. Default: all."),
    ] = None,
) -> None:
    """Parse saved Marvel Database pages into records. Safe to rerun.

    A rerun replaces a category's records; a run that fails keeps the previous ones.
    """
    for name in category or list(Category):
        typer.echo(f"{name}:")

        report = bootstrap.parse_fandom(name, progress=show_pages_read)

        # The leading \r writes the final counts over the progress line.
        typer.echo(f"\r  {report.pages} pages, {report.records} records")


@load_app.command("comicvine")
def load_comicvine() -> None:
    """Store Comic Vine's characters next to the parsed records. Safe to rerun.

    A rerun replaces the stored Comic Vine characters.
    """
    try:
        report = bootstrap.load_comicvine()
    except FileNotFoundError as error:
        typer.echo(f"No Comic Vine data: {error.filename} is missing.", err=True)
        raise typer.Exit(1) from None

    typer.echo(
        f"{report.characters:,} Comic Vine characters stored, "
        f"{report.with_detail:,} with detail"
    )


@match_app.command("comicvine")
def match_comicvine() -> None:
    """Match Comic Vine's characters to the parsed ones. Safe to rerun.

    A rerun replaces the stored matches.
    """
    try:
        report = bootstrap.match_comicvine()
    except RecordsMissing as error:
        typer.echo(f"{error}. Run `cerebro parse fandom` first.", err=True)
        raise typer.Exit(1) from None
    except FileNotFoundError as error:
        typer.echo(f"No Comic Vine data: {error.filename} is missing.", err=True)
        raise typer.Exit(1) from None

    typer.echo(
        f"{report.matched:,} of the {report.with_issues:,} Comic Vine characters "
        f"with an issue list matched ({report.comicvine:,} listed in all; "
        f"{report.pages_claimed_twice:,} pages claimed twice)"
    )


@app.command()
def chunk() -> None:
    """Cut the parsed character pages into chunks for search. Safe to rerun.

    A rerun replaces the stored chunks.
    """
    try:
        report = bootstrap.chunk_records()
    except RecordsMissing as error:
        typer.echo(f"{error}. Run `cerebro parse fandom` first.", err=True)
        raise typer.Exit(1) from None

    typer.echo(f"{report.pages:,} pages, {report.chunks:,} chunks")


@app.command()
def embed() -> None:
    """Embed every chunk with nomic-embed-text on the Ollama server.

    Safe to rerun: finished parts are kept.
    """
    try:
        report = bootstrap.embed_chunks(progress=show_progress)
    except bootstrap.MissingSetting as error:
        typer.echo(f"Set {error} to embed chunks.", err=True)
        raise typer.Exit(1) from None
    except RecordsMissing as error:
        typer.echo(f"{error}. Run `cerebro chunk` first.", err=True)
        raise typer.Exit(1) from None
    except EmbedderUnavailable:
        typer.echo(
            "\nThe embedding server is unavailable; finished parts are kept, "
            "rerun to resume.",
            err=True,
        )
        raise typer.Exit(1) from None

    # The leading \r writes the final counts over the progress line.
    typer.echo(
        f"\r{report.chunks:,} chunks in {report.parts} parts "
        f"({report.skipped_parts} already done)"
    )


@app.command()
def ask(
    question: str,
    model: Annotated[
        bootstrap.Contestant, typer.Option(help="The model that answers.")
    ] = bootstrap.Contestant.MINISTRAL_14B,
) -> None:
    """Answer a question from the stored records, with citations.

    Prints each tool call and what it returned as the agent works, then the answer.
    """
    try:
        # Read before the steps, so a missing key fails before this line is shown.
        steps = bootstrap.ask(question, model)
        typer.echo(bootstrap.search_label(), err=True)
        for step in steps:
            show_step(step)
    except bootstrap.MissingSetting as error:
        typer.echo(f"Set {error} to ask questions.", err=True)
        raise typer.Exit(1) from None
    except RecordsMissing as error:
        typer.echo(f"{error}. Run `cerebro parse fandom` first.", err=True)
        raise typer.Exit(1) from None
    except VectorsMissing as error:
        typer.echo(f"{error}. Run `cerebro embed` first.", err=True)
        raise typer.Exit(1) from None
    except EmbedderUnavailable as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(1) from None
    except RateLimited:
        typer.echo(
            "The model provider is rate limiting requests; try again in a minute.",
            err=True,
        )
        raise typer.Exit(1) from None
    except ModelTimeout:
        typer.echo("The model did not reply in time.", err=True)
        raise typer.Exit(1) from None
    except ProviderError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(1) from None


@eval_app.command("run")
def eval_run(
    model: Annotated[
        bootstrap.Contestant, typer.Option(help="The model that answers.")
    ],
    split: Annotated[
        Split | None, typer.Option(help="Only this split. Default: both.")
    ] = None,
    limit: Annotated[
        int | None,
        typer.Option(help="Answer at most this many new questions."),
    ] = None,
    run: Annotated[
        str | None,
        typer.Option(help="The run's folder name under runs/. Default: model-split."),
    ] = None,
) -> None:
    """Answer the golden questions and save each result. Safe to rerun.

    A rerun skips the answered questions; a failed question is tried again.
    """
    try:
        report = bootstrap.run_eval(
            model,
            split,
            limit=limit,
            run_name=run,
            progress=show_result,
        )
    except bootstrap.MissingSetting as error:
        typer.echo(f"Set {error} to run the evaluation.", err=True)
        raise typer.Exit(1) from None
    except FileNotFoundError as error:
        typer.echo(f"No golden questions: {error.filename} is missing.", err=True)
        raise typer.Exit(1) from None
    except RecordsMissing as error:
        typer.echo(f"{error}. Run `cerebro parse fandom` first.", err=True)
        raise typer.Exit(1) from None
    except VectorsMissing as error:
        typer.echo(f"{error}. Run `cerebro embed` first.", err=True)
        raise typer.Exit(1) from None
    except EmbedderUnavailable as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(1) from None

    typer.echo(
        f"{report.answered} answered, {report.failed} failed, "
        f"{report.skipped} already answered"
    )


@eval_app.command("replay")
def eval_replay(
    run: Annotated[str, typer.Argument(help="The run's folder name under runs/.")],
) -> None:
    """Rerun a saved run offline and check it gives the same steps and answers.

    Each answered question is asked again from its saved model exchanges, so
    nothing leaves this machine and no key is needed. Exits 1 if any answer differs.
    """
    try:
        report = bootstrap.replay_run(run)
    except FileNotFoundError as error:
        typer.echo(f"No golden questions: {error.filename} is missing.", err=True)
        raise typer.Exit(1) from None
    except ExchangesMissing as error:
        typer.echo(f"{error}: its model exchanges were not saved.", err=True)
        raise typer.Exit(1) from None
    except RecordsMissing as error:
        typer.echo(f"{error}. Run `cerebro parse fandom` first.", err=True)
        raise typer.Exit(1) from None

    if report.checked == 0:
        typer.echo(f"No answered questions in runs/{run}.", err=True)
        raise typer.Exit(1)

    for mismatch in report.mismatches:
        typer.echo(f"{mismatch.question_id}: {mismatch.difference}")
    reproduced = report.checked - len(report.mismatches)
    typer.echo(f"{reproduced} of {report.checked} answers reproduced exactly")
    if report.mismatches:
        raise typer.Exit(1)


@eval_app.command("judge")
def eval_judge(
    run: Annotated[str, typer.Argument(help="The run's folder name under runs/.")],
) -> None:
    """Have a model judge whether each answer is correct. Safe to rerun.

    Every run goes to the same judge, so their scores compare. Verdicts are saved
    as they come, and a rerun skips the questions already judged. Run `eval score`
    afterwards to use them.
    """
    try:
        report = bootstrap.judge_run(run, progress=show_verdict)
    except bootstrap.MissingSetting as error:
        typer.echo(f"Set {error} to judge a run.", err=True)
        raise typer.Exit(1) from None
    except FileNotFoundError as error:
        typer.echo(f"No golden questions: {error.filename} is missing.", err=True)
        raise typer.Exit(1) from None
    except RateLimited:
        typer.echo(
            "The judge is rate limiting requests. Verdicts are kept; rerun later "
            "to resume.",
            err=True,
        )
        raise typer.Exit(1) from None
    except ModelTimeout:
        typer.echo("The judge did not reply in time. Verdicts are kept.", err=True)
        raise typer.Exit(1) from None
    except (ProviderError, VerdictUnreadable) as error:
        typer.echo(f"{error} Verdicts are kept.", err=True)
        raise typer.Exit(1) from None

    typer.echo(
        f"{report.judged} judged, {report.correct} correct, "
        f"{report.skipped} already judged"
    )


@eval_app.command("agreement")
def eval_agreement(
    run: Annotated[str, typer.Argument(help="The run's folder name under runs/.")],
) -> None:
    """Check the judge against hand labels.

    Compares the verdicts in verdicts.jsonl with the labels in labels.jsonl, one
    line each of question_id, correct and reason, over the questions that have
    both.
    """
    report = bootstrap.agreement_run(run)

    if report.compared == 0:
        typer.echo(f"No question in runs/{run} has a verdict and a label.", err=True)
        raise typer.Exit(1)

    if report.kappa is None:
        kappa = "kappa undefined (chance agreement is 1)"
    else:
        kappa = f"kappa {report.kappa:.2f}"

    typer.echo(f"{report.compared} compared, agreement {report.agreement:.0%}, {kappa}")
    typer.echo(
        f"both correct {report.both_correct}, both wrong {report.both_wrong}, "
        f"judge only {report.judge_only}, labels only {report.labels_only}"
    )
    if report.disagreed:
        typer.echo("disagree: " + ", ".join(report.disagreed))


@eval_app.command("score")
def eval_score(
    run: Annotated[str, typer.Argument(help="The run's folder name under runs/.")],
) -> None:
    """Score a saved run against the golden questions.

    Uses the judge's verdicts where `eval judge` has saved them, and rules where it
    has not. Writes scores.json and report.md into the run's folder and prints the
    totals.
    """
    try:
        overall = bootstrap.score_run(run)
    except FileNotFoundError as error:
        typer.echo(f"No golden questions: {error.filename} is missing.", err=True)
        raise typer.Exit(1) from None

    if overall is None:
        typer.echo(f"No results in runs/{run}.", err=True)
        raise typer.Exit(1)

    typer.echo(overall)


@app.command()
def serve(
    host: Annotated[
        str,
        typer.Option(help="Address to listen on. The default is this machine only."),
    ] = "127.0.0.1",
    port: Annotated[int, typer.Option(help="Port to listen on.")] = 8000,
) -> None:
    """Serve the question API on the given address."""
    # Imported here: uvicorn and FastAPI take over 100 ms to load, which every
    # other command would otherwise pay.
    import uvicorn

    from cerebro.interfaces.api import app as api

    uvicorn.run(api, host=host, port=port)


def show_step(step: Step) -> None:
    match step:
        case ToolCall():
            typer.echo(f"{step.tool}: {step.argument}")
        case ToolReply():
            # A reply runs to thousands of characters; its first line says what it is.
            first_line = step.text.partition("\n")[0]
            typer.echo(f"  {first_line}")
        case Answer():
            show_answer(step)


def show_answer(answer: Answer) -> None:
    typer.echo()
    typer.echo(answer.text)
    typer.echo()

    if answer.sources:
        for number, source in enumerate(answer.sources, start=1):
            typer.echo(f"[{number}] {source.title}: {source.url}")
    else:
        typer.echo("No sources cited.")
    typer.echo()

    typer.echo(
        f"{answer.model_calls} model calls, {answer.tool_calls} tool calls, "
        f"{answer.input_tokens:,} tokens in, {answer.output_tokens:,} out, "
        f"{answer.seconds:.0f} s"
    )


def show_result(result: RunResult) -> None:
    if isinstance(result.final, Failure):
        typer.echo(f"{result.question_id}: failed ({result.final.type})")
    else:
        typer.echo(f"{result.question_id}: answered")


def show_verdict(question_id: str, verdict: Verdict) -> None:
    ruling = "correct" if verdict.correct else "incorrect"
    typer.echo(f"{question_id}: {ruling}")


def show_pages_read(done: int) -> None:
    # Every thousand pages: often enough to see it move, rarely enough to stay cheap.
    if done % 1000 == 0:
        typer.echo(f"\r  {done} pages", nl=False)


def show_step_progress(step: str, done: int, total: int) -> None:
    # Padded to the longest step name, so a shorter name leaves nothing behind.
    typer.echo(f"\r  {step:<10} {done}/{total}", nl=False)


def show_progress(done: int, total: int) -> None:
    # \r returns to the start of the line, so each update replaces the last one.
    typer.echo(f"\r  {done}/{total}", nl=False)
