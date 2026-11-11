export type Source = { title: string; url: string };

export type AgentEvent =
  | { event: "call"; data: { tool: string; argument: string } }
  | { event: "reply"; data: { tool: string; text: string } }
  | {
      event: "answer";
      data: {
        text: string;
        sources: Source[];
        model_calls: number;
        tool_calls: number;
        input_tokens: number;
        output_tokens: number;
        seconds: number;
      };
    }
  | { event: "error"; data: { message: string } };

// Turns text chunks into complete events. A chunk can end anywhere, so the
// unfinished tail is kept until the blank line that closes its event arrives.
export class EventParser {
  private buffer = "";

  push(chunk: string): AgentEvent[] {
    this.buffer += chunk;

    const blocks = this.buffer.split("\n\n");
    this.buffer = blocks.pop() ?? "";

    return blocks.map(parseBlock);
  }
}

function parseBlock(block: string): AgentEvent {
  let event = "";
  let data = "";

  for (const line of block.split("\n")) {
    if (line.startsWith("event: ")) event = line.slice("event: ".length);
    if (line.startsWith("data: ")) data = line.slice("data: ".length);
  }

  return { event, data: JSON.parse(data) } as AgentEvent;
}

export async function* ask(
  question: string,
  signal?: AbortSignal,
): AsyncGenerator<AgentEvent> {
  const response = await fetch("/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
    signal,
  });

  if (!response.ok) throw new Error(await failureMessage(response));

  // A reader rather than `for await`, which Safari does not offer on a stream.
  const reader = response.body?.getReader();
  if (!reader) throw new Error("The server sent no stream");

  // Streaming mode keeps a multi-byte character that spans two chunks whole.
  const decoder = new TextDecoder();
  const parser = new EventParser();

  while (true) {
    const { done, value } = await reader.read();
    if (done) return;

    yield* parser.push(decoder.decode(value, { stream: true }));
  }
}

async function failureMessage(response: Response): Promise<string> {
  const body = await response.json().catch(() => null);

  // A 422 carries a list of validation problems instead of a string.
  if (typeof body?.detail === "string") return body.detail;
  return `Request failed with status ${response.status}`;
}
