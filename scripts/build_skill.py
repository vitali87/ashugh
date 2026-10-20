"""Package ashugh as a Claude skill.

    uv run scripts/build_skill.py

writes dist/ashugh/ (SKILL.md, the ashugh package, scripts/run_ashugh.py) and
dist/ashugh-skill.zip. Upload the zip in Claude (Settings > Capabilities >
Skills), or copy dist/ashugh to ~/.claude/skills/ for Claude Code.
"""

from __future__ import annotations

import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
SKILL = DIST / "ashugh"

RUNNER = '''#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14"
# dependencies = []
# ///
"""Run the ashugh bundled with this skill: uv run scripts/run_ashugh.py ..."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ashugh.cli import main  # noqa: E402

sys.exit(main())
'''


def build() -> Path:
    if SKILL.exists():
        shutil.rmtree(SKILL)
    SKILL.mkdir(parents=True)
    shutil.copy(ROOT / "skill" / "SKILL.md", SKILL / "SKILL.md")
    shutil.copytree(
        ROOT / "src" / "ashugh",
        SKILL / "ashugh",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    shutil.copy(ROOT / "NOTICE.md", SKILL / "NOTICE.md")
    shutil.copy(ROOT / "LICENSE", SKILL / "LICENSE")
    scripts = SKILL / "scripts"
    scripts.mkdir()
    runner = scripts / "run_ashugh.py"
    runner.write_text(RUNNER, encoding="utf-8")
    runner.chmod(0o755)

    archive = DIST / "ashugh-skill.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in sorted(SKILL.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(DIST))
    return archive


if __name__ == "__main__":
    out = build()
    print(f"{out} ({out.stat().st_size / 1e6:.1f} MB)")
