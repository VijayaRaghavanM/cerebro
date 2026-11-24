import { describe, expect, it } from "vitest";
import { checkOutcome, idle, reduce, type Action, type Answer, type Session } from "./session";

const answer: Answer = {
  text: "Yes [1].",
  sources: [{ title: "A", url: "https://x/A" }],
  model_calls: 3,
  tool_calls: 2,
  input_tokens: 10,
  output_tokens: 5,
  seconds: 9.5,
};

const asked: Action = { type: "asked", question: "Who founded the Hellfire Club?" };
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

function check(verdict: string): Action {
  const data = { tool: "check_answer", argument: verdict };
  return { type: "event", event: { event: "call", data } };
}

describe("reduce", () => {
  it("keeps a call and its whole reply as one step", () => {
    const session = run(asked, call, reply);

    expect(session.status).toBe("asking");
    expect(session.trace).toEqual([
      { tool: "search_pages", argument: "Hellfire Club", reply: "1. one\n2. two" },
    ]);
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

  it("keeps the question that was asked", () => {
    expect(run(asked, call).question).toBe("Who founded the Hellfire Club?");
  });

  it("clears the last trace and answer when asking again", () => {
    const again: Action = { type: "asked", question: "Who leads it?" };
    const session = run(asked, call, reply, answered, ended, again);

    expect(session).toEqual({ ...idle, status: "asking", question: "Who leads it?" });
  });
});

describe("checkOutcome", () => {
  function outcome(...actions: Action[]) {
    return checkOutcome(run(...actions).trace);
  }

  it("marks an answer that went out because the check could not run", () => {
    expect(outcome(asked, call, reply, check("unchecked"), answered, ended)).toBe("unchecked");
  });

  it("passes an answer the check found backed, and has nothing to say with no check", () => {
    expect(outcome(asked, call, reply, check("answers"), answered, ended)).toBe("passed");
    expect(outcome(asked, call, reply, answered, ended)).toBeNull();
  });

  it("goes by the check of the answer shown after a retry", () => {
    expect(outcome(asked, call, reply, check("unsupported"), check("unchecked"), answered)).toBe(
      "unchecked",
    );
    expect(outcome(asked, call, reply, check("unsupported"), check("answers"), answered)).toBe(
      "fixed",
    );
  });

  it("reads a verdict only from the answer check's own call", () => {
    const search: Action = {
      type: "event",
      event: { event: "call", data: { tool: "search_text", argument: "unchecked" } },
    };

    expect(outcome(asked, search, answered)).toBeNull();
  });

  it("leaves a refusal after a failed check unmarked", () => {
    const refusal = { ...answer, text: "I couldn't find that in the records.", sources: [] };
    const refused: Action = { type: "event", event: { event: "answer", data: refusal } };

    expect(outcome(asked, call, reply, check("unsupported"), refused)).toBeNull();
  });
});
