---
name: ashugh
description: Checks and repairs song lyrics and verse in Armenian or Russian so they scan and rhyme. Counts sung syllables including Armenian hidden schwas (ը), finds Russian stress from a 557k-form dictionary, fits meter and judges rhyme by sound. Use whenever you write, translate or edit lyrics or poems in Armenian or Russian (Suno songs included), and run it before showing the lyrics to the user.
---

# ashugh: give your lyrics an ear

You see tokens, not syllables or stress, so you cannot tell by reading whether
a line scans. Armenian makes it worse: it sings vowels it does not write
(Մկրտիչ is mə-kər-tich, սպասել is ըս-պա-սել). Russian stress is lexical and
often ambiguous (за́мок / замо́к), and rhyme depends on sound, not spelling.
So never assert a syllable count, a meter or a rhyme yourself. Draft, then
let `ashugh` measure, then repair what it flags.

## Running it

The skill bundles the tool (pure Python ≥ 3.11, no dependencies):

```bash
python3 <skill-dir>/scripts/run_ashugh.py --version
```

Below, `ashugh` means `python3 <skill-dir>/scripts/run_ashugh.py`, or the
`ashugh` command if it is installed.

| Command | What it does |
|---|---|
| `ashugh scan song.txt --spec song.toml` | check every line; exit 1 if any error |
| `ashugh scan song.txt --spec song.toml --json` | the same as JSON, for you to read |
| `ashugh scan - --syllables 8 --meter iamb4 < alts.txt` | check candidate lines from stdin |
| `ashugh scan song.txt -a` | no spec: show counts, stress grid, detected meter and rhyme |
| `ashugh syl "Մկրտիչ սպասել"` | how words are sung: `Մը-կըր-տի́չ ըս-պա-սե́լ` |
| `ashugh rhyme սիրտ կյանք` | rhyme level and score of two words or lines |
| `ashugh spec --lang hy` | print a starter spec |

## Workflow

1. **Fix the form first.** Write a spec (TOML) with the user's constraints:
   syllables per line, meter, rhyme scheme, endings. If they give a reference
   song or a melody, run `ashugh scan reference.txt -a` and copy its counts
   and scheme into the spec. If the user gave no constraints, still scan with
   `-a` and keep lines within a section consistent.
2. **Draft** the lyrics in a file, one line per sung line, with Suno-style
   tags (`[Verse 1]`, `[Chorus]`). Text in parentheses is a backing vocal and
   is not counted.
3. **Scan**: `ashugh scan song.txt --spec song.toml --json`.
4. **Repair** each line with an error:
   - Write 3–5 alternatives that keep the meaning and the rhyme word if it
     was fine. Test them all in one call, one per line on stdin, with the
     slot's rules as flags (`--syllables 8 --meter iamb4`), and keep the
     best passing one.
   - For a broken rhyme, rewrite the weaker line of the pair and check the
     new pair with `ashugh rhyme`. Moving a word to the end of the line, or
     changing an Armenian line's final word, is usually cheaper than
     rewriting the whole line.
   - Armenian: `sings as ըս-պա-սում` shows the hidden schwas that cost
     syllables. Swap the word for one without the cluster, or put a vowel
     before it: after a vowel the leading ը merges (նա ստացավ).
5. **Re-scan the whole song** after every round. Stop when `"ok": true`. If
   three rounds do not converge, show the user what is still failing and ask
   which constraint to relax. Never relax it silently.
6. **Present** the lyrics, then one line such as
   `ashugh: 16/16 lines pass (8 syllables, iamb4, ABAB)`. Mention warnings
   that changed something, e.g. a stress the meter had to guess.

## Reading the report

Each issue has a `code`, a `severity` and a short `message` with `detail`:

| code | means |
|---|---|
| `syllables` | count differs from the slot; detail lists Armenian words with hidden vowels |
| `meter` | a stressed syllable falls on a weak beat; detail shows the stress grid against the meter's |
| `feet` | wrong number of stressed beats |
| `ending` | masculine/feminine/dactylic ending differs from the slot |
| `final` | the line ends in a forbidden letter (e.g. ը) |
| `rhyme` | two lines of a group do not rhyme well enough; detail names the words and the level |
| `stress` | warning: stress unknown and guessed; info: ambiguous stress the meter resolved |
| `script` | warning: digits or words in another script (counted roughly) |

`error`s break the spec, `warning`s make a check unreliable, and `info` notes
record assumptions. The grid uses `/` for a stressed syllable and `x` for an
unstressed one. Rhyme levels from best to worst: perfect, near, slant,
assonance, none.

## The spec

```toml
language = "hy"            # hy | ru (detected per line if omitted)
syllables = 8              # or [8, 8, 8, 6]; lists repeat over the stanza
tolerance = 0
meter = "iamb4"            # iamb trochee dactyl amphibrach anapest dolnik free (+ feet)
rhyme = "ABAB"             # "-" or "." = free line; AbAb also asks f/m endings
endings = "fmfm"           # m masculine, f feminine, d dactylic, - any
min_rhyme = "near"         # perfect | near | slant | assonance
forbid_final = ["ը"]

[section.chorus]           # overrides for [Chorus]; [Verse 2] matches section.verse
syllables = [7, 7, 7, 5]
rhyme = "AABB"

[lexicon]                  # corrections, see below
"կայսրություն" = "կայ-սը-րու-թյուն"
"замок" = "замо́к"
```

On the command line, `--rhyme` values that start with `-` need `=`:
`--rhyme=-A-A`, or write `.A.A`.

## When the tool is wrong

- **Armenian**: the schwa rules work on sound and do not know morphology,
  so a schwa that a derived word inherits from its base (կայսր → կայսրություն)
  can be missed. If you or the user know how a word is sung, add it to
  `[lexicon]` as hyphenated syllables with the hidden ը written out, and say
  so in your reply.
- **Russian**: words missing from the dictionary get a `stress` warning, and
  the meter's guess is used. Correct them in `[lexicon]` with an acute
  (`замо́к`), a capital vowel (`замОк`) or ё. Stress can also be marked
  inline in the lyrics the same way, which Suno honors as well.
- Only Eastern Armenian and Russian are analyzed. Latin-script words get a
  rough vowel-group count and a warning.
