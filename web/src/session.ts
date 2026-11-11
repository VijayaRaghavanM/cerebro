import type { AgentEvent } from "./stream";

export type Answer = Extract<AgentEvent, { event: "answer" }>["data"];

// `reply` stays null until the tool answers.
export type Step = { label: string; reply: string | null };

export type Session = {
  status: "idle" | "asking" | "done" | "failed";
  trace: Step[];
  answer: Answer | null;
  error: string | null;
};

export type Action =
  | { type: "asked" }
  | { type: "event"; event: AgentEvent }
  | { type: "ended" }
  | { type: "failed"; message: string };

export const idle: Session = {
  status: "idle",
  trace: [],
  answer: null,
  error: null,
};

export function reduce(session: Session, action: Action): Session {
  if (action.type === "asked") {
    return { ...idle, status: "asking" };
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
      const step = { label: `${event.data.tool}: ${event.data.argument}`, reply: null };
      return { ...session, trace: [...session.trace, step] };
    }

    case "reply": {
      // The full text runs to thousands of characters, so only its first line is kept.
      const firstLine = event.data.text.split("\n")[0];
      const trace = [...session.trace];
      const last = trace.length - 1;

      // Tools run one at a time, so a reply belongs to the latest call.
      if (last >= 0) trace[last] = { ...trace[last], reply: firstLine };
      return { ...session, trace };
    }

    case "answer":
      return { ...session, status: "done", answer: event.data };

    case "error":
      return { ...session, status: "failed", error: event.data.message };
  }
}
