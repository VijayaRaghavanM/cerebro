import type { Source } from "./stream";

// Citations are numbered from 1 in the order of `sources`. A marker with no
// matching source, such as [?], stays as it is. The URL goes in angle brackets
// because wiki URLs contain parentheses, which would end a Markdown link early.
export function linkCitations(text: string, sources: Source[]): string {
  return text.replace(/\[(\d+)\]/g, (marker, number: string) => {
    const source = sources[Number(number) - 1];
    if (!source) return marker;

    return `[\\[${number}\\]](<${source.url}>)`;
  });
}
