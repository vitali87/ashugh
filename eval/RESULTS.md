# Results

Measured on 2026-10-20 with the scripts described in [README.md](README.md).
The raw outputs are in [runs/2026-10-20/](runs/2026-10-20/), the analyzer
benchmarks in its `rifma.json`, `armenian.json` and `oov.json`.

## The analyzer

**Russian stress and rhyme, RIFMA** (5,121 hand-marked poems and stanzas):

| | |
|---|---|
| stress of polysyllabic words (60,856) | 97.0% |
| each word's first reading, without meter or rhyme | 91.8% |
| words the dictionary lists (49,996) | 98.1% |
| ambiguous words resolved by meter and rhyme (3,673) | 94.2% |
| unknown words guessed from the ending, meter and rhyme (5,510) | 88.2% |
| "these two lines rhyme", 33,798 pairs within stanzas | P 0.940, R 0.877, F1 0.907 |

RIFMA was the development set for the Russian rules: the misses it showed
led to the gerund and participle twins, the ending prior, the second
locative and the rhyme-aware stress choice. The rhyme threshold was checked
on it too. In a sweep, 0.70 ("near") was the F1 optimum; at 0.60, recall and
precision were both 0.89.

**Armenian sung syllables** (76 words, one schwa rule each, checked by
hand): ashugh matches all 76. espeak-ng counted 82% of the first 68 words
right. The list was written alongside the rules, so it is a regression
test more than a measurement.

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
three translations into their source's grid). A fresh subagent with no
access to ashugh wrote one draft per task from its brief. Fresh subagents
then answered fit's repair requests through
[agent_bridge.py](agent_bridge.py), one per round.

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

### How often ashugh itself was wrong

The first scoring of the drafts flagged 18 lines. Read one by one, only 4
were the writer's. The other 14 were ashugh's mistakes, and each was fixed in
the analyzer before the numbers above were taken:

| flagged | real | ashugh's mistake | fixed by |
|---|---|---|---|
| everyday drafts: 7 lines | 0 | 7 | a line-final preposition takes the stress (ships gone *by* / sky); *us* is not *U.S.*; the plural года́; кружи́т; participles like спящим |
| hard drafts: 11 lines | 4 | 7 | the possessive ս after a sonorant (բոլորս is բո-լո-րըս); ան- keeps its stem's schwa (ան-շը-տապ); reduplications are separate words (ճիվ-ճիվ); *again* also rhymes with *rain*; Russian pronouns are metrically weak |

The possessive fix also caught a real error the first scoring had missed
(աչքերս above). Before the fixes the drafts scored 133/140 and 185/196
lines (8/12 and 5/12 songs). Those scores measured ashugh's errors more than
the writer's.

### What this does and does not show

- n is small: 24 tasks, one draft each, one writer.
- The writer and the proposers were Claude subagents of the session that
  built ashugh, not calls to the API. They had no access to the code, the
  tool or the conversation, only their briefs and fit's requests.
- The analyzer was corrected on these very drafts, so "Claude alone" is
  scored by a checker that has seen them. Every correction is a general
  rule with its own tests, and the RIFMA and Armenian numbers did not move
  or improved, but a fresh set of drafts would be the cleaner measurement.
- The standard is strict: a lexical stress on a weak beat counts as an
  error even where a singer would get away with it, and an open rhyme
  needs its supporting consonant.
- A frontier model already writes these forms well. On this evidence,
  ashugh's value is less in rescuing bad drafts than in making "every line
  scans" a checked fact instead of a claim, and in fixing the last few
  lines without a human counting syllables.

To rerun with the API: `ashugh eval run eval/tasks-hard` (needs
`ANTHROPIC_API_KEY` and `pip install 'ashugh[claude]'`).
