<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/logo-dark.svg">
    <img src="assets/logo-light.svg" alt="Cerebro logo" width="128">
  </picture>
</p>

# Cerebro

A research agent that answers questions about Marvel characters, teams and comics, with citations, plus the evaluation suite that measures how often it is right.

The agent searches a local copy of the Marvel Database wiki and Comic Vine, calls tools to look things up, and cites the record behind every claim. The evaluation suite runs a fixed set of hand-checked questions against several models and reports correctness, grounding, refusals, latency and cost per solved question.

Status: early. The data pipeline runs, and the agent answers questions with citations, in the CLI or on a local chat page that shows each tool call as it happens; the evaluation suite does not exist yet.

## Development

Requires [uv](https://docs.astral.sh/uv/).

```sh
uv sync                          # create .venv and install the pinned dependencies
uv run pytest                    # run the tests
uv run pytest -m live            # check API keys against the real services
uv run ruff check                # lint
uv run ruff format               # format
uv run cerebro crawl fandom      # download raw wiki pages; safe to rerun
uv run cerebro parse fandom      # turn them into records in data/records.sqlite
uv run cerebro chunk             # cut the parsed character pages into chunks for search
uv run cerebro embed             # embed every chunk; safe to resume (needs OLLAMA_BASE_URL)
uv run cerebro load comicvine    # store Comic Vine's characters next to them
uv run cerebro match comicvine   # match Comic Vine's characters to the parsed ones
uv run cerebro ask "..."         # answer a question, with citations (needs MISTRAL_API_KEY)
```

To use the chat page, start the API and then the page, which needs Node 22 (`nvm use` reads it from `web/.nvmrc`):

```sh
uv run cerebro serve             # the question API, on port 8000
cd web && nvm use && npm install && npm run dev
```

Open the address Vite prints. Vite sends `/ask` to the API.

## Data and credits

- Character, team and comic pages, including comic creators and appearances, come from the [Marvel Database](https://marvel.fandom.com) on Fandom, licensed under [CC BY-SA](https://creativecommons.org/licenses/by-sa/3.0/). Text derived from it keeps that license.
- Issue dates and per-character issue lists come from the [Comic Vine API](https://comicvine.gamespot.com/api/) under its terms for non-commercial use. It is not redistributed here; it is fetched with your own API key.

This is a non-commercial fan project. It is not affiliated with or endorsed by Marvel, Fandom or Comic Vine.

## License

Code is MIT licensed. See [LICENSE](LICENSE).
