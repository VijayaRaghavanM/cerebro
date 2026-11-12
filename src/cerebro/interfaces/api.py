"""HTTP entry point: `POST /ask` streams the agent's steps as server-sent events."""

import json
from collections.abc import Iterator
from dataclasses import asdict
from typing import Annotated

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, StringConstraints

from cerebro import bootstrap
from cerebro.domain.answers import Answer, Step, ToolCall, ToolReply
from cerebro.ports.agent import ModelTimeout, ProviderError, RateLimited
from cerebro.ports.records import RecordsMissing

# A question, not a document.
MAX_QUESTION_LENGTH = 500

app = FastAPI()


class AskRequest(BaseModel):
    question: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True, min_length=1, max_length=MAX_QUESTION_LENGTH
        ),
    ]


@app.post("/ask")
def ask(request: AskRequest) -> StreamingResponse:
    # Called before the stream starts: once the first byte is sent the status is
    # fixed at 200, so a missing key has to fail here to become a 503.
    try:
        steps = bootstrap.ask(request.question)
    except bootstrap.MissingSetting as error:
        raise HTTPException(503, f"Set {error} to ask questions.") from None

    return StreamingResponse(stream(steps), media_type="text/event-stream")


def stream(steps: Iterator[Step]) -> Iterator[str]:
    try:
        for step in steps:
            yield event(step_name(step), asdict(step))
    except RecordsMissing as error:
        yield event("error", {"message": f"{error}. Run `cerebro parse fandom` first."})
    except RateLimited:
        message = "Mistral is rate limiting requests; try again in a minute."
        yield event("error", {"message": message})
    except ModelTimeout:
        yield event("error", {"message": "Mistral did not reply in time."})
    except ProviderError as error:
        yield event("error", {"message": str(error)})


def step_name(step: Step) -> str:
    match step:
        case ToolCall():
            return "call"
        case ToolReply():
            return "reply"
        case Answer():
            return "answer"


def event(name: str, data: object) -> str:
    return f"event: {name}\ndata: {json.dumps(data)}\n\n"
