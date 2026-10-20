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
pip install "ashugh[all] @ git+https://github.com/vitali87/surprise"
# or the bare checker: pip install git+https://github.com/vitali87/surprise
```

Python 3.11 or newer. `[claude]` adds the Anthropic SDK for `fit`,
`translate` and `eval`; `[cpsat]` adds OR-Tools for large repair problems.

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
| `ashugh rhyme сердце дверце` | `perfect 1.00  sʲertsɨ / vʲertsɨ` |
| `ashugh eval run eval/tasks` | spec pass rate of a writer alone and with ashugh |
| `ashugh mcp`, `ashugh lsp` | MCP server for agents, language server for editors |

### scan

```
$ ashugh scan examples/song.ru.txt --spec examples/song.ru.toml
[Verse 1]  iamb · ABCB (spec AbAb)
  L4   rhyme A broken                     «окон» / «строгий»: assonance 0.42, need near
  L5   last stress off the beat           stress x/x/xx/, iamb wants x/x/x/x
  L5   3 feet, slot is 4                  7 syllables; iamb4 with a masculine ending has 8
...
```

`scan -a` shows every line with its count, stress grid (`/` stressed, `x`
not), rhyme letter and sung spelling. Lyrics follow the Suno conventions:
`[Verse 1]`, `[Chorus]` and other tags open sections, a blank line ends a
stanza, and text in parentheses is a backing vocal left out of the count.

### The spec

```toml
language = "ru"            # hy | ru | en; detected per line if omitted
syllables = 8              # or [8, 8, 8, 6]; lists repeat over the stanza
tolerance = 0
meter = "iamb4"            # iamb trochee dactyl amphibrach anapest dolnik free (+ feet)
rhyme = "AbAb"             # "-" or "." = free line; mixed case also asks f/m endings
endings = "fmfm"           # m masculine, f feminine, d dactylic, - any
min_rhyme = "near"         # perfect | near | slant | assonance
forbid_final = ["ը"]       # a line may not end in these letters

[section.chorus]           # [Chorus], [Chorus x2]; [Verse 2] matches section.verse
syllables = [7, 7, 7, 5]
rhyme = "AABB"

[stanza.3]                 # one stanza of the file, counted from 1
syllables = [9, 8, 9, 8]

[lexicon]                  # how a word is really sung, when ashugh gets it wrong
"կայսրություն" = "կայ-սը-րու-թյուն"   # Armenian: syllables, hidden ը written out
"замок" = "замо́к"                    # Russian: an acute, a capital vowel or ё
"zorblax" = "Z AO1 R B L AE0 K S"     # English: ARPABET with stress digits
```

Top-level keys apply everywhere; `[section.<name>]` and `[stanza.<n>]`
override them. Command-line flags (`--syllables`, `--meter`, `--rhyme`,
`--endings`, `--tolerance`, `--min-rhyme`, `--forbid-final`) override all.
A `--rhyme` value that starts with `-` needs `=` (`--rhyme=-A-A`), or use
`.A.A`.

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
with a candidates file.

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

* Russian: ё is restored only where the dictionary is sure.
* Russian: stress is marked only on words whose stress is ambiguous or
  guessed, by a capital vowel (the convention Suno users rely on) or with
  `--stress acute`.
* Armenian: kept in script, written with every sung schwa (linking schwas
  dropped, as they are in speech), or romanized.
* Section tags in Russian or Armenian are translated to Suno's names. An
  untagged song gets `[Verse n]` and `[Chorus]` from its repeated stanzas.

Suno does not document its pronunciation, so `probe` measures it:

```bash
ashugh probe make սպասել Մկրտիչ --lang hy --lyrics probes/   # one clip lyric per spelling
# generate each clip in Suno, save as probes/<id>.mp3
ashugh probe transcribe probes/ --plan probes.json           # Whisper (pip install openai-whisper)
ashugh probe score probes.json transcripts.json -o policy.json
ashugh suno song.hy.txt --policy policy.json                  # the winning spelling, word by word
```

The score is how close each transcript, analyzed by ashugh, comes to the
intended sung form. Transcripts use normal spelling, so this measures
intelligibility rather than every sung schwa.

## Agents and editors

* **Claude skill.** `python scripts/build_skill.py` writes
  `dist/ashugh-skill.zip`. Upload it in Claude under Settings > Capabilities >
  Skills, or copy `dist/ashugh` to `~/.claude/skills/` for Claude Code. It
  bundles the tool and tells Claude to draft, scan, repair with `requests` and
  `pick`, and re-scan before it shows you a song. See
  [skill/SKILL.md](skill/SKILL.md).
* **MCP.** `claude mcp add ashugh -- ashugh mcp` gives an agent the tools
  `scan`, `syllables`, `rhyme`, `pick`, `suno`, `derive_spec` and
  `spec_template`.
* **Language server.** `ashugh lsp` underlines the lines that do not scan and
  shows on hover how a line is sung. The spec is the file's sibling `.toml`
  (song.txt -> song.toml) or the nearest `ashugh.toml`.

## How well it works

All numbers are from the scripts in [eval/](eval/), on this commit.

**Russian, on RIFMA** (Koziev 2025: 5,121 poems and stanzas with every
stress marked by hand and a rhyme scheme; `python eval/rifma.py`):

| | |
|---|---|
| stress of polysyllabic words (60,863) | **97.0%** correct |
| each word's first reading, without meter or rhyme | 91.8% |
| words the dictionary lists | 98.1% |
| ambiguous words, resolved by meter and rhyme | 94.2% |
| unknown words (9%), guessed from the ending, meter and rhyme | 88.2% |
| "these two lines rhyme", pairs within a stanza | precision 0.94, recall 0.88, F1 0.91 |

RIFMA was also the development set for the Russian rules, so these numbers
are not from unseen data.

**Armenian sung syllables** (`python eval/armenian.py`). On 68 words that
each exercise one schwa rule (eval/data/hy_gold.tsv, checked by hand),
ashugh matches every syllabification. espeak-ng, the reference
phonemizer, gets 82% of the syllable counts. It misses two schwas in
Մկրտիչ, the possessive schwa in սիրտս, and rising final clusters like աստղ.
The gold list was written together with the rules, so treat ashugh's 100% as
a regression test, not as an independent measurement.

**Words outside the dictionaries**, held out (`python eval/oov.py`): the
stress-by-ending prior gets 75.7% of Russian words right (always guessing the
commonest position: 40.8%) and 77.0% of English words (66.7%). The English
syllable count from spelling is right for 87.7% of words.

## How it works

**Armenian** (`lang/hy.py`). Letters become phonemes: word-initial ե is
[je] and ո is [vo], ու is one vowel, and և splits into e + v. Then every
consonant cluster is split into a coda, an onset and as few schwa syllables
as possible:

- a word-initial ս, զ or շ before a stop takes a schwa in front of it:
  ըս-պա-սել, ըզ-գեստ, and ըս-կը-սել when the cluster goes on;
- an onset is one consonant, or a consonant plus յ (կյանք, -թյուն);
- a coda is at most two consonants that do not rise in sonority (սիրտ,
  միտք), so տետր is տե-տըր and աստղ is աս-տըղ;
- a final ս or դ after an obstruent is the possessive and takes a schwa
  (սիր-տըս, գը-լու-խըդ);
- among equal splits, the onset with յ wins, then the split whose codas
  are longest reading from the right: մը-կըր-տիչ, ա-դըր-բե-ջան.

In connected speech, a vowel before a word swallows its leading ը (նա
ստացավ), and a final schwa syllable links onto a vowel after it (կյանքն է).
The check uses whichever length fits the slot. Stress falls on the last full
vowel, or where a ՛ ՜ ՞ mark puts it. The auxiliary եմ/ես/է… is an unstressed
enclitic that rhymes with the word before it.

**Russian** (`lang/ru.py`). Stress comes from, in order:

1. a mark in the text;
2. the spec's `[lexicon]`;
3. 559,393 stressed forms from OpenRussian, with ё restored (еще becomes
   ещё) and the past tenses the dump leaves out derived from the infinitive;
4. the dictionary twin of a poetic or derived form: мгновенье, мглою,
   сильней, -ся, не-;
5. the verb forms that share a gerund's or participle's stress: теряя from
   теряю, начав from начать, создавший from создать;
6. else a prior learned from word endings, which the meter can overrule.

After в, во and на, about a hundred nouns take the stressed second locative
(на берегу́, в саду́, в крови́). At the end of a line, the rhyme partner picks between readings the meter
allows equally: облака́ / издалека́. A phonetic transcription reduces
unstressed vowels, devoices and assimilates obstruents, and drops silent
consonants (сердце, солнце, честный). Where the text writes е and the
dictionary restores ё, a rhyme may still read е, as older verse does
(безнадежной / нежный).

**English** (`lang/en.py`). Pronunciations come from CMUdict (126k words),
with primary and secondary stress. A variant with one vowel fewer (every,
fire, temperate) makes a droppable syllable; a variant that spells out an
abbreviation (us as U.S.) does not count. Unknown words are counted from
their spelling and stressed by the ending prior. A preposition that ends a
line takes the stress (ships gone by / sky).

**Meter** (`meter.py`). Each syllable position is a strong or a weak beat.
Fitting a line picks a reading for every ambiguous word and prices the
mismatches:

- a polysyllable stressed on a weak beat costs the most;
- a skipped beat (pyrrhic) is cheap in binary meters;
- monosyllables, function words and secondary stresses may take either beat;
- the last stress must land on a beat.

English verse licences cost a little: a line may open on an inverted foot
(Sometime too hot the eye of heaven shines), a compound may move its stress
to its second part (sometíme), and the last beat may fall on a final syllable
two after the stress (témperàte), which can then carry the rhyme
(memory / free).

Detection compares iamb, trochee, dactyl, amphibrach, anapest and dolnik,
and falls back to free verse.

**Rhyme** (`rhyme.py`). A tail runs from the last stressed vowel to the end
of the line, enclitics included. Two tails score by their stressed vowels
and a feature-weighted alignment of what follows, where reduced vowels after
the stress count half. Russian and Armenian open rhymes also need the
consonant before the vowel (ты / красоты).

## Limits

- Armenian schwas that come from morphology rather than from the cluster are
  missed: կայսրություն keeps the schwa of կայսր. Fix them in `[lexicon]`.
- Only Eastern Armenian. Western Armenian is not supported yet.
- Russian stress shifts onto prepositions (и́з лесу, на́ гору) are not
  modeled.
- Rhyme is judged within a stanza, so the cross-stanza rhymes of a sonnet
  (ABBA ABBA) go unseen.
- `probe` needs you to generate the clips in Suno; ashugh cannot call Suno.

## Development

```bash
uv venv && uv pip install -e '.[dev]'
.venv/bin/pytest
.venv/bin/ruff check . && .venv/bin/ruff format --check .
```

The data tables are rebuilt by `scripts/build_ru_lexicon.py` (from the
[OpenRussian dump](https://github.com/Badestrand/russian-dictionary)),
`scripts/build_en_lexicon.py` (from
[CMUdict](https://github.com/cmusphinx/cmudict)) and
`scripts/build_suffix_stress.py`.

## License

The code is MIT (see [LICENSE](LICENSE)). The Russian stress table is
derived from OpenRussian (CC BY-SA 4.0), and the English table from CMUdict
(BSD-style). See [NOTICE.md](NOTICE.md).
