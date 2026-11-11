import { afterEach, describe, expect, it, vi } from "vitest";
import { ask, EventParser, type AgentEvent } from "./stream";

const call = 'event: call\ndata: {"tool":"search_pages","argument":"Hellfire Club"}\n\n';
const reply = 'event: reply\ndata: {"tool":"search_pages","text":"1. one\\n2. two"}\n\n';
const answer =
  'event: answer\ndata: {"text":"Yes [1].","sources":[{"title":"A","url":"https://x/A"}],' +
  '"model_calls":3,"tool_calls":2,"input_tokens":10,"output_tokens":5,"seconds":9.5}\n\n';
const failure = 'event: error\ndata: {"message":"model unavailable"}\n\n';

function parseAll(chunks: string[]): AgentEvent[] {
  const parser = new EventParser();
  return chunks.flatMap((chunk) => parser.push(chunk));
}

function streamOf(chunks: Uint8Array[]): ReadableStream<Uint8Array> {
  return new ReadableStream({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(chunk);
      controller.close();
    },
  });
}

function fakeFetch(response: Response) {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response));
}

async function collect(question: string): Promise<AgentEvent[]> {
  const events: AgentEvent[] = [];
  for await (const event of ask(question)) events.push(event);
  return events;
}

afterEach(() => vi.unstubAllGlobals());

describe("EventParser", () => {
  it("reads all four event names", () => {
    const events = parseAll([call + reply + answer + failure]);

    expect(events.map((e) => e.event)).toEqual(["call", "reply", "answer", "error"]);
    expect(events[0].data).toEqual({ tool: "search_pages", argument: "Hellfire Club" });
    expect(events[3].data).toEqual({ message: "model unavailable" });
  });

  it("keeps a newline escaped inside the JSON text", () => {
    const [event] = parseAll([reply]);

    expect(event.data).toEqual({ tool: "search_pages", text: "1. one\n2. two" });
  });

  it("returns several events from one chunk", () => {
    expect(parseAll([call + reply])).toHaveLength(2);
  });

  it("waits for the blank line before emitting", () => {
    const parser = new EventParser();

    expect(parser.push(call.slice(0, -1))).toEqual([]);
    expect(parser.push("\n")).toHaveLength(1);
  });

  it("survives a split at every position", () => {
    const whole = call + reply + answer;

    for (let cut = 1; cut < whole.length; cut++) {
      const events = parseAll([whole.slice(0, cut), whole.slice(cut)]);

      expect(events.map((e) => e.event)).toEqual(["call", "reply", "answer"]);
    }
  });
});

describe("ask", () => {
  it("posts the question as JSON", async () => {
    fakeFetch(new Response(streamOf([])));

    await collect("Who leads the Hellfire Club?");

    const [url, init] = vi.mocked(fetch).mock.calls[0];
    expect(url).toBe("/ask");
    expect(init?.method).toBe("POST");
    expect(JSON.parse(init?.body as string)).toEqual({ question: "Who leads the Hellfire Club?" });
  });

  it("decodes a multi-byte character split across chunks", async () => {
    const bytes = new TextEncoder().encode('event: reply\ndata: {"tool":"t","text":"Café"}\n\n');
    const cut = bytes.indexOf(0xc3) + 1; // between the two bytes of "é"
    fakeFetch(new Response(streamOf([bytes.slice(0, cut), bytes.slice(cut)])));

    const events = await collect("q");

    expect(events[0].data).toEqual({ tool: "t", text: "Café" });
  });

  it("throws the server's detail on a non-2xx reply", async () => {
    const body = JSON.stringify({ detail: "No model key" });
    fakeFetch(new Response(body, { status: 503 }));

    await expect(collect("q")).rejects.toThrow("No model key");
  });

  it("falls back to the status when there is no detail string", async () => {
    fakeFetch(new Response(JSON.stringify({ detail: [{ msg: "too long" }] }), { status: 422 }));

    await expect(collect("q")).rejects.toThrow("422");
  });
});
