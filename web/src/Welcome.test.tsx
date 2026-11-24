import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { EXAMPLES, Welcome } from "./Welcome";

describe("Welcome", () => {
  it("offers each example question as a button", () => {
    const html = renderToStaticMarkup(<Welcome onPick={() => {}} />);

    for (const example of EXAMPLES) {
      expect(html).toContain(`<button type="button">${example.replace(/'/g, "&#x27;")}</button>`);
    }
  });
});
