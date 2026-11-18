# Golden v2: what changed and why

`golden-v2.jsonl` is `golden.jsonl` with the scoring rules below applied. `golden.jsonl` is unchanged: it is the set the first evaluation was scored on. The ids, questions and splits are the same; 16 questions changed their expected outcome, facts or pages. Every new fact comes from the records, never from an answer.

## The rules

- **R1, first appearance:** a character's first appearance is its page's first appearance field. Where the page marks that comic as retroactive (a later story placed the character there), the first actual appearance is the answer; naming the retcon is welcome, not required.
- **R2, first comics in order:** count only comics whose cast list shows the character in person, by cover date. Cast entries tagged as a mention, a photo, a dream, a vision, behind the scenes and the like do not count; "Shadow only" does. The tag decides, even where the synopsis disagrees. A season counts as its middle month.
- **R3, shared codenames:** a bare codename means its main holder when one Earth-616 page holds more than half of the Earth-616 links with that text; then the answer is about that holder. With no main holder, the right reply is a clarifying question. When the answer is the same whichever holder is meant, a correct answer is right too (`also_accepts`).
- **R4, Comic Vine citations:** citing a character's Comic Vine record counts as citing the wiki page that record is matched to, and no other page. This one is a scoring rule, in `application/scoring.py`, not a label change.
- **R5, judge prompts:** sets how a new judge prompt is chosen; it changes no label.
- **R6, release dates:** "when did it come out" is answered by the cover date or the release date, if it matches the record.
- **R7, a first comic:** "the first X comic" of a team or a title is answered by its debut or by issue #1 of the series named after it, if the answer says which.

## The changes

### g030 (R6): Who debuted first, Namor or Captain America?

- Was: `{"expected_facts": ["Namor", "1939", "1941"]}`
- Now: `{"expected_facts": ["Namor", "1939", "1941 (cover date) or 1940 (release date)"]}`
- Record: Captain America Comics Vol 1 1: release_date "December 20, 1940", cover March 1941; Namor first_appearance Motion Picture Funnies Weekly Vol 1 1 (1939)

### g039 (R6): Who debuted first, the Hulk or Spider-Man?

- Was: `{"expected_facts": ["Hulk", "May 1962", "August 1962"]}`
- Now: `{"expected_facts": ["Hulk", "May 1962 (cover date) or March 1, 1962 (release date)", "August 1962 (cover date) or June 5, 1962 (release date)"]}`
- Record: Incredible Hulk Vol 1 1: release_date "March 1, 1962", cover May 1962; Amazing Fantasy Vol 1 15: release_date "June 5, 1962", cover August 1962

### g055 (R1): Did all four original Fantastic Four members first appear in Fantastic Four #1?

- Was: `{"expected_facts": ["Reed Richards", "Amazing Adult Fantasy Vol 1 7"]}`
- Now: `{"expected_facts": ["Yes", "Fantastic Four Vol 1 1"]}`
- Record: Reed Richards first_appearance: "Amazing Adult Fantasy Vol 1 7", note "(Retroactively) Fantastic Four Vol 1 1 (First actual appearance)"; the retcon is welcome, not required

### g081 (R2): In publication order by cover date, what are Thanos's first four comic appearances?

- Was: `{"expected_facts": ["Iron Man 55", "Captain Marvel 26", "Captain Marvel 27", "Captain Marvel 28"]}`
- Now: `{"expected_facts": ["Iron Man 55", "Captain Marvel 25", "Captain Marvel 26", "Captain Marvel 27"]}`
- Record: Captain Marvel Vol 1 25 (March 1973) cast: "Masterlord (Thanos) (Shadow only)"; a character seen only in shadow is on the page, so it counts

### g082 (R2): What are Deadpool's first three comic appearances, in order of cover date?

- Was: `{"expected_facts": ["New Mutants 98", "X-Force 2", "X-Force 4"]}`
- Now: `{"expected_facts": ["New Mutants 98", "X-Force 2", "X-Force 5"]}`
- Record: X-Force Vol 1 4 cast: "Deadpool (Behind the scenes)"; the cast tag decides. Next in person: X-Force Vol 1 5 (December 1991)

### g088 (R2): What are Daredevil's first four comic appearances, in order of cover date?

- Was: `{"expected_facts": ["Daredevil 1", "Daredevil 2", "Daredevil 3", "Amazing Spider-Man Annual 1"]}`
- Now: `{"expected_facts": ["Daredevil 1", "Daredevil 2", "Daredevil 3", "Amazing Spider-Man 16"]}`
- Record: Amazing Spider-Man Annual Vol 1 1 (October 1964) cast: "Daredevil (Matt Murdock) (Mentioned in narration or thoughts)" and "(Vision or hallucination)"; Amazing Spider-Man Vol 1 16 (September 1964) cast: "Daredevil (Matt Murdock)"

### g109 (R3): Who is Nova?

- Was: `{"expected_outcome": "clarify", "expected_facts": ["Richard Rider", "Samuel Alexander"], "expected_pages": ["Richard Rider (Earth-616)", "Samuel Alexander (Earth-616)"]}`
- Now: `{"expected_outcome": "answer", "expected_facts": ["Richard Rider"], "expected_pages": ["Richard Rider (Earth-616)"]}`
- Record: Earth-616 links with the text "nova": Richard Rider 344 of 475 (72%)

### g110 (R3): Who is Ant-Man?

- Was: `{"expected_outcome": "clarify", "expected_facts": ["Henry Pym", "Scott Lang"], "expected_pages": ["Henry Pym (Earth-616)", "Scott Lang (Earth-616)"]}`
- Now: `{"expected_outcome": "answer", "expected_facts": ["Scott Lang"], "expected_pages": ["Scott Lang (Earth-616)"]}`
- Record: Earth-616 links with the text "ant-man": Scott Lang 240 of 376 (64%)

### g111 (R3): Who is Spider-Woman?

- Was: `{"expected_outcome": "clarify", "expected_facts": ["Jessica Drew", "Martha Franklin", "Charlotte Witter"], "expected_pages": ["Jessica Drew (Earth-616)", "Martha Franklin (Earth-616)", "Charlotte Witter (Earth-616)"]}`
- Now: `{"expected_outcome": "answer", "expected_facts": ["Jessica Drew"], "expected_pages": ["Jessica Drew (Earth-616)"]}`
- Record: Earth-616 links with the text "spider-woman": Jessica Drew 404 of 558 (72%)

### nq009 (R7, R6): When did the first Guardians of the Galaxy comic come out?

- Was: `{"expected_facts": ["Marvel Super-Heroes Vol 1 18", "January 1969"], "expected_pages": ["Guardians of the Galaxy (Earth-691)", "Marvel Super-Heroes Vol 1 18"]}`
- Now: `{"expected_facts": ["Marvel Super-Heroes Vol 1 18, cover January 1969 (released October 15, 1968), the debut; or Guardians of the Galaxy Vol 1 1, cover June 1990 (released April 17, 1990), the first issue of its own series; either, if the answer says which"], "expected_pages": ["Guardians of the Galaxy (Earth-691)", "Marvel Super-Heroes Vol 1 18", "Guardians of the Galaxy Vol 1 1"]}`
- Record: Marvel Super-Heroes Vol 1 18: release_date "October 15, 1968", cover January 1969; Guardians of the Galaxy Vol 1 1: release_date "April 17, 1990", cover June 1990

### nq010 (R6): When was the Black Panther Marvel character created?

- Was: `{"expected_facts": ["Fantastic Four Vol 1 52", "July 1966"]}`
- Now: `{"expected_facts": ["Fantastic Four Vol 1 52", "July 1966 (cover date) or April 12, 1966 (release date)"]}`
- Record: Fantastic Four Vol 1 52: release_date "April 12, 1966", cover July 1966

### nq015 (R6): When did Spider-Man first appear in comics?

- Was: `{"expected_facts": ["Amazing Fantasy", "August 1962"]}`
- Now: `{"expected_facts": ["Amazing Fantasy", "August 1962 (cover date) or June 5, 1962 (release date)"]}`
- Record: Amazing Fantasy Vol 1 15: release_date "June 5, 1962", cover August 1962

### nq016 (R6): When did the Captain America comic come out?

- Was: `{"expected_facts": ["Captain America Comics Vol 1 1", "March 1941"]}`
- Now: `{"expected_facts": ["Captain America Comics Vol 1 1", "March 1941 (cover date) or December 20, 1940 (release date)"]}`
- Record: Captain America Comics Vol 1 1: release_date "December 20, 1940", cover March 1941

### nq018 (R7, R6): When did the first Black Panther comic come out?

- Was: `{"expected_outcome": "clarify", "expected_facts": ["July 1966", "January 1977"]}`
- Now: `{"expected_outcome": "answer", "expected_facts": ["Fantastic Four Vol 1 52, cover July 1966 (released April 12, 1966), the debut; or Black Panther Vol 1 1, cover January 1977 (released October 19, 1976), the first issue of its own series; either, if the answer says which"]}`
- Record: Fantastic Four Vol 1 52: release_date "April 12, 1966", cover July 1966; Black Panther Vol 1 1: release_date "October 19, 1976", cover January 1977

### nq019 (R7, R6): When was the first Iron Man comic released?

- Was: `{"expected_outcome": "clarify", "expected_facts": ["Tales of Suspense Vol 1 39", "Iron Man Vol 1 1"]}`
- Now: `{"expected_outcome": "answer", "expected_facts": ["Tales of Suspense Vol 1 39, cover March 1963 (released December 10, 1962), the debut; or Iron Man Vol 1 1, cover May 1968 (released February 1, 1968), the first issue of its own series; either, if the answer says which"]}`
- Record: Tales of Suspense Vol 1 39: release_date "December 10, 1962", cover March 1963; Iron Man Vol 1 1: release_date "February 1, 1968", cover May 1968

### nq020 (R3): Who came first, Captain Marvel or Captain America?

- Was: `{"expected_outcome": "clarify", "expected_facts": ["Captain America Comics Vol 1 1", "Marvel Super-Heroes Vol 1 12"]}`
- Now: `{"expected_outcome": "answer", "expected_facts": ["Captain America came first", "Captain America Comics Vol 1 1 (1941)"], "also_accepts": ["clarify"]}`
- Record: Captain America Comics Vol 1 1: cover March 1941; every Earth-616 holder of "captain marvel" debuted later (Mar-Vell: Marvel Super-Heroes Vol 1 12, December 1967), so the answer is the same whichever is meant, and asking which one is right too
