# Results

Measured on 2026-10-20 and 2026-10-21 with the scripts described in
[README.md](README.md). The raw outputs are in [runs/2026-10-20/](runs/2026-10-20/)
(the analyzer benchmarks in its `rifma.json`, `armenian.json`, `wikipron.json`
and `oov.json`, rerun as the analyzer changed; the latest RIFMA run is
[runs/2026-10-21/rifma.json](runs/2026-10-21/rifma.json)) and the third
holdout's in [runs/2026-10-21/holdout3/](runs/2026-10-21/holdout3/).

## The analyzer

**Russian stress and rhyme, RIFMA** (5,121 hand-marked poems and stanzas):

| | |
|---|---|
| stress of polysyllabic words (60,854) | 97.4% |
| each word's first reading, without meter or rhyme | 93.3% |
| words the dictionary lists (52,714) | 98.2% |
| ambiguous words resolved by meter and rhyme (3,669) | 95.3% |
| unknown words guessed from the ending, meter and rhyme (4,346) | 88.6% |
| "these two lines rhyme", 33,798 pairs within stanzas | P 0.941, R 0.880, F1 0.909 |

RIFMA was the development set for the Russian rules: the misses it showed
led to the gerund and participle twins, the ending prior, the second
locative and the rhyme-aware stress choice. The derived forms (comparatives,
participles, the declension of lemmas the dump lists bare) moved 799 words
from guess to dictionary; against RIFMA's marks, 98 words came out right
that had been wrong and 45 the other way, most of those 45 a colloquial
stress the poets used where the dictionary has another (огово́рен for
оговорён, отклю́чен for отключён). The rhyme threshold was checked
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
matches when ashugh agrees with any of them, and a word whose schwa ashugh
makes optional (a compound's, or the article -ն's in սերն) matches at
either length, as the checker accepts both.

| | before the lists | now |
|---|---|---|
| sung syllables equal Wiktionary's vowels | 91.2% | **93.4%** |
| the same, on the 309 words Wiktionary writes with a schwa | 84.1% | **93.5%** |

The last rules (the negative չ- and future կ-, reduplicated roots, ռն and
րն before a consonant, ղմն, շ before an aspirate) came from a comparison with
every Wiktionary entry, held-out ones included, so for those patterns this is
not unseen data. Across all 17,594 entries they raised agreement from 16,891
to 16,958 words and broke none.

The 116 disagreements left, by kind:

| kind | words | mostly |
|---|---|---|
| a schwa at the start | 49 | Wiktionary writes none in loanwords and names (բրիգադ, ֆլեշմոբ, Պլեթոն) or before ս and a stop (սպանուհի), where ashugh sings one |
| a schwa at the end | 23 | stems in -նդ, -րդ and -րս that the held-out list lacks, read as the possessive (տաղանդ, մարդ, աղերս), and abbreviations (ԵՏՄ) |
| a vowel letter | 32 | Wiktionary reads ի before a vowel as a glide (դանիացի as dɑnjɑtsʰi); sung verse gives it a syllable |
| a schwa inside | 12 | compounds whose second root is listed in no form of its own (ծո-վա-գը-նաց, from գնալ) or was left out for breaking an entry (պատ-կե-րա-սը-րահ) |

Wiktionary transcribes speech, not singing, so this is agreement rather than
accuracy. The comparison gave ashugh four things:

- four rules: a word does not end in մն or ռն (ու-րե-մըն, սա-ռըն, as in 19
  of 21 entries), though it may end on a fricative and մ (կողմ, -իզմ: all 84
  such entries are closed); it may end on three consonants that fall in sonority
  (պարտք, կուրծք, Մինսկ, and տեքստ with ս between stops: all 67 such
  entries are written closed, where ashugh had sung a schwa); a schwa
  syllable closes on two consonants only when the second is a stop
  (մը-կըրտ-չյան but զը-րըն-գալ, բը-ժըշ-կել: of the entries where ashugh
  had closed one on a sonorant or a fricative, Wiktionary splits 39 and
  keeps 8); and a final դ after ր is the possessive (սե-րըդ, your love).
  Dictionary forms never carry the possessive, so this test shows what the
  last costs (the -րդ stems the held-out list lacks) and not what it gains;
- 296 stems whose final ս or դ is their own (ադամանդ, մաքս, ժողովուրդ);
- 248 word beginnings that keep a compound root's schwa (մեղադր-, so
  մե-ղա-դը-րել, մե-ղա-դը-րան-քը), each kept only if it breaks no entry the
  rules read right. On the held-out words they fixed 8 and broke none.
  Speech often drops this schwa (Wiktionary gives both forms for 193
  words), so a line may sing it or not, as with the schwas of connected
  speech;
- 1,995 roots that open on two consonants with a schwa between (նշան,
  սղոց), which keep it after a compound's linker ա or ե (լու-սա-նը-շան,
  բեն-զա-սը-ղոց), less 24 that would break an entry the rules read right
  (կցել would make համագործակցել հա-մա-գոր-ծա-կը-ցել). On the held-out
  words they fixed 14 and broke none; where they add a schwa, Wiktionary
  writes it in 14 of 15, and the fifteenth differs only at its start.

In the eval's Armenian drafts (2,919 words) only three words read
differently: լեռն and սառն gain their schwa, which connected speech still
lets fit, and լուսանկարներ (lu-sa-nə-kar-ner) gains an optional one. Every
draft scores the same. The roots match one word in the drafts, the same
լուսանկարներ, which the compound list already covers.

**Words outside the dictionaries** (every tenth entry held out):

| | ashugh | baseline (commonest position) |
|---|---|---|
| Russian stress (55,417 words) | 75.6% | 40.8% |
| English stress (9,405) | 77.0% | 66.7% |
| English syllables from spelling (11,748) | 88.4% | |

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
bugs; rescoring every draft and every repaired text with the analyzer of that
time gave the same numbers. A later fix of the possessive after a plural
(782b9cc: աչ-քե-րըդ is three syllables) flags three more draft lines
(աչքերդ twice in hy-lullaby, Աչքերդ in hy-spring): rescored today, the
drafts meet 136/140 lines and 9/12 songs, the repaired texts 137/140 and 10/12. Before the fixes the drafts scored 133/140 and 185/196
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
measurement: with the fixed analyzer the same drafts raise only two of the
three real flags. The troika line now passes: a later round found that the
canonical anapests of Fet and Nekrasov stress a whole word before the first
beat (Утро дышит у ней на груди), and ashugh took that licence, so the
strict standard this line broke is no longer the one it checks. One false alarm did harm: the hy-lullaby line was right, and the
repair Դու աչուկներդ փակիր sings seven syllables in a slot of six, so the
repaired songs, rescored today, meet 997 / 1,000 lines and 47 / 48 songs.

### Holdout 3

After nine more rounds of fixes, two new cold writers wrote all 24 briefs
again (48 drafts, 836 lines, in
[runs/2026-10-21/holdout3/](runs/2026-10-21/holdout3/)). They were scored
and repaired with the analyzer frozen at commit 0420c02, run from an export
while later work went on. A fresh subagent answered the repair requests in
one round (`ashugh eval requests`, then `ashugh eval apply`), with nothing
but the requests to go on.

| | lines meeting the spec | songs meeting the spec |
|---|---|---|
| Claude alone | 822 / 836 (98.3%) | 40 / 48 |
| Claude with ashugh, by the checker | **836 / 836** | **48 / 48** |
| Claude with ashugh, on reading | 835 / 836 | 47 / 48 |

Read one by one, the 14 flagged lines were 6 real errors, 7 lines that
break the strict rhyme standard ashugh documents (an open rhyme wants the
consonant before its vowel; a closed ending does not rhyme an open one),
and 1 false alarm:

| flagged | real? | after fit |
|---|---|---|
| hy-mother: Աչքերս փակում՝ քեզ եմ տեսնում | yes: աչ-քե-րըս is three syllables, the line nine in a slot of eight | Աչքերս փակ՝ քեզ եմ տեսնում |
| hy-iamb: Նայում էր մայրս հեռու ճամփին | yes: մայ-րըս has two syllables, so every stress after it falls a beat late | Ու մայրս էր նայում ճամփին |
| hy-iamb: Այդ լույսն երբեք էլ չի հանգչում | yes: լույ-սըն keeps its schwa, as ե after it is [je] | Երբեք այդ լույսը չի հանգչում |
| hy-trochee (3 lines): …գան դուրս, against չորս | yes: դուրս and չորս differ in their stressed vowel | Թող կատուն գնա իր որս |
| hy-wedding (2 lines): …դուք երկու, against հարսնացու | by the strict standard: -կու / -ցու | Սիրով ապրեք, ոչ կծու |
| ru-road: двадцать / остаться | by the strict standard: closed against open | Нам по двадцать — что бояться? |
| ru-road (2 lines): звеня / семья | by the strict standard: -ня́ / -мья́ | Ветер бьёт в стекло, друзья |
| ru-dog: навстречу / вечер | by the strict standard: closed against open | И в тот вечер, в эту встречу |
| ru-city: стене / голове | by the strict standard (-не́ / -ве́), but ashugh also misread стене as сте́не | И в тишине звенят ступени |
| ru-troika: Не вернуть ни саней, ни коней | no: the dictionary dump stresses са́ней, the norm is сане́й | Не вернуть ни возка, ни коней |

One repair was a defect: the ru-city line passed the checker only through
its misreading of стене as сте́не, from стен, an obsolete unit the
dictionary dump lists. «Ступени» rhymes with сте́не, not with «по белой
стене́», so the repaired stanza still does not rhyme, and the
with-ashugh line reads 835 / 836. Both mistakes were fixed after the run,
each with a test: сани is stressed сане́й, саня́м, and obsolete words are
left out of the dictionary build. Rescored with today's analyzer, the drafts
meet 823 / 836 lines and the repaired texts 835 / 836: the troika line
passes, and the ru-city repair is flagged, as it should be.

The checker's own mistakes fell from 14 of the 18 flags in the two earlier
holdouts to 1 of 14 here.

### What this does and does not show

- The measurement is 120 holdout drafts of 24 tasks from eight writers, 48
  of them scored with today's analyzer; the first 24 drafts, from a ninth,
  are the development set.
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
