import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { idle, type Session } from "./session";
import { Timeline } from "./Timeline";

const reply = '1. "Roberto Da Costa (Earth-616)": character\n2. "Sunspot Vol 1 1": comic';

function render(session: Session) {
  return renderToStaticMarkup(<Timeline session={session} />);
}

describe("Timeline", () => {
  it("lets a finished step open to show the tool's whole reply", () => {
    const session: Session = {
      ...idle,
      status: "asking",
      trace: [{ tool: "search_pages", argument: "Sunspot", reply }],
    };
    const html = render(session);

    expect(html).toContain("<details");
    expect(html).toContain("2. &quot;Sunspot Vol 1 1&quot;: comic</pre>");
  });

  it("shows a running step with nothing to open", () => {
    const session: Session = {
      ...idle,
      status: "asking",
      trace: [{ tool: "read_page", argument: "Thanos (Earth-616)", reply: null }],
    };
    const html = render(session);

    expect(html).toContain("Reading");
    expect(html).not.toContain("<details");
    expect(html).not.toContain("Working out the next step");
  });

  it("shows the model at work between tools", () => {
    const session: Session = {
      ...idle,
      status: "asking",
      trace: [{ tool: "search_pages", argument: "Sunspot", reply }],
    };

    expect(render(session)).toContain("Working out the next step");
    expect(render({ ...session, status: "done" })).not.toContain("Working out the next step");
  });

  it("shows the note of a check that found a problem", () => {
    const note = "No source names the penciler.";
    const session: Session = {
      ...idle,
      status: "asking",
      trace: [{ tool: "check_answer", argument: "unsupported", reply: note }],
    };

    expect(render(session)).toContain(note);
  });
});
