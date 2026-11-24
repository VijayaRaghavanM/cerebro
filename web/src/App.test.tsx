import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { App } from "./App";

describe("App", () => {
  it("opens on example questions", () => {
    expect(renderToStaticMarkup(<App />)).toContain("Try a question");
  });
});
