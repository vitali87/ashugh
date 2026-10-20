"""A proposer command that hands fit's requests to an agent through files.

    ASHUGH_PROPOSER_TIMEOUT=7200 ashugh eval run eval/tasks-hard/ru-dog.toml \\
        --writer dir:DRAFTS --modes ashugh \\
        --proposer "cmd:uv run eval/agent_bridge.py BRIDGE ru-dog" -o OUT.json

Each time fit asks for candidates, this writes BRIDGE/<task>-<round>.request.json
(the requests and the proposer's system prompt) and waits until an agent writes
BRIDGE/<task>-<round>.answer.json in the proposer answer format
({"lines": [{"id": "L3", "candidates": [...]}]}), then prints it for fit.
This is how the eval's "with ashugh" runs were made with a coding agent as the
proposer, through the same check, solve and re-ask loop as `ashugh fit`.

    uv run eval/agent_bridge.py --pending BRIDGE

lists the request files that have no answer yet.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from ashugh.proposers import SCHEMA, SYSTEM  # noqa: E402

POLL = 2.0


def pending(folder: Path) -> list[Path]:
    return sorted(
        p
        for p in folder.glob("*.request.json")
        if not p.with_name(p.name.replace(".request.", ".answer.")).exists()
    )


def ask(folder: Path, task: str, payload: dict) -> dict:
    folder.mkdir(parents=True, exist_ok=True)
    k = len(list(folder.glob(f"{task}-*.request.json"))) + 1
    request = folder / f"{task}-{k}.request.json"
    answer = folder / f"{task}-{k}.answer.json"
    body = {"task": task, "round": k, "system": SYSTEM, "answer_format": SCHEMA, **payload}
    request.write_text(json.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8")
    while True:
        if answer.exists():
            try:
                return json.loads(answer.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass  # still being written
        time.sleep(POLL)


def main(argv: list[str]) -> int:
    if len(argv) == 2 and argv[0] == "--pending":
        for p in pending(Path(argv[1])):
            print(p)
        return 0
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    payload = json.load(sys.stdin)
    print(json.dumps(ask(Path(argv[0]), argv[1], payload), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
