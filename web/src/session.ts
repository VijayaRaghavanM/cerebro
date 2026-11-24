import type { AgentEvent } from "./stream";

export type Answer = Extract<AgentEvent, { event: "answer" }>["data"];

// `reply` stays null until the tool answers. It keeps the tool's whole text, which
// can run to thousands of characters, so a step can be opened to read it.
export type Step = { tool: string; argument: string; reply: string | null };

// The answer check comes through the stream as a step of its own.
export function isCheck(step: Step): boolean {
  return step.tool === "check_answer";
}

export type Session = {
  status: "idle" | "asking" | "done" | "failed";
  // Kept apart from the input, which can change while the run streams.
  question: string;
  trace: Step[];
  answer: Answer | null;
  error: string | null;
};

export type Action =
  | { type: "asked"; question: string }
  | { type: "event"; event: AgentEvent }
  | { type: "ended" }
  | { type: "failed"; message: string };

export const idle: Session = {
  status: "idle",
  question: "",
  trace: [],
  answer: null,
  error: null,
};

export function reduce(session: Session, action: Action): Session {
  if (action.type === "asked") {
    return { ...idle, status: "asking", question: action.question };
  }

  if (action.type === "failed") {
    return { ...session, status: "failed", error: action.message };
  }

  if (action.type === "ended") {
    // A stream that closes with neither an answer nor an error was cut off.
    if (session.status !== "asking") return session;
    return { ...session, status: "failed", error: "The server stopped before it answered." };
  }

  return reduceEvent(session, action.event);
}

function reduceEvent(session: Session, event: AgentEvent): Session {
  switch (event.event) {
    case "call": {
      const step = { tool: event.data.tool, argument: event.data.argument, reply: null };
      return { ...session, trace: [...session.trace, step] };
    }

    case "reply": {
      const trace = [...session.trace];
      const last = trace.length - 1;

      // Tools run one at a time, so a reply belongs to the latest call.
      if (last >= 0) trace[last] = { ...trace[last], reply: event.data.text };
      return { ...session, trace };
    }

    case "answer":
      return { ...session, status: "done", answer: event.data };

    case "error":
      return { ...session, status: "failed", error: event.data.message };
  }
}

// What the check found about the answer shown. "fixed" means it sent a first
// answer back and passed the second. Null when no check ran, or when a problem
// stood, since the reply shown is then the refusal or another non-answer.
export type CheckOutcome = "passed" | "fixed" | "unchecked" | null;

export function checkOutcome(trace: Step[]): CheckOutcome {
  // The verdict comes as the check's argument. After a retry, the second check
  // speaks for the answer that is shown.
  const verdicts = trace.filter(isCheck).map((step) => step.argument);
  const last = verdicts.at(-1);

  if (last === "unchecked") return "unchecked";
  if (last === "answers") return verdicts.length > 1 ? "fixed" : "passed";
  return null;
}
