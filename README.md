# ashugh

**A prosody checker that gives LLM-written lyrics an ear.** Named after the
Armenian troubadours (աշուղ).

LLMs see tokens, not syllables or stress, so they cannot hear whether a line
scans. Armenian makes it worse because it sings vowels it does not write:
Մկրտիչ has one vowel letter and three sung syllables (mə-kər-tich), and
սպասել is sung ըս-պա-սել. Russian stress is lexical and often ambiguous
(за́мок / замо́к), and rhyme there is a matter of sound, not spelling.

ashugh measures instead of guessing. It counts sung syllables, finds stress,
fits lines to a meter, judges rhyme by sound, and checks all of it against a
song spec. The LLM drafts and the phonology verifies.

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

Version 0.1 does `scan` for Eastern Armenian and Russian, as a command-line
tool and as a Claude skill. It is pure Python with no dependencies.

## Install

```bash
pip install git+https://github.com/vitali87/surprise
# or: uv tool install git+https://github.com/vitali87/surprise
```

Python 3.11 or newer is required.

## Use

```bash
ashugh scan song.txt --spec song.toml    # check a song; exit 1 on errors
ashugh scan song.txt -a                  # no spec: counts, stress, meter, rhyme
ashugh scan song.txt --spec song.toml --json
ashugh scan - --syllables 8 --meter iamb4 < candidates.txt
ashugh syl Մկրտիչը կյանքն է սիրում       # how a line is sung
ashugh rhyme сердце дверце               # perfect 1.00  sʲertsɨ / vʲertsɨ
ashugh spec --lang ru > song.toml        # starter spec
```

`scan -a` shows every line with its syllable count, stress grid (`/`
stressed, `x` unstressed), rhyme letter and sung spelling:

```
[Verse 1]  detected dolnik · ABAB
  L2    8  x/x/xxx/       A  Գի-շերն ի-ջավ մեր քա-ղա-քին
  L3    9  xxx/xx/x/      B  Ու ես նո-րից ըս-պա-սում եմ քեզ
  L4    8  x/xx/xx/       A  Լու-սի-նը շո-ղաց տա-նի-քին
  L5    8  xx/x/x//       B  Ու քա-մին նո-րից կան-չեց մեզ
```

Lyrics files follow the Suno conventions. `[Verse 1]`, `[Chorus]` and other
tags open sections, a blank line ends a stanza, and text in parentheses is a
backing vocal that is left out of the count.

### The spec

```toml
language = "ru"            # hy | ru; detected per line if omitted
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

[lexicon]                  # how a word is really sung, when ashugh gets it wrong
"կայսրություն" = "կայ-սը-րու-թյուն"
"замок" = "замо́к"
```

Top-level keys apply to every section, and `[section.<name>]` overrides them.
Command-line flags (`--syllables`, `--meter`, `--rhyme`, `--endings`,
`--tolerance`, `--min-rhyme`, `--forbid-final`) override both. A `--rhyme`
value that starts with `-` needs `=` (`--rhyme=-A-A`), or use `.A.A`.

The Russian example shows meter checks:

```
$ ashugh scan examples/song.ru.txt --spec examples/song.ru.toml
[Verse 1]  iamb · ABCB (spec AbAb)
  L4   rhyme A broken                     «окон» / «строгий»: assonance 0.35, need near
  L5   last stress off the beat           stress x/x/xx/, iamb wants x/x/x/x
  L5   3 feet, slot is 4                  7 syllables; iamb4 with a masculine ending has 8

[Chorus]  iamb · ABCB (spec AbAb)
  L10  «се́рд-це», «бьёт-ся» off the beat  stress x/x//x/x, iamb wants x/x/x/x/
  ...
```

## Claude skill

```bash
python scripts/build_skill.py      # -> dist/ashugh-skill.zip and dist/ashugh/
```

Upload `dist/ashugh-skill.zip` in Claude under Settings > Capabilities >
Skills, or copy `dist/ashugh` to `~/.claude/skills/` for Claude Code. The
skill tells Claude to draft, scan, try alternatives for failing lines, and
re-scan until the song passes, before showing it to you. See
[skill/SKILL.md](skill/SKILL.md).

## How it works

**Armenian** (`src/ashugh/lang/hy.py`). Letters become phonemes (word-initial
ե is [je] and ո is [vo]; ու is one vowel; և splits into e + v). Then every
consonant cluster is split into a coda, an onset and as few schwa syllables
as possible:

- a word-initial ս, զ or շ before a stop takes a schwa in front of it:
  ըս-պա-սել, ըզ-գեստ, and ըս-կը-սել when the cluster goes on;
- an onset is one consonant, or a consonant plus յ (կյանք, -թյուն);
- a coda is at most two consonants that do not rise in sonority (սիրտ, միտք),
  so տետր is տե-տըր and աստղ is աս-տըղ;
- a word-final ս or դ after an obstruent is the possessive and takes a schwa
  (սիր-տըս, գը-լու-խըդ);
- among equal splits the onset with յ wins, then the split whose codas are
  longest reading from the right: մը-կըր-տիչ, ա-դըր-բե-ջան.

In connected speech a vowel before a word swallows its leading ը (նա
ստացավ), and a final schwa syllable links onto a following vowel (կյանքն է).
These give a line more than one length, and the check uses whichever length
fits the slot. Stress falls on the last syllable whose vowel is not a schwa,
or where a ՛ ՜ ՞ mark puts it. The auxiliary եմ/ես/է... is an unstressed
enclitic, so it rhymes with the word before it.

**Russian** (`src/ashugh/lang/ru.py`). Stress comes from, in this order:

1. a mark in the text: an acute, ё, or a single capital vowel (замОк);
2. the spec's `[lexicon]`;
3. a table of 557,501 stressed word forms built from OpenRussian, with ё
   restored (еще becomes ещё; все may be все or всё);
4. poetic and derived forms looked up through their dictionary twin
   (мгновенье, мглою, сильней, -ся, не-);
5. otherwise every vowel is a candidate, the meter picks one, and the report
   warns.

A phonetic transcription reduces unstressed vowels, devoices and assimilates
obstruents, and drops silent consonants (сердце, солнце, честный), so rhyme
is judged by sound.

**Meter** (`src/ashugh/meter.py`). Each syllable position is a strong or a
weak beat. Fitting a line picks a reading for each ambiguous word and prices
the mismatches:

- a polysyllable stressed on a weak beat costs the most;
- a skipped beat (pyrrhic) is cheap in binary meters;
- monosyllables and function words may take either beat;
- the last stress must land on a beat.

Detection compares iamb, trochee, dactyl, amphibrach, anapest and dolnik, and
falls back to free verse.

**Rhyme** (`src/ashugh/rhyme.py`). A rhyme tail runs from the last stressed
vowel to the end of the line, enclitics included. Two tails score by vowel
match and a feature-weighted alignment of what follows. Open masculine
rhymes also need the consonant before the vowel (ты / красоты).

## Limits

- Schwas that come from morphology rather than from the cluster are missed,
  for example կայսրություն keeping the schwa of կայսր. Fix them in
  `[lexicon]`.
- Russian stress shifts onto prepositions (и́з лесу, на́ гору) are not
  modeled.
- Eastern Armenian only; Western Armenian is not supported yet.
- Words in other scripts get a rough vowel-group count and a warning.

## Roadmap

- `fit`: the LLM proposes candidates for failing lines, the engine keeps the
  ones that scan, and CP-SAT picks the combination that keeps rhyme pairs
  intact.
- `translate`: singable translation between English, Russian and Armenian,
  using the source's syllable grid and rhyme scheme as the target spec.
- `suno`: stress hints, ё restoration, script choices and section tags that
  Suno sings correctly, measured with Whisper round trips.
- An MCP server and a language server.
- An evaluation: the share of lines that meet the spec, Claude alone versus
  Claude with ashugh, on Tumanyan, Teryan and the RIFMA stanzas.

## Development

```bash
uv venv && uv pip install -e '.[dev]'
.venv/bin/pytest
.venv/bin/ruff check . && .venv/bin/ruff format --check .
```

`scripts/build_ru_lexicon.py` rebuilds the Russian stress table from the
[OpenRussian dump](https://github.com/Badestrand/russian-dictionary).

## License

The code is MIT (see [LICENSE](LICENSE)). The Russian stress table
`src/ashugh/data/ru_stress.tsv` is derived from OpenRussian and is licensed
CC BY-SA 4.0 (see [NOTICE.md](NOTICE.md)).
