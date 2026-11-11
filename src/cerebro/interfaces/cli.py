"""Command-line entry point: `cerebro <command>`."""

import logging
from typing import Annotated

import typer

from cerebro import bootstrap
from cerebro.domain.answers import Answer, Step, ToolCall, ToolReply
from cerebro.domain.pages import Category
from cerebro.ports.agent import ModelTimeout, ProviderError, RateLimited
from cerebro.ports.embeddings import EmbedderUnavailable
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
    except bootstrap.MissingKey as error:
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
def ask(question: str) -> None:
    """Answer a question from the stored records, with citations.

    Prints each tool call and what it returned as the agent works, then the answer.
    """
    try:
        for step in bootstrap.ask(question):
            show_step(step)
    except bootstrap.MissingKey as error:
        typer.echo(f"Set {error} to ask questions.", err=True)
        raise typer.Exit(1) from None
    except RecordsMissing as error:
        typer.echo(f"{error}. Run `cerebro parse fandom` first.", err=True)
        raise typer.Exit(1) from None
    except RateLimited:
        typer.echo(
            "Mistral is rate limiting requests; try again in a minute.", err=True
        )
        raise typer.Exit(1) from None
    except ModelTimeout:
        typer.echo("Mistral did not reply in time.", err=True)
        raise typer.Exit(1) from None
    except ProviderError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(1) from None


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


def show_pages_read(done: int) -> None:
    # Every thousand pages: often enough to see it move, rarely enough to stay cheap.
    if done % 1000 == 0:
        typer.echo(f"\r  {done} pages", nl=False)


def show_progress(done: int, total: int) -> None:
    # \r returns to the start of the line, so each update replaces the last one.
    typer.echo(f"\r  {done}/{total}", nl=False)
