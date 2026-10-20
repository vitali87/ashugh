# Evaluation

Five measurements, each a script you can rerun. Results are in
[RESULTS.md](RESULTS.md).

| script | what it measures | data |
|---|---|---|
| `uv run eval/rifma.py` | Russian stress and rhyme against hand-marked poems | RIFMA (downloaded on first use) |
| `uv run eval/armenian.py` | Armenian sung syllables against a hand-checked list, and espeak-ng | `data/hy_gold.tsv` |
| `uv run eval/wikipron.py` | Armenian sung syllables against Wiktionary, on entries the stem list never saw | WikiPron's Wiktionary scrape (downloaded on first use) |
| `uv run eval/oov.py` | stress and syllables of words the dictionaries lack, on held-out entries | the bundled tables |
| `ashugh eval run TASKS` | how many lines and songs meet their spec, written alone and with ashugh | `tasks/`, `tasks-hard/` |

## Writing tasks

A task is a TOML file: an id, a language, a prompt and a `[spec]` (with
`[spec.section.*]` and `[spec.stanza.*]` tables as in any spec). The writer
gets the prompt and the spec in words (`ashugh.evaluate.brief`), never the
TOML or ashugh itself.

* `tasks/` are twelve everyday forms: one syllable count or one meter and a
  rhyme scheme per song.
* `tasks-hard/` are twelve tasks closer to writing for an existing melody:
  a syllable count per line with set endings, a different form for the
  chorus, dactylic and anapestic meters, Armenian trochees and feminine
  endings, and three translations that keep their source's grid. They were
  written and committed before any draft for them existed.

`ashugh eval run TASKS --writer W --modes alone,ashugh` scores each draft
as written (`alone`) and after `ashugh fit` repairs it (`ashugh`). A line
passes when it has no error; a song passes when every line does. The writer
is Claude by default (`ANTHROPIC_API_KEY`), a command (`cmd:`), or a folder
of drafts (`dir:`); the proposer that answers fit's repair requests is
Claude, a command, or a candidates file.

### Running it with a coding agent instead of an API key

The runs in RESULTS.md were made inside a coding agent, with fresh
subagents (no access to the repository, the tool or this conversation)
playing Claude:

1. One subagent wrote every draft from its brief, cold, into a folder.
2. `ashugh eval run TASKS --writer dir:DRAFTS --modes alone` scored them.
3. For the `ashugh` mode, each task's fit loop ran with
   `--proposer "cmd:uv run eval/agent_bridge.py BRIDGE <task id>"`. The
   bridge writes every round's requests to `BRIDGE/<task>-<round>.request.json`
   and waits for an answer file; a fresh subagent per round read the pending
   requests and wrote the answers, with nothing but the requests to go on.
   Fit checked every candidate, solved the rhyme groups and asked again,
   up to three rounds, exactly as `ashugh fit` does with the API.

`ashugh eval requests` and `ashugh eval apply` are a simpler one-shot
version of step 3 for agents that cannot keep a process waiting.
