import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { Result } from "./Result";
import type { Answer, CheckOutcome } from "./session";

const answer: Answer = {
  text: "Jim Starlin penciled it [1].",
  sources: [{ title: "Iron Man Vol 1 55", url: "https://wiki/Iron_Man_Vol_1_55" }],
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
});
