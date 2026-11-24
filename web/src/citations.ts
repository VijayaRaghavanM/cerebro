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

export type Origin = { kind: "wiki" | "comicvine"; site: string; name: string };

const COMIC_VINE = "Comic Vine: ";

// Comic Vine records come titled "Comic Vine: Wolverine"; every other source is a
// Marvel Database wiki page.
export function origin(title: string): Origin {
  if (!title.startsWith(COMIC_VINE)) return { kind: "wiki", site: "Marvel Database", name: title };

  return { kind: "comicvine", site: "Comic Vine", name: title.slice(COMIC_VINE.length) };
}
