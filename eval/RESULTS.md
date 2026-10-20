# Results

Measured on 2026-10-20 with the scripts described in [README.md](README.md).
The raw outputs are in [runs/2026-10-20/](runs/2026-10-20/), the analyzer
benchmarks in its `rifma.json`, `armenian.json`, `wikipron.json` and `oov.json`.

## The analyzer

**Russian stress and rhyme, RIFMA** (5,121 hand-marked poems and stanzas):

| | |
|---|---|
| stress of polysyllabic words (60,856) | 97.0% |
| each word's first reading, without meter or rhyme | 91.8% |
| words the dictionary lists (49,981) | 98.1% |
| ambiguous words resolved by meter and rhyme (3,688) | 94.2% |
| unknown words guessed from the ending, meter and rhyme (5,510) | 88.1% |
| "these two lines rhyme", 33,798 pairs within stanzas | P 0.941, R 0.875, F1 0.907 |

RIFMA was the development set for the Russian rules: the misses it showed
led to the gerund and participle twins, the ending prior, the second
locative and the rhyme-aware stress choice. The rhyme threshold was checked
on it too. In a sweep, 0.70 ("near") was the F1 optimum; at 0.60, recall and
precision were both 0.89.

**Armenian sung syllables** (81 words, one schwa rule each, checked by
hand): ashugh matches all 81. espeak-ng counted 82% of the first 68 words
right. The list was written alongside the rules, so it is a regression
test more than a measurement.

**Armenian against Wiktionary** (WikiPron's scrape of Wiktionary's Eastern
Armenian pronunciations: 18,090 entries, 17,736 words). ashugh's two word
lists, stems whose final ս or դ is their own and compounds that keep a
root's schwa, come from the same data, so they are rebuilt without every
tenth word and ashugh is scored on those 1,768. A word Wiktionary
transcribes more than one way (կերակրել with and without its root's schwa)
matches when ashugh agrees with any of them.

| | before the lists | now |
|---|---|---|
| sung syllables equal Wiktionary's vowels | 91.2% | **91.4%** |
| the same, on the 309 words Wiktionary writes with a schwa | 84.1% | **86.7%** |

The 152 disagreements left, by kind:

| kind | words | mostly |
|---|---|---|
| a schwa at the start | 55 | Wiktionary writes none in loanwords and names (բրիգադ, ֆլեշմոբ, Պլեթոն) or before ս and a stop (սպանուհի), where ashugh sings one |
| a schwa at the end | 38 | rising clusters of loanwords that Wiktionary writes closed (ռազմ, նուդիզմ, մետաքս), and -րդ stems the held-out list lacks (նյարդ, Ալվարդ) |
| a vowel letter | 32 | Wiktionary reads ի before a vowel as a glide (դանիացի as dɑnjɑtsʰi); sung verse gives it a syllable |
| a schwa inside | 27 | compounds whose beginning no listed word shares (աստ-ղա-գը-նաց) |

Wiktionary transcribes speech, not singing, so this is agreement rather than
accuracy. The comparison gave ashugh three things:

- two rules: a word does not end in մն or ռն (ու-րե-մըն, սա-ռըն, as in 19
  of 21 entries), and a final դ after ր is the possessive (սե-րըդ, your
  love). Dictionary forms never carry the possessive, so this test shows
  what the second costs (the -րդ stems the held-out list lacks) and not what
  it gains;
- 296 stems whose final ս or դ is their own (ադամանդ, մաքս, ժողովուրդ);
- 253 word beginnings that keep a compound root's schwa (մեղադր-, so
  մե-ղա-դը-րել, մե-ղա-դը-րան-քը), each kept only if it breaks no entry the
  rules read right. On the held-out words they fixed 8 and broke none.
  Speech often drops this schwa (Wiktionary gives both forms for 193
  words), so a line may sing it or not, as with the schwas of connected
  speech.

In the eval's Armenian drafts (2,919 words) only three words read
differently: լեռն and սառն gain their schwa, which connected speech still
lets fit, and լուսանկարներ (lu-sa-nə-kar-ner) gains an optional one. Every
draft scores the same.

**Words outside the dictionaries** (every tenth entry held out):

| | ashugh | baseline (commonest position) |
|---|---|---|
| Russian stress (55,255 words) | 75.7% | 40.8% |
| English stress (9,405) | 77.0% | 66.7% |
| English syllables from spelling (11,748) | 87.7% | |

## Claude alone and Claude with ashugh

Twenty-four tasks: twelve everyday forms (`tasks/`) and twelve harder ones
(`tasks-hard/`: per-line melody grids with set endings, a different form for
the chorus, ternary meters, Armenian trochees and feminine endings, and
three translations into their source's grid). Fresh subagents with no
access to ashugh wrote the drafts from the briefs; fresh subagents then
answered fit's repair requests through [agent_bridge.py](agent_bridge.py),
one per round.

### The measurement: two holdouts, analyzer frozen

Both holdout sets were written after the analyzer was frozen, and scored and
repaired with that frozen analyzer; nothing was fixed until both steps had
run. These are the numbers to quote:

| | lines meeting the spec | songs meeting the spec |
|---|---|---|
| holdout 1 (24 drafts, frozen at 268da1e), alone | 479 / 482 | 21 / 24 |
| holdout 2 (48 drafts, frozen at 5c2962f), alone | 985 / 1,000 | 42 / 48 |
| **both, Claude alone** | **1,464 / 1,482 (98.8%)** | **63 / 72** |
| **both, Claude with ashugh** | **1,482 / 1,482** | **72 / 72** |

Of the 18 lines the frozen checkers flagged, 4 were real errors and 14
were the checker's own mistakes; fit repaired all 18 in one round, the 14
needlessly but without losing the meaning. Both sets are detailed below.

### The development set

The first 24 drafts were scored while the analyzer was still being
corrected, and its rules were fixed on them, so they are a development set:
their "alone" numbers are from a checker that has seen them.

| | lines meeting the spec | songs meeting the spec |
|---|---|---|
| everyday forms, Claude alone | 139 / 140 (99.3%) | 11 / 12 |
| everyday forms, Claude with ashugh | **140 / 140** | **12 / 12** |
| hard forms, Claude alone | 192 / 196 (98.0%) | 9 / 12 |
| hard forms, Claude with ashugh | **196 / 196** | **12 / 12** |

The repair took 8 requests over at most two rounds and changed 5 lines (4
distinct lines; one chorus line repeats):

| task | as written | after fit | what was wrong |
|---|---|---|---|
| hy-night-city | Աչքերս քո ճամփին են այստեղ | Աչքերս ճամփիդ են այստեղ | 9 syllables in an 8 slot: աչքերս is աչ-քե-րըս |
| en-night-train (×2) | Through the dark where the wild grasses sway | Through the dark where the grasses all sway | *gras-* stressed on a weak beat of the anapest |
| en-waltz | Tied to the rail where the last couple stayed | Tied to the rail by the couple who stayed | *cou-* stressed on a weak beat of the dactyl |
| hy-wedding | Մեր բակում մեծ հարսանիք կա | Մեր բակում մեծ հարսանիք, հա | կա / ահա lacks the consonant an open rhyme needs; the fix pads with the interjection հա |

The errors that survive a careful model are the ones it cannot hear: an
Armenian schwa it does not write, a lexical stress landing on the weak slot
of a three-syllable foot, an open rhyme whose consonants differ. ashugh finds
them, and one or two rounds of candidates fix them.

### How often ashugh was wrong on the development set

The first scoring of the drafts flagged 18 lines. Read one by one, only 4
were the writer's. The other 14 were ashugh's mistakes, and each was fixed in
the analyzer before the numbers above were taken:

| flagged | real | ashugh's mistake | fixed by |
|---|---|---|---|
| everyday drafts: 7 lines | 0 | 7 | a line-final preposition takes the stress (ships gone *by* / sky); *us* is not *U.S.*; the plural года́; кружи́т; participles like спящим |
| hard drafts: 11 lines | 4 | 7 | the possessive ս after a sonorant (բոլորս is բո-լո-րըս); ան- keeps its stem's schwa (ան-շը-տապ); reduplications are separate words (ճիվ-ճիվ); *again* also rhymes with *rain*; Russian pronouns are metrically weak |

The possessive fix also caught a real error the first scoring had missed
(աչքերս above). A second code review after these runs fixed more analyzer
bugs; rescoring every draft and every repaired text with the final analyzer
gave the same numbers. Before the fixes the drafts scored 133/140 and 185/196
lines (8/12 and 5/12 songs). Those scores measured ashugh's errors more than
the writer's.

### Holdout 1

Because the analyzer was corrected on the drafts above, a second set was
written afterwards: new cold writers, the same 24 briefs, drafts in
[runs/2026-10-20/holdout/](runs/2026-10-20/holdout/). They were scored at
commit 268da1e and the analyzer was not touched until the repair had run.

| | lines meeting the spec | songs meeting the spec |
|---|---|---|
| everyday forms, Claude alone | 321 / 322 (99.7%) | 11 / 12 |
| everyday forms, Claude with ashugh | **322 / 322** | **12 / 12** |
| hard forms, Claude alone | 158 / 160 (98.8%) | 10 / 12 |
| hard forms, Claude with ashugh | **160 / 160** | **12 / 12** |

One round of repair, three changed lines:

| task | as written | after fit | flag was |
|---|---|---|---|
| hy-translate-dickinson | Ու ես թողել էի | Ու արդեն թողեցի | right: թողել էի ends on the unstressed auxiliary, so it does not rhyme with գթի |
| ru-road | Нет пути милей на свете | Лучше нет пути на свете | wrong: миле́й (dearer) was read as ми́лей (of miles) |
| en-translate-pushkin | Through restless bustle's noisy race | Amid the clamor's restless race | wrong: *bustle's* was counted as one syllable |

Of the three lines the frozen checker flagged, one was a real error and
two were its own mistakes; fit rewrote those two without harm to the
meaning, but they did not need it. The mistakes were fixed afterwards
(the -ее twin of a short comparative, the possessive *'s* and the *-les*
ending of English). As a regression check, not a measurement: with the fixed
analyzer the same drafts raise only the one real flag.

### Holdout 2

Four further cold writers wrote two more drafts per task (48 drafts, 1,000
lines, in [runs/2026-10-20/holdout2/](runs/2026-10-20/holdout2/)). They were
scored, and repaired, with the analyzer frozen at commit 5c2962f, run from a
separate worktree while later work went on.

| | lines meeting the spec | songs meeting the spec |
|---|---|---|
| Claude alone | 985 / 1,000 (98.5%) | 42 / 48 |
| Claude with ashugh | **1,000 / 1,000** | **48 / 48** |

Read one by one, the 15 flagged lines were 3 real errors and 12 false
alarms:

| flagged | real? | after fit |
|---|---|---|
| hy-mother: Ոչ ոք չի սիրում ինձ քեզ պես, against …անցել ես | yes: the rhyme falls on an unstressed auxiliary | Ինձ ամենից շատ սիրել ես |
| en-waltz: One final waltz, and the evening is done | yes: *fi-* on a weak beat of the dactyl | Last of the waltzes, the evening is done |
| ru-troika: Рядом ты, моя милая, нежная | yes, by the strict standard: an adverb stressed on the anacrusis | Ты со мной, моя милая, нежная |
| ru-troika: Только сердце навеки с тобой | no: только is a particle, metrically weak | Но лишь сердце навеки с тобой |
| ru-winter (7 lines): кружится | no: кружи́тся was missing, only кру́жится was listed | клубится |
| hy-lullaby (3 lines): Աչուկներդ փակիր | no: after the plural -եր, դ is the possessive (ա-չուկ-նե-րըդ, 6 syllables) | Դու աչուկներդ փակիր |
| ru-grid-call: …номер искрится | no: the table has и́скрится for искри́тся | …номер лучится |

The false alarms were fixed afterwards. As a regression check, not a
measurement: with the fixed analyzer the same drafts raise only the three
real flags.

### What this does and does not show

- The measurement is 72 holdout drafts of 24 tasks from six writers; the
  first 24 drafts, from a seventh, are the development set.
- The writers and the proposers were Claude subagents of the session that
  built ashugh, not calls to the API. They had no access to the code, the
  tool or the conversation, only their briefs and fit's requests.
- The development set's "alone" numbers come from a checker corrected on
  those drafts; the holdouts' come from frozen ones. They agree: Claude
  alone meets these forms in 98–100% of lines.
- On fresh drafts, most flags were ashugh's own mistakes: 2 of 3 on
  holdout 1, 12 of 15 on holdout 2, and 14 of 18 on the first set before
  its fixes. Real errors were rare (3 in 1,000 lines on holdout 2). A
  false flag costs a needless rewrite, which fit made without losing the
  meaning; each one also pointed at a dictionary gap or a rule worth
  fixing, and was fixed with a test.
- The standard is strict: a lexical stress on a weak beat counts as an
  error even where a singer would get away with it, and an open rhyme
  needs its supporting consonant.
- A frontier model already writes these forms well. On this evidence,
  ashugh's value is less in rescuing bad drafts than in making "every line
  scans" a checked fact instead of a claim, and in fixing the last few
  lines without a human counting syllables. In every set, every song met
  its spec after fit.

To rerun with the API: `ashugh eval run eval/tasks-hard` (needs
`ANTHROPIC_API_KEY` and the claude extra: `uv sync --extra claude`).
