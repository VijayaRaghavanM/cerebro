import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { Result } from "./Result";
import type { Answer, CheckOutcome } from "./session";

const answer: Answer = {
  text: "Jim Starlin penciled it [1].",
  sources: [
    { title: "Iron Man Vol 1 55", url: "https://wiki/Iron_Man_Vol_1_55" },
    { title: "Comic Vine: Thanos", url: "https://comicvine/thanos" },
  ],
  model_calls: 4,
  tool_calls: 3,
  input_tokens: 9614,
  output_tokens: 65,
  seconds: 14.2,
};

function render(check: CheckOutcome) {
  return renderToStaticMarkup(<Result answer={answer} check={check} />);
}

describe("Result", () => {
  it("says how the answer check went", () => {
    expect(render("passed")).toContain("Checked against the records.");
    expect(render("fixed")).toContain("Checked against the records on the second try.");
    expect(render("unchecked")).toContain("Not double-checked.");
  });

  it("shows no check when none ran", () => {
    expect(render(null)).not.toContain("check-banner");
  });

  it("names the site of each source and drops Comic Vine's title prefix", () => {
    const html = render(null);

    expect(html).toContain('>Iron Man Vol 1 55</span><span class="site is-wiki">Marvel Database<');
    expect(html).toContain('>Thanos</span><span class="site is-comicvine">Comic Vine<');
  });

  it("sets a refusal apart from an answer, with no sources", () => {
    const refusal = { ...answer, text: "I couldn't find that in the records.", sources: [] };
    const html = renderToStaticMarkup(<Result answer={refusal} check={null} />);

    expect(html).toContain(">No answer</h3>");
    expect(html).toContain("gives no answer when that doesn&#x27;t settle the question");
    expect(html).not.toContain("Sources");
    expect(render(null)).toContain(">Answer</h3>");
  });
});
