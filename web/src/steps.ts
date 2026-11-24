import type { Session, Step } from "./session";
import { REFUSAL } from "./stream";

// The words before a tool's argument, while it runs and once it is done. Searches
// take words to look for, which read best in quotes; the other tools take titles.
type Wording = { running: string; done: string; quoted: boolean };

const WORDING: Record<string, Wording> = {
  search_pages: {
    running: "Searching page names for",
    done: "Searched page names for",
    quoted: true,
  },
  search_text: { running: "Searching passages for", done: "Searched passages for", quoted: true },
  read_page: { running: "Reading", done: "Read", quoted: false },
  find_appearances: {
    running: "Finding the comics that feature",
    done: "Found the comics that feature",
    quoted: false,
  },
  reading_order: {
    running: "Building the reading order for",
    done: "Built the reading order for",
    quoted: false,
  },
  compare_characters: { running: "Comparing", done: "Compared", quoted: false },
};

export type ToolView = {
  action: string;
  quoted: boolean;
  // What the reply found, in a line; null when the records say it better.
  finding: string | null;
  // Titles the reply offers the model as sources it may cite, other than the one
  // the step already names.
  records: string[];
};

export type CheckView = {
  title: string;
  finding: string;
  tone: "passed" | "problem" | "unchecked";
  // What happened to the answer because of the check, when it found a problem.
  next: string | null;
};

// A tool that cites pages ends its reply with them: "Sources: [1] A, [2] B".
const SOURCES = /\n\nSources: (\[\d+\] .*)$/;
const NUMBER = /^\[\d+\] /;
// search_pages lists its hits as `1. "Title": character`.
const HIT = /^\d+\. "(.+)": /;
// A page read opens with its title and kind: "Thanos (Earth-616) (character)".
const KIND = / \((character|team|comic)\)$/;
const KINDS: Record<string, string> = {
  character: "Character page",
  team: "Team page",
  comic: "Comic page",
};

export function describeTool(step: Step, running: boolean): ToolView {
  const wording = WORDING[step.tool] ?? { running: step.tool, done: step.tool, quoted: false };
  const action = running ? wording.running : wording.done;
  if (step.reply === null) return { action, quoted: wording.quoted, finding: null, records: [] };

  const sources = step.reply.match(SOURCES);
  const body = sources ? step.reply.slice(0, sources.index) : step.reply;
  // Split only before a number, as titles can hold commas of their own.
  const labels = sources ? sources[1].split(/, (?=\[\d+\] )/) : [];
  const titles = [...new Set(labels.map((label) => label.replace(NUMBER, "")))];
  const records = titles.filter((title) => title !== step.argument);

  return { action, quoted: wording.quoted, finding: finding(step.tool, body, records), records };
}

function finding(tool: string, body: string, records: string[]): string | null {
  const lines = body.split("\n");
  const hits = lines.flatMap((line) => line.match(HIT)?.[1] ?? []);

  if (tool === "search_pages" && hits.length === 1) return `Found 1 page: ${hits[0]}`;
  if (tool === "search_pages" && hits.length > 1) {
    return `Found ${hits.length} pages, starting with ${hits[0]}`;
  }
  if (tool === "search_text" && records.length > 0) {
    return `Found passages on ${plural(records.length, "page")}`;
  }

  const kind = lines[0].match(KIND)?.[1];
  if (tool === "read_page" && kind) return KINDS[kind];
  // Two pages compared are named by their records.
  if (tool === "compare_characters" && records.length > 0) return null;

  // Otherwise the first line says what came back; a list's heading ends in a colon.
  return lines[0].replace(/:$/, "");
}

// The check's verdict comes as its argument and its note, when it found a problem,
// as its reply. A problem gets one more try, and a second one withholds the answer.
export function describeCheck(step: Step, afterRetry: boolean): CheckView {
  const next = afterRetry ? "The answer was withheld" : "Sent back to try once more";

  switch (step.argument) {
    case "answers":
      return {
        title: "Checked the answer",
        finding: "Every claim is backed by the records Cerebro read",
        tone: "passed",
        next: null,
      };
    case "unsupported":
      return {
        title: "Checked the answer",
        finding: "Found a claim the records don't back",
        tone: "problem",
        next,
      };
    case "off_target":
      return {
        title: "Checked the answer",
        finding: "Found that the answer misses the question",
        tone: "problem",
        next,
      };
    case "unchecked":
      return {
        title: "Tried to check the answer",
        finding: "The check couldn't run, so the answer went out as it was",
        tone: "unchecked",
        next: null,
      };
    default:
      return { title: "Checked the answer", finding: step.argument, tone: "unchecked", next: null };
  }
}

// True while the latest tool is still working. A check arrives with its verdict,
// so the run is never waiting on one.
export function waitingOnTool(session: Session): boolean {
  const last = session.trace.at(-1);
  if (session.status !== "asking" || last === undefined) return false;

  return last.tool !== "check_answer" && last.reply === null;
}

// One line on where the run is, for screen readers: the step under way or just
// finished, then the outcome. A failure speaks for itself as an alert.
export function progress(session: Session): string {
  if (session.status === "done") {
    return session.answer?.text === REFUSAL ? "No answer in the records" : "Answer ready";
  }

  const last = session.trace.at(-1);
  if (session.status !== "asking" || last === undefined) return "";

  if (last.tool === "check_answer") {
    const afterRetry = session.trace.slice(0, -1).some((step) => step.tool === "check_answer");
    const check = describeCheck(last, afterRetry);
    return [check.title, check.finding, check.next].filter(Boolean).join(". ");
  }

  const tool = describeTool(last, waitingOnTool(session));
  return [`${tool.action} ${last.argument}`, tool.finding].filter(Boolean).join(". ");
}

function plural(count: number, word: string): string {
  return `${count} ${word}${count === 1 ? "" : "s"}`;
}
