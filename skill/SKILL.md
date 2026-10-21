---
name: ashugh
description: Checks and repairs song lyrics and verse in Armenian, Russian or English so they scan and rhyme, and rewrites them for Suno. Counts sung syllables including Armenian hidden schwas (ը), finds Russian stress from a 559k-form dictionary and English stress from CMUdict, fits meter, judges rhyme by sound, translates songs into the same syllable grid. Use whenever you write, translate or edit lyrics or poems in these languages (Suno songs included), and run it before showing the lyrics to the user.
---

# ashugh: give your lyrics an ear

You see tokens, not syllables or stress, so you cannot tell by reading whether
a line scans. Armenian makes it worse: it sings vowels it does not write
(Մկրտիչ is mə-kər-tich, սպասել is ըս-պա-սել). Russian stress is lexical and
often ambiguous (за́мок / замо́к), and rhyme is about sound, not spelling.
So never assert a syllable count, a meter or a rhyme yourself. Draft, let
`ashugh` measure, and repair what it flags.

## Running it

The skill bundles the tool (pure Python, no dependencies). uv runs it and
fetches Python 3.14 if the machine lacks it:

```bash
uv run <skill-dir>/scripts/run_ashugh.py --version
```

Below, `ashugh` means `uv run <skill-dir>/scripts/run_ashugh.py`, or the
`ashugh` command if it is installed (`uv tool install`). Without uv, a
Python 3.14 runs the same script directly.

| Command | What it does |
|---|---|
| `ashugh scan song.txt --spec song.toml` | check every line; exit 1 if any error |
| `ashugh scan song.txt --spec song.toml --json` | the same as JSON, for you to read |
| `ashugh scan song.txt -a` | no spec: counts, stress grid, detected meter and rhyme |
| `ashugh requests song.txt --spec song.toml` | the failing lines with their constraints, as JSON |
| `ashugh pick song.txt --spec song.toml --candidates c.json -o fixed.txt` | choose among your candidate lines so the song passes |
| `ashugh syl "Մկրտիչ սպասել"` | how words are sung: `Մը-կըր-տի́չ ըս-պա-սե́լ` |
| `ashugh rhyme սիրտ կյանք` | rhyme level and score of two words or lines |
| `ashugh spec --from source.txt --keep syllables,rhyme --lang hy` | the spec that reproduces a song's form |
| `ashugh suno song.txt --spec song.toml` | the lyrics rewritten for Suno |
| `ashugh spec --lang hy` | a starter spec |

## Workflow

1. **Fix the form first.** Write a spec (TOML) with the user's constraints:
   syllables per line, meter, rhyme scheme, endings. If they give a reference
   song or a melody, use `ashugh spec --from reference.txt` to copy its form.
   If the user gave no constraints, still scan with `-a` and keep lines
   within a section consistent.
2. **Draft** the lyrics in a file, one line per sung line, with Suno-style
   tags (`[Verse 1]`, `[Chorus]`). Text in parentheses is a backing vocal and
   is not counted.
3. **Scan**: `ashugh scan song.txt --spec song.toml --json`.
4. **Repair**, at most three rounds:
   - `ashugh requests song.txt --spec song.toml` lists every failing line,
     and the partners of a broken rhyme even where they pass (changing those
     is optional), with what each must satisfy: `syllables`, the stress
     `template` ("/" a beat, where a stressed syllable belongs and a
     one-syllable word may also sit unstressed; "x" an off-beat, where no
     word's own stress may fall), `rhyme_with` (the words of the partners
     that stay) and `rhyme_sound` (the rime to match; when `rhyme_with` is
     empty it is the line's own rhyme, to keep), `ending`, `avoid_final`,
     and the `problems` found, including partners that must change too.
   - For each request write 4–6 alternatives that keep the meaning and the
     voice of the song. Put them in a JSON file keyed by line number:
     `{"3": ["...", "..."], "11": ["..."]}`. Including the original line is
     not needed; ashugh keeps it when it still passes on its own.
   - `ashugh pick song.txt --spec song.toml --candidates c.json -o song.txt`
     checks every candidate, picks one per line so that rhyme groups hold,
     and keeps the most faithful combination. It prints what is unresolved.
   - For Armenian, `sings as ըս-պա-սում` in a problem names the hidden schwas
     that cost syllables: swap the word for one without the cluster, or put
     a vowel before it (after a vowel the leading ը merges: նա ստացավ).
5. **Re-scan the whole song.** Stop when `"ok": true`. If three rounds do not
   converge, show the user what is still failing and ask which constraint to
   relax. Never relax it silently.
6. **For Suno**, run `ashugh suno song.txt --spec song.toml` and give the user
   that text: it restores ё, marks only the ambiguous Russian stresses (зАмок),
   and normalizes section tags. `--armenian schwa` spells out the hidden
   vowels for Suno; `--armenian latin` romanizes.
7. **Present** the lyrics, then one line such as
   `ashugh: 16/16 lines pass (8 syllables, iamb4, ABAB)`. Mention warnings
   that changed something, e.g. a stress the meter had to guess.

## Translating a song

To sing the translation to the same melody, keep the stresses and endings as
well as the counts and rhymes:

```bash
ashugh spec --from source.txt --keep syllables,meter,rhyme,endings --lang ru > target.toml
```

turns the source's form into a spec with one `[stanza.N]` table per stanza
(a stanza whose lines do not all keep one meter gets its counts without it).
Translate line by line into a draft, then run the repair loop above against
`target.toml`. Or let ashugh hold the translation loop: write your candidate
translations per source line in a JSON file as for `pick`, then

```bash
ashugh translate source.txt --to ru --keep syllables,meter,rhyme,endings \
  --proposer file:candidates.json -o song.ru.txt
```

checks them against the source's grid and picks the combination that holds.
`--keep syllables,rhyme` alone fits the counts and rhymes but not the
stresses, so the words may not sit on the melody's beats.

## Reading the report

Each issue has a `code`, a `severity` and a short `message` with `detail`:

| code | means |
|---|---|
| `syllables` | count differs from the slot; detail lists Armenian words with hidden vowels; info: the line fits only if a schwa drops |
| `meter` | a stressed syllable falls on a weak beat; detail shows the stress grid against the meter's |
| `feet` | wrong number of stressed beats |
| `ending` | masculine/feminine/dactylic ending differs from the slot |
| `final` | the line ends in a forbidden letter (e.g. ը) |
| `rhyme` | two lines of a group do not rhyme well enough; detail names the words and the level |
| `stress` | warning: stress unknown and guessed; info: ambiguous stress the meter resolved |
| `script` | warning: digits or words in a script ashugh does not analyze |
| `scheme` | warning: a stanza has a different number of lines than its rhyme scheme |
| `spec` | warning: a `[section.X]` or `[stanza.N]` table that matches nothing (a typo such as `[section.chorsu]`) |
| `translate` | error: no candidate came back for a line of a translation |

`error`s break the spec, `warning`s make a check unreliable, and `info` notes
record assumptions. Rhyme levels from best to worst: perfect, near, slant,
assonance, none.

## The spec

```toml
language = "hy"            # hy | ru | en (detected per line if omitted)
syllables = [9, 8, 9, 8]   # or 8 for every line; lists repeat over the stanza
tolerance = 0
meter = "iamb4"            # iamb trochee dactyl amphibrach anapest dolnik free (+ feet)
rhyme = "ABAB"             # "-" or "." = free line; AbAb also asks endings:
                           # a capital letter feminine, a small one masculine
                           # "ABBA ABBA CDC DCD": one part per stanza, letters shared
endings = "fmfm"           # m masculine, f feminine, d dactylic, h 3+ after, - any
                           # (iamb4 is 8 syllables masculine, 9 feminine)
min_rhyme = "near"         # perfect | near | slant | assonance
forbid_final = ["ը"]

[section.chorus]           # overrides for [Chorus], [Припев], [Կրկներգ]; [Verse 2] is section.verse
syllables = [7, 7, 7, 5]
meter = "trochee"
feet = [4, 4, 4, 3]        # trochee: 7 syllables in four feet, masculine; 5 in three
endings = "m"
rhyme = "AABB"

[stanza.3]                 # overrides for the third stanza only
syllables = [9, 8, 9, 8]

[lexicon]                  # corrections, see below
"կայսրություն" = "կայ-սը-րու-թյուն"
"замок" = "замо́к"
```

On the command line, `--rhyme` values that start with `-` need `=`:
`--rhyme=-A-A`, or write `.A.A`.

## When the tool is wrong

- **Armenian**: the schwa rules work on sound and do not know morphology,
  so a schwa a derived word inherits from its base (կայսր → կայսրություն)
  can be missed. If you or the user know how a word is sung, add it to
  `[lexicon]` as hyphenated syllables with the hidden ը written out, and say
  so in your reply.
- **Russian**: words missing from the dictionary get a `stress` warning, and
  a guess from the word's ending, overruled by the meter where it can be.
  Correct them in `[lexicon]` with an acute (`замо́к`), a capital vowel
  (`замОк`) or ё. Stress can also be marked inline in the lyrics.
- **English**: words missing from CMUdict are counted from their spelling and
  warned about; give a pronunciation in `[lexicon]` as ARPABET with stress
  digits, e.g. `"zorblax" = "Z AO1 R B L AE0 K S"`.
