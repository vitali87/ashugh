# ashugh

**A prosody compiler that gives LLM-written lyrics an ear.** Named after the
Armenian troubadours (աշուղ).

LLMs see tokens, not syllables or stress, so they cannot hear whether a line
scans. Armenian makes it worse because it sings vowels it does not write:
Մկրտիչ has one vowel letter and three sung syllables (mə-kər-tich), and
սպասել is sung ըս-պա-սել. Russian stress is lexical and often ambiguous
(за́мок / замо́к), and rhyme there is a matter of sound, not spelling.

ashugh measures instead of guessing. It counts sung syllables, finds stress,
fits lines to a meter, judges rhyme by sound and checks it all against a song
spec. It then repairs what fails: an LLM proposes candidate lines, ashugh
keeps the ones that scan, and a solver picks the combination that keeps every
rhyme. The LLM drafts and the phonology verifies.

```
$ ashugh scan examples/song.hy.txt --spec examples/song.hy.toml
examples/song.hy.txt · Armenian · spec examples/song.hy.toml

[Verse 1]  detected dolnik · ABAB (spec ABAB)
  L3   9 syllables, slot is 8             «սպասում» sings as ըս-պա-սում

[Chorus]  detected dolnik4 · ABAC (spec ABAB)
  L11  rhyme B broken                     «սիրտ» / «կյանք»: none 0.10, need near

[Outro]  detected trochee4 · A (spec -)
  L14  ends in ը                          forbid_final = ["ը"]

6/9 lines pass · 3 errors
```

Armenian (Eastern), Russian and English. Pure Python, no required
dependencies; the Claude proposer and the CP-SAT solver are optional extras.

## Install

```bash
uv tool install "ashugh[all] @ git+https://github.com/vitali87/ashugh"
# the bare checker:  uv tool install "git+https://github.com/vitali87/ashugh"
# or once, no install: uvx --from "git+https://github.com/vitali87/ashugh" ashugh scan song.txt
```

Python 3.14; uv fetches it when the machine lacks it. The extras: `[claude]`
adds the Anthropic SDK for `fit`, `translate` and `eval`, `[cpsat]` adds
OR-Tools for large repair problems, `[whisper]` adds openai-whisper for
`probe transcribe`. `[all]` is `claude` and `cpsat`.

## Commands

| Command | What it does |
|---|---|
| `ashugh scan song.txt --spec song.toml` | check a song; exit 1 on errors; `--json` for agents, `-a` for every line |
| `ashugh fit song.txt --spec song.toml` | repair failing lines with candidates from Claude (or any program) |
| `ashugh pick song.txt --spec s.toml --candidates c.json` | repair with candidate lines you already have, no LLM |
| `ashugh requests song.txt --spec song.toml` | the failing lines and their constraints, as JSON for an agent |
| `ashugh translate song.en.txt --to hy --keep syllables,rhyme` | singable translation into the source's grid |
| `ashugh suno song.ru.txt --meter iamb` | rewrite for Suno: ё, stress hints, Armenian spelling, tags |
| `ashugh probe make սպասել --lang hy` | measure how Suno pronounces different spellings |
| `ashugh spec --from song.txt` | the spec that reproduces a song's form |
| `ashugh syl Մկրտիչը կյանքն է սիրում` | how a line is sung |
| `ashugh rhyme сердце дверце` | `perfect 1.00  sʲertsə / vʲertsə` |
| `ashugh eval run eval/tasks` | spec pass rate of a writer alone and with ashugh |
| `ashugh mcp`, `ashugh lsp` | MCP server for agents, language server for editors |

### scan

```
$ ashugh scan examples/song.ru.txt --spec examples/song.ru.toml
examples/song.ru.txt · Russian · spec examples/song.ru.toml

[Verse 1]  iamb · AbCb (spec AbAb)
  L4   rhyme A broken                     «окон» / «строгий»: assonance 0.40, need near
  L5   last stress off the beat           stress x/x/xx/, iamb wants x/x/x/x
  L5   3 feet, slot is 4                  7 syllables; iamb4 with a masculine ending has 8
...
```

`scan -a` shows every line with its count, stress grid (`/` stressed, `x`
not), rhyme letter and sung spelling. Lyrics follow the Suno conventions:
`[Verse 1]`, `[Chorus]` and other tags open sections, a blank line ends a
stanza, and text in parentheses is a backing vocal left out of the count. A
tag line may carry more tags or a note (`[Verse 1] [Male Vocal]`,
`[Chorus] (softly)`, `[Verse 2 - Rap]`); the tag Suno knows as a section names
it, and a style tag on a line of its own right after a section tag keeps that
section. Text pasted from elsewhere reads as typed: decomposed letters are
composed, soft hyphens and zero-width characters are dropped, a stray Latin
letter in a Cyrillic word or the other way round (oкон, hеllo) is read as its
look-alike, and the look-alikes of the apostrophe (´ ` ‘ ′ ʼ) and of the
hyphen inside a word count as ' and -. Parentheses may nest inside a backing
vocal, and a line of tags with notes (`[Chorus] (softly)`) is a tag line. A
vowel written three times or more is one held note (Ooooh, Ооо, Օօօ); written
with hyphens it is a note each (О-о-о). A note that names a section is given
Suno's name (`[Куплет 2 - Рэп]` becomes `[Verse 2 - Rap]`); a free note stays
as written.

### The spec

```toml
language = "ru"            # hy | ru | en; detected per line if omitted
syllables = [9, 8, 9, 8]   # or 8 for every line; lists repeat over the stanza;
                           # a 0 in a list leaves that line free (feet too),
                           # [0] every line of its section
tolerance = 0
meter = "iamb4"            # iamb trochee dactyl amphibrach anapest dolnik free (+ feet)
# feet = [4, 3]            # or feet per line, repeating over the stanza (a ballad)
rhyme = "AbAb"             # "-" or "." = free line; mixed case also asks endings:
                           # a capital letter feminine, a small one masculine
endings = "fmfm"           # m masculine, f feminine, d dactylic, h 3+ after, - any
                           # (iamb4 is 8 syllables masculine, 9 feminine)
min_rhyme = "near"         # perfect | near | slant | assonance
forbid_final = ["ը"]       # a line may not end in these letters

[section.chorus]           # [Chorus x2], [Припев], [Կրկներգ]; [Verse 2] is section.verse
syllables = [7, 7, 7, 5]
meter = "trochee"
feet = [4, 4, 4, 3]        # trochee: 7 syllables in four feet, masculine; 5 in three
endings = "m"
rhyme = "AABB"

[stanza.3]                 # one stanza of the file, counted from 1
syllables = [9, 8, 9, 8]

[lexicon]                  # how a word is really sung, when ashugh gets it wrong
"կայսրություն" = "կայ-սը-րու-թյուն"   # Armenian: syllables, hidden ը written out
"замок" = "замо́к"                    # Russian: an acute, a capital vowel or ё
"zorblax" = "Z AO1 R B L AE0 K S"     # English: ARPABET with stress digits
```

Each `[lexicon]` entry is checked when the spec loads, so a correction is
never silently ignored: a Russian word needs its stress marked, an English one
ARPABET with a digit on every vowel, an Armenian one its sung syllables split
by hyphens, one vowel each, and every entry must spell its word.

Top-level keys apply everywhere; `[section.<name>]` overrides them for its
sections, and `[stanza.<n>]` overrides its stanza's section in turn, so a
chorus stanza's table changes only what it sets, except that a table's
`meter` brings its own feet (`dactyl` in a chorus is any number of dactyls,
not the `iamb4` above's four). Command-line flags (`--syllables`, `--meter`, `--feet`,
`--rhyme`, `--endings`, `--tolerance`, `--min-rhyme`, `--forbid-final`) override all.
A `--rhyme` value that starts with `-` needs `=` (`--rhyme=-A-A`), or use
`.A.A`.

A rhyme scheme applies to each stanza on its own: `ABAB` over two stanzas
asks for two separate pairs of rhymes. Spaces split a scheme into stanzas
whose letters are shared, for rhymes that run across them, as in a sonnet:

```toml
rhyme = "ABBA ABBA CDC DCD"   # line 8 must rhyme with line 1
```

The parts are dealt out over the stanzas in turn, starting over with fresh
rhymes after the last part and at every section tag. A run that stops partway
through the scheme is a warning, and a single stanza reads the scheme
without its spaces.

### fit and pick

`fit` turns every failing line, and every line of a broken rhyme group, into
a variable. A proposer writes candidates for each, with the slot's
constraints and what went wrong: the syllable count, the stress template, the
words it must rhyme with, the forbidden endings. ashugh checks every
candidate in its slot. Within each rhyme group a solver picks one candidate
per line that keeps every rhyme while losing the least meaning: exact branch
and bound, or CP-SAT when OR-Tools is installed. Where nothing fits, the next
round asks again, aimed at the blocking constraint, with the near misses and
the words to rhyme with. That is column generation, with the LLM as the
pricing oracle.

```bash
ashugh fit song.txt --spec song.toml -o fixed.txt            # Claude (ANTHROPIC_API_KEY)
ashugh fit song.txt --spec song.toml --proposer "cmd:my-llm" # any program speaking JSON
ashugh pick song.txt --spec song.toml --candidates c.json     # candidates you wrote
```

The default proposer is Claude Opus 5.5 with structured JSON output
(`--model`, `--effort`). A `cmd:` proposer gets `{"requests": [...]}` on stdin
and prints `{"lines": [{"id": "L3", "candidates": ["..."]}]}`. `pick` and the
MCP `pick` tool let an agent that is already writing the lyrics be the
proposer itself: `ashugh requests` hands it the constraints, and it answers
with a candidates file: that same `{"lines": [...]}` answer, or simply
`{"3": ["...", "..."]}`, where a candidate may also be
`{"text": "...", "faithfulness": 0.9}`.

### translate

```bash
ashugh translate song.en.txt --to hy --keep syllables,rhyme -o song.hy.txt
ashugh spec --from song.en.txt --keep syllables,meter,rhyme --lang ru > grid.toml
```

The source is scanned first. Per stanza, its syllable counts, meter and feet,
rhyme scheme and endings become `[stanza.N]` rules for the target, as far as
`--keep` asks. Then every line is translated under its slot's constraints by
the same check, solve and re-ask loop as `fit`. Rhyme hints only ever come
from target-language candidates.

### suno

```bash
ashugh suno song.ru.txt --meter iamb            # зАмок, ещё, [Припев] -> [Chorus]
ashugh suno song.hy.txt --armenian schwa        # ըսպասում, Մըկըրտիչ
ashugh suno song.hy.txt --armenian latin        # əspasum, Məkərtich
ashugh suno song.txt --split last               # пра-вил: syllables of held notes
```

* Russian: ё is restored only where the dictionary is sure, in backing vocals
  too.
* Russian: stress is marked only on words whose stress is ambiguous or
  guessed, by a capital vowel (the convention Suno users rely on) or with
  `--stress acute`, and on a preposition that took the stress (пО лесу).
* Armenian: kept in script, written with every sung schwa (linking schwas
  dropped, as they are in speech), or romanized, backing vocals included; the
  writer's ՛ ՜ ՞ stay on held-note pieces, and in Latin letters a ՞ or ՜ makes
  its sentence a question or an exclamation (Ո՞ւր ես, ո՞ւր: Úr es, úr?).
* Section tags in Russian or Armenian are translated to Suno's names. An
  untagged song gets `[Verse n]` and `[Chorus]` from its repeated stanzas.

Suno does not document its pronunciation, so `probe` measures it:

```bash
ashugh probe make սպասել Մկրտիչ --lang hy --lyrics probes/   # one clip lyric per spelling
# generate each clip in Suno, save as probes/<id>.mp3
ashugh probe transcribe probes/ --plan probes.json           # Whisper (the whisper extra)
ashugh probe transcribe probes/ --engine "cmd:whisper-cli -m ggml-small.bin -l {lang} -nt -f {audio}"
ashugh probe score probes.json transcripts.json -o policy.json
ashugh suno song.hy.txt --policy policy.json                  # the winning spelling, word by word
```

Any recognizer works through `--engine cmd:`: `{audio}` and `{lang}` stand
for the clip and its language, and the command prints the transcript.
The score is how close each transcript, analyzed by ashugh, comes to the
intended sung form. Transcripts use normal spelling, so this measures
intelligibility rather than every sung schwa.

## Agents and editors

* **Claude skill.** `uv run scripts/build_skill.py` writes
  `dist/ashugh-skill.zip` (CI attaches it to every build). Upload it as a
  skill in Claude, or copy `dist/ashugh` to `~/.claude/skills/` for Claude Code. It
  bundles the tool and tells Claude to draft, scan, repair with `requests` and
  `pick`, and re-scan before it shows you a song. See
  [skill/SKILL.md](skill/SKILL.md).
* **MCP.** `claude mcp add ashugh -- ashugh mcp` (or, with nothing installed,
  `claude mcp add ashugh -- uvx --from git+https://github.com/vitali87/ashugh ashugh mcp`)
  gives an agent the tools
  `scan`, `syllables`, `rhyme`, `requests`, `pick`, `translate`, `suno`,
  `derive_spec` and `spec_template`. `translate` takes the CLI's `keep`,
  `tolerance` and `min_rhyme`, and `derive_spec` a `source_lang`.
* **Language server.** `ashugh lsp` underlines the lines that do not scan and
  shows on hover how a line is sung. The spec is the file's sibling `.toml`
  (song.txt -> song.toml) or the nearest `ashugh.toml`; saving the spec
  rechecks the open songs.

## How well it works

All numbers are from the scripts in [eval/](eval/); the full write-up is
[eval/RESULTS.md](eval/RESULTS.md).

**Claude alone and Claude with ashugh.** Twenty-four writing tasks, twelve
everyday forms and twelve harder ones: per-line melody grids with set
endings, a separate chorus form, ternary meters, Armenian feminine endings,
and translations into the source's grid. Claude writers with no access to
ashugh drafted each song; then `fit` asked Claude for candidates for the
lines that failed. The latest holdout, 48 drafts from two new writers, was
scored and repaired with the analyzer frozen before they were written:

| | lines meeting the spec | songs meeting the spec |
|---|---|---|
| Claude alone | 822 / 836 (98.3%) | 40 / 48 |
| Claude with ashugh | **835 / 836** | **47 / 48** |

The repair took one round. A strong model gets most lines right on its own;
what it misses is what it cannot hear: a schwa Armenian sings but does not
write (աչ-քե-րըս, մայ-րըս), a rhyme on another vowel (դուրս / չորս), an open
rhyme without its supporting consonant (звеня / семья). Of the 14 lines the
checker flagged, 13 were real. One was its own mistake (the dictionary's
са́ней for сане́й), and one repair passed only through another (стене read
as сте́не, from an obsolete unit), so it counts as failed above; both are
fixed with tests. In two earlier holdouts, scored with older analyzers, 14
of the 18 flags were the checker's mistakes. RESULTS.md has every flagged
line, those holdouts, the development set and the caveats. The writers and
proposers were Claude subagents, not API calls.

**Russian, on RIFMA** (Koziev 2025: 5,121 poems and stanzas with every
stress marked by hand and a rhyme scheme; `uv run eval/rifma.py`):

| | |
|---|---|
| stress of polysyllabic words (60,855) | **97.4%** correct |
| each word's first reading, without meter or rhyme | 93.0% |
| words the dictionary lists | 98.2% |
| ambiguous words, resolved by meter and rhyme | 95.4% |
| unknown words (7%), guessed from the ending, meter and rhyme | 88.6% |
| "these two lines rhyme", pairs within a stanza | precision 0.94, recall 0.88, F1 0.91 |

RIFMA was also the development set for the Russian rules, so these numbers
are not from unseen data.

**Armenian sung syllables** (`uv run eval/armenian.py`). On 81 words that
each exercise one schwa rule (eval/data/hy_gold.tsv, checked by hand),
ashugh matches every syllabification. espeak-ng, the reference
phonemizer, got 82% of the syllable counts on the first 68. It misses two schwas in
Մկրտիչ, the possessive schwa in սիրտս, and rising final clusters like աստղ.
The gold list was written together with the rules, so treat ashugh's 100% as
a regression test, not as an independent measurement.

**Armenian against Wiktionary** (`uv run eval/wikipron.py`): on 1,768
words of Wiktionary's Eastern Armenian pronunciations that ashugh's word
lists were built without, its sung syllables match Wiktionary's vowels for
93.4% of words (93.5% of those written with a schwa). Most of the rest are
conventions rather than errors: Wiktionary leaves out the schwa of many
loanwords and names (բրիգադ, ֆլեշմոբ) and reads ի before a vowel as a
glide (դանիացի). The real misses, 12 words (0.7%), have a schwa inside that
the two readings disagree on: mostly compounds no listed word explains
(ծո-վա-գը-նաց), and some clusters where ashugh sings a schwa Wiktionary does
not write (ա-բըստ-րա-հել).

**Words outside the dictionaries**, held out (`uv run eval/oov.py`): the
stress-by-ending prior gets 75.6% of Russian words right (always guessing the
commonest position: 40.8%) and 77.0% of English words (66.7%). The English
syllable count from spelling is right for 88.4% of words.

## How it works

**Armenian** (`lang/hy.py`). Letters become phonemes: word-initial ե is
[je] and ո is [vo], ու is one vowel, and և splits into e + v. Then every
consonant cluster is split into a coda, an onset and as few schwa syllables
as possible:

- a word-initial ս, զ or շ before a stop takes a schwa in front of it:
  ըս-պա-սել, ըզ-գեստ, and ըս-կը-սել when the cluster goes on; but շ before
  an aspirate and զ before a voiceless stop take it after them (շը-քեղ,
  շը-փոթ, զը-տել);
- an onset is one consonant, or a consonant plus յ (կյանք, -թյուն);
- a coda is at most two consonants that do not rise in sonority (սիրտ,
  միտք), so տետր is տե-տըր and աստղ is աս-տըղ, though a word may end on a
  fricative and մ (կողմ, ռեալիզմ) or on three
  (պարտք, կուրծք, Մինսկ, and տեքստ with ս between stops); a schwa syllable
  closes on two consonants only when the second is a stop (մը-կըրտ-չյան,
  հընդ-կաս-տան), so զրնգալ is զը-րըն-գալ and բժշկել is բը-ժըշ-կել;
- a word does not end in մն or ռն: ու-րե-մըն, սա-ռըն; nor does a syllable
  close on ռն or րն before another consonant (ա-ռըն-չել, ձեռ-նը-տու), while
  a fricative and մ stay a coda before ն (կողմ-նա-կի, բեղմ-նա-վոր);
- a final ս or դ after a consonant other than յ is the possessive and takes
  a schwa (սիր-տըս, գը-լու-խըդ, սե-րըս, սե-րըդ, տու-նըդ), except where the
  stem ends that way: 296 stems listed from Wiktionary's dictionary forms
  (չորս, մարդ, ադամանդ, մաքս), compounds joined by ա or ե that end in one
  (նո-րա-հարս), and nouns in -որդ and -ուրդ (վա-րորդ, ժո-ղո-վուրդ);
- the negative prefix ան- keeps its stem's schwa (ան-շը-տապ), as վեր-
  keeps the one before ս and a stop (վե-րըս-տին, վե-րըս-կը-սել), and so do
  the negative չ- and the future կ- before a verb (չը-գը-նամ, կը-գը-նամ, as
  գը-նալ); the future only where its ending fits a listed verb, so the roots
  կղզի and կրկին stay as they are;
- a reduplicated root keeps both schwas (բըլ-բը-լալ, կըլ-կը-լալ, թըր-թը-ռում);
- the article -ն after ր, լ or ն may be sung with a schwa or without it
  (սե-րըն or սերն): a line may count either; after two consonants the
  schwa stays (կյան-քըն) unless a vowel follows (կյանքն է, կյանք-նէ);
- a compound keeps its second root's schwa (մե-ղա-դը-րել, from դրել): 248
  word beginnings that do this are listed from Wiktionary, and so are 1,995
  roots that open on two consonants with a schwa between (նշան, սղոց), which
  keep it after a compound's linker ա or ե (լու-սա-նը-շան, բեն-զա-սը-ղոց);
  since speech often drops that schwa, a line may sing it or not;
- among equal splits, the onset with յ wins, then the split whose codas
  are longest reading from the right: մը-կըր-տիչ, ա-դըր-բե-ջան.

In connected speech, a vowel before a word swallows its leading ը (նա
ստացավ), and a final schwa syllable links onto a vowel after it (կյանքն է);
where a word does both (քո ստվերն է), the leading ը goes for good. The check
uses whichever length fits the slot. Stress falls on the last full vowel, or
where a ՛ ՜ ՞ mark puts it. The auxiliary եմ/ես/է… (and speech's ա for է) is
an unstressed enclitic that rhymes with the word before it. ես is the pronoun
I [jes] instead where it opens its clause (Ես եմ, ու ես), follows an
auxiliary of I (սիրում եմ ես) or its clause has a verb of I (հիմա ես գիտեմ,
քեզ ես սիրեցի), and the auxiliary [es] otherwise (ինչու ես լռում, գեղեցիկ
ես ամեն անգամ). A voiced stop after ր is said aspirated (երգ [jɛɾkʰ] rhymes
with բերք). An abbreviation in capitals is said letter by letter (Ա-Մե-Նե,
Հա-Հա), even in a line in capitals when it has no vowel letter, and a case
ending after a hyphen follows the letters and takes the stress (ԱՄՆ-ից
Ա-Մե-Նե-ի́ց, ՀՀ-ի Հա-Հա-յի́); a word of up to five letters that Wiktionary
lists, or one with ու, stays a word when written in capitals for emphasis
(ՔԵԶ, ԻՆՁ, ԴՈՒ). In an Armenian song, a line in Latin
letters whose words are mostly not English is Armenian typed in Latin (Mtnem
aygin, kyanq), read in Armenian letters: mət-nem, ay-gin; the English words
it borrows stay English (sirum em qez, baby), and in an English line a word
spelt as Armenian is Armenian (oh baby kyanqs: kyan-kʰəs). A name in Latin letters with an Armenian
ending (TikTok-ում, Ararat-ը, iPhone-ս) is one Armenian word: the name as
English says it (or in Armenian letters if English lacks it), the ending after
it with a schwa where a lone consonant follows a consonant (iPhone-ըս), and the
stress on the ending's vowel or else on the name's end, never on ը; `suno`
keeps the name as written and, in Latin mode, writes the ending in Latin
(TikTok-um, Ararat-ə). A hyphenated reduplication
(փափուկ-փափուկ, тихо-тихо) is one stressed word per part, and any other
hyphenated word the dictionary lacks keeps each part's stress as a secondary
one the meter may use, the last part carrying the main stress and the rhyme
(баю́-ба́юшки-баю́, ice-cóld, twenty-four-séven).

**Russian** (`lang/ru.py`). Stress comes from, in order:

1. a mark in the text;
2. the spec's `[lexicon]`;
3. 559,413 stressed forms from OpenRussian, with ё restored (еще becomes
   ещё), the past tenses the dump leaves out derived from the infinitive,
   and a prefixed verb's feminine past ending-stressed where its base's is
   (позвала́ like звала́; the dump's позва́ла stays second, for verse); a
   form's readings come in the order of how usual their source is, the
   headword first, then nominatives and verb forms, then the other cases
   (глаза́ before гла́за, долги́ before до́лги);
4. 398,547 regular forms the dump leaves out, derived from its lemmas and
   read only where it lists no form with that spelling (ё read as е):
   comparatives with their по- (нежне́е, кре́пче, подо́льше), past
   participles (бро́шен, решённый, сби́ты, обма́нутых, ста́вший), and, for
   a lemma whose row is empty, its declension (пре́жнему, вселе́нной,
   людски́х) or, for -овать and -ывать verbs, its present (припарку́ет);
   verbs whose participles move their stress their own way (о́тдан,
   отдана́; про́лит) are left to the steps below;
5. the dictionary twin of a poetic or derived form: мгновенье, мглою,
   сильней, -ся, не-, folk -ся after a vowel (ложи́ся), and a prefixed verb
   the dump lacks (отжила́ like жила́);
6. the verb forms that share a gerund's or participle's stress: теряя from
   теряю, начав from начать, создавший from создать;
7. about 30 slang words and loanwords of today's songs, newer than the
   dump, with their forms (`lang/ru_slang.py`): дедла́йн, бе́йби, тре́нды,
   фле́ксить and фле́кшу, ха́йповый, суперзвезда́ and суперзвёзды;
8. else a prior learned from word endings (from step 3's forms alone),
   which the meter can overrule.

A capitalized word inside a sentence that spells one of about 230 first
names, diminutives and places is that name (Ма́шу, Ко́лю, Со́чи, Росто́ва,
not машу́, колю́, сочи́); one that opens a sentence keeps the dictionary's
reading first and gains the name's. A name written without its ё gets it
(Лёха, Алёна, and surnames such as Горбачёв, Королёва), and a first name gives its possessive and diminutives
(Та́нин, Та́нечка, Ни́ночка). An abbreviation in capitals that spells no
word is sung letter by letter and stressed on the last (эс-пэ-бэ́, which
`suno` writes out for the singer) when it has no vowel letter (СПб, МСК),
ends on a vowel and has more consonants (США, МГУ), has two letters (ИП,
и-пэ́) or ends on a doubled consonant after another (ГИБДД, гэ-и-бэ-дэ-дэ́);
США and ЦСКА are said as custom has it (сэ-шэ-а́, цэ-эс-ка́). One said as a
word is stressed on its end (ЕГЭ́) unless the dictionary knows it (НА́ТО);
a word in capitals for emphasis stays a word (СТРАНА, ГДЕ), ЗАГС and ВУЗ stay
words, a line in capitals spells only the ones with no vowel or a doubled
end (ВСЁ В СССР), and ХМ and ТСС are sounds, not letters. A preposition or conjunction said twice in a
row is a vocable, not a clitic (на-на-на, да-да-да), and тя leans on its
verb like бы. A hyphenated word the dictionary stresses only before its last
part takes the last part's stress too (чёрно-бе́лый), and a compound's
earlier ё is no reading of its own (трёхэта́жный).

A dictionary reading after the first costs the meter a little, so where the
meter leaves the choice open the usual reading wins (уже́, not у́же; е́ду,
not еду́), and right after a preposition a stress only a verb form has is
dropped (по по́лю, not полю́, I weed); after a preposition of the genitive
(из, у, от, до, без, с, ни...) so is a stress only a nominative or
accusative plural has (из окна́, до луны́, из села́; not о́кна, лу́ны, сёла).
Frequent words come before rarer homographs the table ranks higher (мою́,
стоя́т, выходи́).

After в, во and на, about a hundred nouns take the stressed second locative
(на берегу́, в саду́, в крови́), also past an adjective or pronoun before them
(в э́том дыму́, в моей груди́). In about a hundred set pairs the stress may
move onto the preposition (по́ лесу, на́ ночь, за́ руку); the meter takes
whichever reading fits, and a shifted line end rhymes from the preposition.
At the end of a line, the rhyme partner picks between readings the meter
allows equally: облака́ / издалека́. A phonetic transcription reduces
unstressed vowels, devoices and assimilates obstruents, drops silent
consonants (сердце, солнце, честный), says г before к or ч as х (лёгкий,
мягче) and a double consonant single before a consonant or at the end (класс
rhymes with вас); a word after the line's last stress is said with its vowels
reduced (он же rhymes with тоже, ты ли with пыли).


**English** (`lang/en.py`). Pronunciations come from CMUdict (126k words),
with primary and secondary stress. A variant with one vowel fewer (every,
fire, temperate) makes a droppable syllable, and so does an unstressed er
right after the diphthong of desire or power, which the dictionary writes
only long; a variant that spells out an abbreviation (us as U.S.) does not
count. A diphthong after the main stress keeps its full vowel and acts as a
secondary stress, for the meter and the rhyme (ém-pìre / fire, bírd-hòuse /
mouse), whether or not the dictionary marks it. An object pronoun that ends a
line after a verb or a noun leans on it (néed it, hóld me), and the rhyme may
fall on either (need it / read it, love you / true), though never on the same
pronoun twice (need it / want it). After a verb and a preposition the pronoun
may stay weak or take the beat (cáll to me / áll to me, walk with mé / free). A
grave sings an -ed (blessèd), an old -est
or -eth after a vowel is its own syllable (go-est), & is sung as and, and a
word glued to digits ('80s) is left to the digits warning. A dropped g is
the -ing word ending in [ɪn] (goin', nothin' / within), and ya and 'em are
weak like you and them. A word the dictionary lacks is its stem and an ending
where it has one: a plural (lán-ces, be-síe-ges), -ing, -ed and -er (ví-bing,
ghó-sted, ín-flu-en-cer). An abbreviation in capitals is sung letter by
letter, stress on the last (L-Á, N-Y-C, D-Ms), unless the whole line is in
capitals (I AM THE ONE) or the dictionary has it as a word (NASA); a lowercase
word is never read as its letters (ba is not B.A.). Other unknown words are
counted from their spelling and stressed by the ending prior, and named in a
warning, a one-syllable one too (zorb), since English spelling does not count
syllables. A preposition that ends a line takes the stress (ships gone by /
sky). A word sung a syllable short rhymes as sung (real in one syllable /
feel), and as written; a last word that may be sung short (fire, hour, poem)
takes the ending a spec asks of it and rhymes either way (poem / home). An
object pronoun after a form of be is the predicate and takes the beat (all I
want is yóu). A hyphenated word is read part by part, the last part's stress
the main one, even where the dictionary lists the whole (twenty-óne / sun).
A dictionary reading that moves the stress costs the meter a little, and one
that moves it onto a full vowel where the usual reading has a reduced one is
a surname's and left out (begún, not Bé-gun). An abbreviation with no vowel
letter is always spelt (MC, DJ), even in a line in capitals; Y counts as a
vowel there (MY, WHY and GYM are words) and HMM, SHH and PSST are sounds. One
of four letters or more that alternates
consonant and vowel is a word (FOMO, NASA), and Dr. is doctor. Song slang
the dictionary lacks or gets wrong is listed: yeet, highkey, lowkey, rizz,
bae, email, spring.

**Meter** (`meter.py`). Each syllable position is a strong or a weak beat.
Fitting a line picks a reading for every ambiguous word and prices the
mismatches:

- a polysyllable stressed on a weak beat costs the most;
- a skipped beat (pyrrhic) is cheap in binary meters;
- monosyllables, function words, pronouns and secondary stresses may take
  either beat;
- the last stress must land on a beat;
- in a ternary meter or the dolnik, a word wholly before the first beat may
  keep its stress (У́тро ды́шит у ней на груди, Сму́глый о́трок бродил).

English verse licences cost a little: in a ternary meter a foot may lose one
weak syllable, at the line's start and once inside it (That hóst with their
bánners at súnset were séen; And there láy the stéed), as English anapests
and dactyls do; a line may open on an inverted foot
(Sometime too hot the eye of heaven shines), a compound may move its stress
to its second part (sometíme, but not prógram or áthlete), a late stress may move back onto a secondary
one when a stressed word follows (Ténnessee whiskey, but not a line that ends
on Tennessee), and the last beat may fall on a final syllable
two after the stress (témperàte), which can then carry the rhyme
(memory / free), or in a ternary meter on a final secondary stress, the main
one yielding to the beat before it (on deep Gal-i-lée).

Detection compares iamb, trochee, dactyl, amphibrach, anapest and dolnik,
and falls back to free verse.

**Rhyme** (`rhyme.py`). A tail runs from the last stressed vowel to the end
of the line, enclitics included. Two tails score by their stressed vowels
and a feature-weighted alignment of what follows, where reduced vowels after
the stress count half. Russian and Armenian open rhymes also need the
consonant before the vowel (ты / красоты). A rhyme group holds where its
lines rhyme with one another, each line at its own stanza's `min_rhyme`:
the largest set that does stands, and the lines outside it are flagged
(pen / end / friends / ends holds, though pen and ends are only slant).
Words are compared by sound, not spelling: a homograph stressed apart is no
rhyme (за́мок / замо́к, désert / desért), and English keeps apart the vowels it
contrasts (still / feel, far / war) but not the ones it merges before r
(here / year, tour / poor), and an English r is no l (care / bell is slant). A line that rhymes only on the word an earlier
line ends with, or on another form of it (сердце / сердца, սիրտս / սիրտը), is
warned about as a refrain, not a rhyme.

## Limits

- Some Armenian schwas come from a word's history rather than its clusters:
  a compound keeps the schwa of its second root (աստղագնաց is
  աստ-ղա-գը-նաց, կայսրություն is կայ-սը-րու-թյուն). The listed compounds
  and roots cover most; for the rest (0.8% of dictionary words), write the word into
  `[lexicon]` once and every song uses it, in its forms with an article,
  possessive, case or plural too (կայսրությունը, կայսրությունում).
- Only Eastern Armenian. Western Armenian is not supported yet.
- Rhyme follows modern pronunciation, as Suno sings it: an unwritten ё is
  ё, so a classical rhyme like безнадежной / нежный reads as no rhyme.
- No sentence is parsed. A Russian homograph is read by the meter and the
  usual reading (уже́, е́ду), so where both fit, the rarer one may be picked
  against the grammar (твои́ руки́ for ру́ки): mark the stress (ру́ки or рУки)
  where it matters. Russian forms the dictionary lacks are derived by rule
  (scripts/ru_forms.py), and verbs whose participles move their stress their
  own way are left to the guess.
- Armenian typed in Latin letters is turned back into Armenian letters, but
  Latin spelling cannot tell ч from ճ or ց from ծ, nor mark aspiration;
  syllables and stress come out right, rhymes only approximately.
- `probe` needs you to generate the clips in Suno; ashugh cannot call Suno.

## Development

```bash
uv sync --extra all          # Python 3.14, the dev tools, and the claude and cpsat extras
uv run pytest
uv run ruff check . && uv run ruff format --check .
uv run ty check
```

CI runs the same on Python 3.14, and on 3.15 while it is in beta (with the
claude extra only: OR-Tools has no 3.15 wheels yet).

The data tables are rebuilt by `scripts/build_ru_lexicon.py` (from the
[OpenRussian dump](https://github.com/Badestrand/russian-dictionary)),
`scripts/build_en_lexicon.py` (from
[CMUdict](https://github.com/cmusphinx/cmudict)),
`scripts/build_hy_lexicon.py` (from
[WikiPron](https://github.com/CUNY-CL/wikipron)'s Wiktionary scrape) and
`scripts/build_suffix_stress.py`.

## License

The code is MIT (see [LICENSE](LICENSE)). The Russian stress table is
derived from OpenRussian (CC BY-SA 4.0), the Armenian word lists from
Wiktionary (CC BY-SA 4.0), and the English table from CMUdict (BSD-style).
See [NOTICE.md](NOTICE.md).
