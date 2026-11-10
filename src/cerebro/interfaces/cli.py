"""Command-line entry point: `cerebro <command>`."""

import logging
from typing import Annotated

import typer

from cerebro import bootstrap
from cerebro.domain.pages import Category
from cerebro.ports.wiki import WikiUnavailable

app = typer.Typer(no_args_is_help=True)

crawl_app = typer.Typer(no_args_is_help=True, help="Download raw source data.")
app.add_typer(crawl_app, name="crawl")

parse_app = typer.Typer(no_args_is_help=True, help="Turn raw pages into records.")
app.add_typer(parse_app, name="parse")


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


def show_pages_read(done: int) -> None:
    # Every thousand pages: often enough to see it move, rarely enough to stay cheap.
    if done % 1000 == 0:
        typer.echo(f"\r  {done} pages", nl=False)


def show_progress(done: int, total: int) -> None:
    # \r returns to the start of the line, so each update replaces the last one.
    typer.echo(f"\r  {done}/{total}", nl=False)
