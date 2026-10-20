"""Rendering a scan report as text for people or JSON for agents."""

from __future__ import annotations

import json
import unicodedata

from .lang import NAMES
from .scan import LineReport, Report, UnitReport


def _width(s: str) -> int:
    return sum(0 if unicodedata.combining(ch) else 1 for ch in s)


def _pad(s: str, n: int) -> str:
    return s + " " * max(0, n - _width(s))


def _meter_label(u: UnitReport) -> str:
    feet = sorted({lr.fit.feet for lr in u.lines})
    if u.meter == "free":
        return "free verse"
    label = u.meter + (str(feet[0]) if len(feet) == 1 else "")
    return label if u.meter_source == "spec" else f"detected {label}"


def _unit_header(u: UnitReport) -> str:
    name = f"[{u.section}]" if u.section else "[untagged]"
    rhyme = u.scheme
    if u.rule.rhyme:
        rhyme += f" (spec {u.rule.rhyme})"
    return f"{name}  {_meter_label(u)} · {rhyme}"


def _line_row(lr: LineReport) -> str:
    n = f"L{lr.line.number}"
    return f"  {_pad(n, 5)}{lr.fit.count:>2}  {_pad(lr.fit.grid, 14)} {lr.letter or ' '}  {lr.sung}"


def text(report: Report, show_all: bool = False) -> str:
    out = []
    langs = ", ".join(NAMES.get(code, code) for code in report.languages) or "no text"
    head = f"{report.path} · {langs}"
    if report.spec.path:
        head += f" · spec {report.spec.path}"
    elif report.spec.empty:
        head += " · no spec (analysis only)"
    out.append(head)
    show_all = show_all or report.spec.empty
    for u in report.units:
        rows = []
        for lr in u.lines:
            if show_all:
                rows.append(_line_row(lr))
            for issue in lr.issues:
                if issue.severity == "info" and not show_all:
                    continue
                mark = {"error": "", "warning": "warning: ", "info": "note: "}[issue.severity]
                label = f"L{issue.line}" if not show_all else ""
                rows.append(
                    f"  {_pad(label, 5)}{_pad(mark + issue.message, 34)} {issue.detail}".rstrip()
                )
        if rows:
            out.append("")
            out.append(_unit_header(u))
            out.extend(rows)
    total = len(report.lines)
    passing = sum(1 for lr in report.lines if lr.ok)
    errors, warnings = report.count("error"), report.count("warning")
    summary = f"{passing}/{total} lines pass"
    summary += f" · {errors} error{'s' if errors != 1 else ''}"
    if warnings:
        summary += f" · {warnings} warning{'s' if warnings != 1 else ''}"
    out.append("")
    out.append(summary)
    return "\n".join(out)


def _line_dict(lr: LineReport) -> dict:
    t = lr.tail
    return {
        "line": lr.line.number,
        "text": lr.line.text,
        "lang": lr.line.lang,
        "ok": lr.ok,
        "syllables": lr.fit.count,
        "target": lr.target,
        "sung": lr.sung,
        "grid": lr.fit.grid,
        "feet": lr.fit.feet,
        "ending": lr.ending,
        "rhyme": {"letter": lr.letter, "word": t.word, "sound": t.sound} if t else None,
        "words": [
            {
                "text": w.text,
                "syllables": [s.text for s in w.syllables],
                "stress": lr.fit.stresses.get(i),
                "source": w.reading(lr.fit.stresses.get(i)).source if w.readings else None,
            }
            for i, w in enumerate(lr.line.words)
        ],
        "issues": [i.as_dict() for i in lr.issues],
    }


def as_dict(report: Report) -> dict:
    return {
        "file": report.path,
        "spec": report.spec.path,
        "ok": report.ok,
        "summary": {
            "lines": len(report.lines),
            "passing": sum(1 for lr in report.lines if lr.ok),
            "errors": report.count("error"),
            "warnings": report.count("warning"),
        },
        "sections": [
            {
                "section": u.section,
                "key": u.key,
                "meter": u.meter,
                "meter_source": u.meter_source,
                "rhyme_found": u.scheme,
                "rhyme_spec": u.rule.rhyme,
                "lines": [_line_dict(lr) for lr in u.lines],
            }
            for u in report.units
        ],
        "issues": [i.as_dict() for i in report.issues],
    }


def as_json(report: Report) -> str:
    return json.dumps(as_dict(report), ensure_ascii=False, indent=2)
