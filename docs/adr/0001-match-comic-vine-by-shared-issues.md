# 1. Match Comic Vine characters by shared issues

- **Date:** 2026-11-11
- **Status:** accepted

## Decision

Match a Comic Vine character to the Fandom page whose appearances overlap most with its issues.

1. Find each of its issues on Fandom: the one comic page with the same series, number and cover year.
2. The candidates are the character pages in those comics' cast lists that share a name word with the character.
3. A whole shared name ranks first, then the highest overlap, `shared / (found + appearances - shared)`, where `found` counts the character's issues found on Fandom and `appearances` the comics that list the page. A tie at the top means no match.

For now this covers the 300 Comic Vine characters that have an issue list.

## Reasoning

- **Names alone can't decide.** Fandom has a page for every version of a character, titled by real name and reality. 645 pages are named Wolverine, 16 of them on Earth-616, and each of the 300 shares a whole name with a median of 66 pages.
- **Shared issues over first appearances.** Famous characters have many versions with the same name, and the two sites often disagree on first appearances. Matching on first appearance left 40 of the top 300 unmatched and sent others to alternate versions. Shared issues match all 300.
- **Names as a filter.** Without them, a character with a few issues loses to henchmen who appear in every one. An exact name would lose pages the two sites name differently, so a shared word qualifies a page and a whole name ranks it higher.
- **Jaccard overlap.** A raw count of shared issues lets the busiest co-star win, so Wolverine would take every minor X-Men character.
- **Only 300 for now.** Comic Vine returns full detail one character per call, at about 200 calls an hour. The other 23,027 would take about five days, and their bulk data adds little to Fandom. A later enrichment phase can fetch them.
- **No tuned thresholds**, so the rule works unchanged when that data arrives.
- **Weak spot.** The rule can pick the wrong one of two characters who share nearly all their issues and a name word.
