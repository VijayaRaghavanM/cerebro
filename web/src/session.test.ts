import { describe, expect, it } from "vitest";
import { idle, reduce, type Action, type Answer, type Session } from "./session";

const answer: Answer = {
  text: "Yes [1].",
  sources: [{ title: "A", url: "https://x/A" }],
  model_calls: 3,
  tool_calls: 2,
  input_tokens: 10,
  output_tokens: 5,
  seconds: 9.5,
};

const asked: Action = { type: "asked" };
const ended: Action = { type: "ended" };
const answered: Action = { type: "event", event: { event: "answer", data: answer } };
const call: Action = {
  type: "event",
  event: { event: "call", data: { tool: "search_pages", argument: "Hellfire Club" } },
};
const reply: Action = {
  type: "event",
  event: { event: "reply", data: { tool: "search_pages", text: "1. one\n2. two" } },
};

function run(...actions: Action[]): Session {
  return actions.reduce(reduce, idle);
}

describe("reduce", () => {
  it("shows a call and its reply as one step with the reply's first line", () => {
    const session = run(asked, call, reply);

    expect(session.status).toBe("asking");
    expect(session.trace).toEqual([{ label: "search_pages: Hellfire Club", reply: "1. one" }]);
  });

  it("keeps the answer when the run is done", () => {
    const session = run(asked, call, reply, answered, ended);

    expect(session.status).toBe("done");
    expect(session.answer).toEqual(answer);
  });

  it("fails when the stream ends without an answer or an error", () => {
    const session = run(asked, call, reply, ended);

    expect(session.status).toBe("failed");
    expect(session.error).toBe("The server stopped before it answered.");
  });

  it("fails with the message of an error event", () => {
    const session = run(
      asked,
      { type: "event", event: { event: "error", data: { message: "model unavailable" } } },
      ended,
    );

    expect(session.status).toBe("failed");
    expect(session.error).toBe("model unavailable");
  });

  it("fails with the message of a request failure", () => {
    const session = run(asked, { type: "failed", message: "No model key" });

    expect(session.status).toBe("failed");
    expect(session.error).toBe("No model key");
  });

  it("clears the last trace and answer when asking again", () => {
    const session = run(asked, call, reply, answered, ended, asked);

    expect(session).toEqual({ ...idle, status: "asking" });
  });
});
