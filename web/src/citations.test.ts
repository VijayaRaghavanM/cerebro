import { describe, expect, it } from "vitest";
import { splitCitations } from "./citations";

const sources = [
  { title: "A", url: "https://wiki/A" },
  { title: "B", url: "https://wiki/B" },
];

describe("splitCitations", () => {
  it("links [n] to the nth source", () => {
    expect(splitCitations("One [1] and two [2].", sources)).toEqual([
      { kind: "text", text: "One " },
      { kind: "citation", label: "[1]", url: "https://wiki/A" },
      { kind: "text", text: " and two " },
      { kind: "citation", label: "[2]", url: "https://wiki/B" },
      { kind: "text", text: "." },
    ]);
  });

  it("leaves [?] and numbers without a source as plain text", () => {
    expect(splitCitations("Odd [?] and [3] and [0].", sources)).toEqual([
      { kind: "text", text: "Odd [?] and [3] and [0]." },
    ]);
  });

  it("joins plain text around an unknown marker", () => {
    expect(splitCitations("a [?] b [1]", sources)).toEqual([
      { kind: "text", text: "a [?] b " },
      { kind: "citation", label: "[1]", url: "https://wiki/A" },
    ]);
  });

  it("returns nothing for empty text", () => {
    expect(splitCitations("", sources)).toEqual([]);
  });
});
