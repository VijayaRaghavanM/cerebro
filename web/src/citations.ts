import type { Source } from "./stream";

export type Part =
  | { kind: "text"; text: string }
  | { kind: "citation"; label: string; url: string };

// Citations are numbered from 1 in the order of `sources`. A marker with no
// matching source, such as [?], stays plain text.
export function splitCitations(text: string, sources: Source[]): Part[] {
  const parts: Part[] = [];
  let plain = "";

  for (const piece of text.split(/(\[[^\]]*\])/)) {
    const number = /^\[(\d+)\]$/.exec(piece)?.[1];
    const source = number ? sources[Number(number) - 1] : undefined;

    if (source) {
      if (plain) parts.push({ kind: "text", text: plain });
      plain = "";
      parts.push({ kind: "citation", label: piece, url: source.url });
    } else {
      plain += piece;
    }
  }

  if (plain) parts.push({ kind: "text", text: plain });
  return parts;
}
