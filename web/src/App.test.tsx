import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { App } from "./App";

describe("App", () => {
  it("keeps a live region for screen readers from the start", () => {
    expect(renderToStaticMarkup(<App />)).toContain('aria-live="polite"');
  });

  it("opens on example questions", () => {
    expect(renderToStaticMarkup(<App />)).toContain("Try a question");
  });
});
