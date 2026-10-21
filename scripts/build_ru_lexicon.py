"""Build ashugh's Russian stress table from the OpenRussian dictionary dump.

The source is https://github.com/Badestrand/russian-dictionary (CC BY-SA 4.0):
nouns.csv, verbs.csv, adjectives.csv and others.csv, tab separated, with every
inflected form written with an apostrophe after the stressed vowel.

    uv run scripts/build_ru_lexicon.py path/to/russian-dictionary

writes src/ashugh/data/ru_stress.tsv: one form per line, sorted by UTF-8 bytes,
followed by a tab and the 1-based positions of its stressed vowels ("21" means
the form is stressed on the second vowel in one reading and the first in
another), the usual reading first (see build), each followed by v where only
a verb form has that stress and the form has another ("2v1" for полю: полю́,
I weed, and по́лю), so a reading after a preposition can leave it out. Forms
with one vowel are left out unless they contain ё, because their stress
carries no information but their ё does.

It also writes src/ashugh/data/ru_derived.tsv, in the same format: regular forms
the dump leaves out (scripts/ru_forms.py), derived from its lemmas, wherever the
dump lists no form with the same spelling; ashugh reads it after ru_stress.tsv,
and the suffix prior learns from ru_stress.tsv alone. And it writes
src/ashugh/data/ru_yo.tsv: the one-vowel forms that exist only
with ё (ждёт, шёл, лёд), one per line, so that ждет written without its ё
reads as ждёт. A form whose е spelling is a word too (всё and все) is left out.
"""

from __future__ import annotations

import csv
import re
import sys
from collections import defaultdict
from pathlib import Path

import ru_forms

VOWELS = set("аеёиоуыэюя")
FILES = ("nouns.csv", "verbs.csv", "adjectives.csv", "others.csv")
NOT_FORMS = {
    "bare",
    "translations_en",
    "translations_de",
    "gender",
    "partner",
    "animate",
    "indeclinable",
    "sg_only",
    "pl_only",
    "aspect",
}
FORM_RE = re.compile(r"[а-яё'\-]+")
# Rare words whose forms are spelt like a common word's and stressed otherwise: the
# sthene (сте́не) is no reading of стене́, the wall's.
OBSOLETE = {"стен"}
OUT = Path(__file__).resolve().parent.parent / "src" / "ashugh" / "data" / "ru_stress.tsv"
YO_OUT = OUT.with_name("ru_yo.tsv")
DERIVED_OUT = OUT.with_name("ru_derived.tsv")


def stress_positions(form: str) -> tuple[str, set[int], int]:
    """The bare form, its stressed vowels and its vowel count. In a compound without
    a hyphen that marks one vowel and has an ё elsewhere, the later of the two is
    the stress and the earlier the first part's: трёхэта́жный, госсекретарём (the
    dump's го'ссекретарём). A hyphenated form keeps both (чёрно-бе́лый)."""
    marks: set[int] = set()
    yos: set[int] = set()
    count = 0
    for i, ch in enumerate(form):
        if ch in VOWELS:
            count += 1
            # the mark follows its vowel, or in a few rows (такс'ист) comes before it
            if form[i + 1 : i + 2] == "'" or (
                form[i - 1 : i] == "'" and form[i - 2 : i - 1] not in VOWELS and i > 1
            ):
                marks.add(count)
            elif ch == "ё":
                yos.add(count)
    positions = marks | yos
    if marks and yos and "-" not in form:
        if max(yos) < min(marks):
            positions = marks
        elif min(yos) > max(marks):
            positions = yos
    return form.replace("'", ""), positions, count


def past_forms(infinitive: str) -> list[str]:
    """The past tense of a verb whose dump row lists none, stressed like its infinitive.

    Only -ть and -ться verbs with a vowel before the ending and a stress mark
    qualify; -сть, -сти and -чь verbs change their stem in the past.
    """
    if "'" not in infinitive and "ё" not in infinitive:
        return []
    if infinitive.endswith("ться"):
        stem, endings = infinitive[:-4], ("лся", "лась", "лось", "лись")
    elif infinitive.endswith("ть"):
        stem, endings = infinitive[:-2], ("л", "ла", "ло", "ли")
    else:
        return []
    if not stem.rstrip("'") or stem.rstrip("'")[-1] not in VOWELS:
        return []
    return [stem + e for e in endings]


# Verb prefixes, longest first. A prefixed verb whose base ends its feminine past on
# the ending (звала́, ждала́, мела́) does too (позвала́, дождала́сь, замела́), where the
# dump often has only the stem stress; that reading stays second, as verse and speech
# use it too (призва́ла / нача́ло). The bases are the verbs whose past moves its
# stress (Zaliznyak's past pattern c, and -сти, -зти and -чь verbs); родить and стричь
# are not among them (породи́ла, остри́гла). вы- takes the stress itself (вы́звала), and
# забыть keeps забы́ла, unlike была́.
PREFIXES = sorted(
    "пере пред при про пре разо раз рас без бес взо воз вос вз вс изо из ис недо "
    "надо над подо под обо об ото от по до за на со с у о во в".split(),
    key=len,
    reverse=True,
)
STEM_FEMININE = {"забыть", "забыться"}
MOBILE = set(
    "брать быть взять вить врать гнать дать драть ждать жить звать лгать лить пить плыть "
    "рвать слыть спать ткать жрать стлать клясть вести мести нести плести грести цвести "
    "брести трясти везти ползти расти печь течь мочь лечь жечь беречь стеречь сечь".split()
)


def end_feminines(source: Path) -> dict[str, tuple[str, int, str]]:
    """The MOBILE verbs whose feminine past is stressed on its last vowel:
    infinitive -> (the form, its vowel count, the first person present)."""
    csv.field_size_limit(sys.maxsize)
    out: dict[str, tuple[str, int, str]] = {}
    with open(source / "verbs.csv", encoding="utf-8", newline="") as fh:
        rows = csv.reader(fh, delimiter="\t")
        header = next(rows)
        if "past_f" not in header:
            return out
        at = header.index("past_f")
        for row in rows:
            infinitive = row[0].strip().lower() if row else ""
            if infinitive not in MOBILE or at >= len(row):
                continue
            for variant in re.split(r"[,;/]", row[at]):
                form = variant.strip().lower().replace("\u0301", "'")
                bare, positions, count = stress_positions(form)
                if count and positions == {count} and FORM_RE.fullmatch(form):
                    out[infinitive] = (bare, count, _first_person(header, row))
    return out


def _first_person(header: list[str], row: list[str]) -> str:
    if row and row[0].strip() == "быть":
        return "буду"  # the dump gives есть, which no prefixed быть conjugates like
    at = header.index("presfut_sg1") if "presfut_sg1" in header else len(row)
    form = row[at].split(",")[0].strip().lower().replace("'", "") if at < len(row) else ""
    return form.removesuffix("сь").removesuffix("ся")


def feminine_like_base(
    infinitive: str, form: str, bases: dict[str, tuple[str, int, str]], first: str = ""
) -> str | None:
    """form, the past of infinitive, stressed on its ending where its base's feminine
    is, or None. first, the verb's first person present, must end like the base's:
    позову and зову, but not воплю and пью (вопить is no во- with пить)."""
    bare = form.replace("'", "")
    if infinitive in STEM_FEMININE:
        return None
    reflexive = infinitive.endswith(("ся", "сь"))
    stem = infinitive[:-2] if reflexive else infinitive
    for prefix in PREFIXES:
        if prefix == "вы" or not stem.startswith(prefix) or stem[len(prefix) :] not in bases:
            continue
        base, count, base_first = bases[stem[len(prefix) :]]
        if first and base_first and not first.endswith(base_first):
            continue
        if bare == prefix + base + ("сь" if reflexive else ""):
            target = sum(ch in VOWELS for ch in prefix) + count
            out, seen = [], 0
            for ch in bare:
                out.append(ch)
                seen += ch in VOWELS
                if ch in VOWELS and seen == target and ch != "ё":
                    out.append("'")
            return "".join(out)
    return None


def all_forms(source: Path) -> set[str]:
    """Every form the dump lists, without its stress marks."""
    csv.field_size_limit(sys.maxsize)
    out: set[str] = set()
    for name in FILES:
        with open(source / name, encoding="utf-8", newline="") as fh:
            rows = csv.reader(fh, delimiter="\t")
            header = next(rows)
            columns = [i for i, h in enumerate(header) if h not in NOT_FORMS]
            for row in rows:
                for variant in (
                    v for i in columns if i < len(row) for v in re.split(r"[,;/]", row[i])
                ):
                    form = variant.strip().lower().replace("\u0301", "").replace("'", "")
                    form = form.replace("*", "")
                    if form and FORM_RE.fullmatch(form):
                        out.add(form)
    return out


def yo_only(forms: set[str]) -> list[str]:
    """One-vowel forms with ё whose е spelling is no form of its own."""
    return sorted(
        (
            f
            for f in forms
            if "ё" in f and sum(ch in VOWELS for ch in f) == 1 and f.replace("ё", "е") not in forms
        ),
        key=lambda f: f.encode(),
    )


def column_rank(column: str) -> int:
    """How usual a form of this column is, lower first: a nominative or a verb form
    (руки́ of рука́ is a genitive, ру́ки the plural; е́ду a verb, еду́ of еда́ an
    accusative), then accusatives, comparatives and adjective forms, then the
    other cases and short forms (до́лги beside долги́ of долг)."""
    if column.endswith("_nom") or column.startswith(("presfut", "past", "imperative")):
        return 1
    if column.endswith("_acc") or column == "comparative" or column.startswith("decl_"):
        return 2
    return 3


VERB_COLUMNS = ("presfut", "past", "imperative")


def build(source: Path) -> dict[str, list[int]]:
    """Each form's stressed vowels, the usual reading first: a headword's own
    stress (вода́, the noun, before во́да of вод), then by column_rank (глаза́ the
    plural before гла́за the genitive), so a reading the line leaves open is the
    common one."""
    return {form: [p for p, _ in entry] for form, entry in ranked(source).items()}


def ranked(source: Path) -> dict[str, list[tuple[int, bool]]]:
    """build's table with each stress marked True where only a verb form has it
    (полю́, I weed, beside по́лю of по́ле): no reading after a preposition."""
    csv.field_size_limit(sys.maxsize)
    rank: dict[str, dict[int, int]] = defaultdict(dict)
    nominal: dict[str, set[int]] = defaultdict(set)  # stresses some non-verb form has

    def add(bare: str, positions: set[int], r: int, verb: bool) -> None:
        for p in positions:
            rank[bare][p] = min(rank[bare].get(p, r), r)
            if not verb:
                nominal[bare].add(p)

    bases = end_feminines(source)
    for name in FILES:
        with open(source / name, encoding="utf-8", newline="") as fh:
            rows = csv.reader(fh, delimiter="\t")
            header = next(rows)
            columns = [i for i, h in enumerate(header) if h not in NOT_FORMS]
            past = header.index("past_m") if "past_m" in header else None
            accented = header.index("accented") if "accented" in header else None
            for row in rows:
                if row and row[0].strip().lower() in OBSOLETE:
                    continue
                forms = [
                    (v, header[i])
                    for i in columns
                    if i < len(row)
                    for v in re.split(r"[,;/]", row[i])
                ]
                verb_row = past is not None
                if accented is not None and accented < len(row):
                    head = row[accented].strip().lower().replace("\u0301", "'")
                    if FORM_RE.fullmatch(head):
                        bare, positions, count = stress_positions(head)
                        if positions and (count >= 2 or "ё" in bare):
                            add(bare, positions, 0, verb_row)
                listed_past = "".join(row[past : past + 1]).strip() if past is not None else "?"
                if accented is not None and not listed_past:
                    forms += [(f, "past") for f in past_forms(row[accented].strip().lower())]
                infinitive = row[0].strip().lower() if past is not None and row else ""
                first = _first_person(header, row) if infinitive else ""
                for variant, column in forms:
                    form = variant.strip().lower().replace("\u0301", "'").replace("*", "")
                    verb = column.startswith(VERB_COLUMNS)
                    norm = infinitive and feminine_like_base(infinitive, form, bases, first)
                    if norm:  # позвала́ before позва́ла
                        bare, positions, _ = stress_positions(norm)
                        add(bare, positions, 0, verb)
                    if not FORM_RE.fullmatch(form):
                        continue
                    bare, positions, count = stress_positions(form)
                    if not positions or (count < 2 and "ё" not in bare):
                        continue
                    add(bare, positions, column_rank(column), verb)
    return {
        form: [(p, p not in nominal[form]) for p in sorted(ranks, key=lambda p: (ranks[p], p))]
        for form, ranks in rank.items()
    }


def encode(entry: list[tuple[int, bool]]) -> str:
    """Stresses in order, each followed by v where only a verb form has it and the
    form has another stress too: полю is "1v2" read as 2, then 1 (verb only)."""
    several = len(entry) > 1
    return "".join(f"{p}{'v' if verb and several else ''}" for p, verb in entry)


def extra(source: Path, table: dict[str, list[int]]) -> dict[str, list[int]]:
    """The derived forms (see derived) whose spelling the dump's table lacks, ё read
    as е: нужён, of нудить, would make the dictionary's ну́жен ambiguous."""
    listed = {form.replace("ё", "е") for form in table}
    return {f: p for f, p in derived(source).items() if f.replace("ё", "е") not in listed}


NOUN_FORMS = ("sg_nom", "sg_gen", "sg_dat", "sg_acc", "sg_inst", "sg_prep", "pl_nom", "pl_gen")
DECLENSION = ("decl_m_gen", "decl_m_dat", "decl_f_gen", "decl_pl_gen")


def _rows(source: Path, name: str) -> list[dict[str, str]]:
    with open(source / name, encoding="utf-8", newline="") as fh:
        return [
            {k: (v or "").strip().lower().replace("\u0301", "'") for k, v in row.items() if k}
            for row in csv.DictReader(fh, delimiter="\t")
        ]


def derived(source: Path) -> dict[str, list[int]]:
    """Regular forms the dump leaves out (ru_forms): the declension of an adjective
    or a noun whose row lists none, comparatives (with по-), and participles. The
    caller adds one only where the dump lists no form with its spelling."""
    csv.field_size_limit(sys.maxsize)
    forms: list[str] = []
    comparatives: list[str] = list(ru_forms.IRREGULAR_COMPARATIVES)
    for row in _rows(source, "adjectives.csv"):
        lemma = row.get("accented", "")
        if row.get("bare") in OBSOLETE:
            continue
        if not any(row.get(c) for c in DECLENSION):
            forms += ru_forms.adjective(lemma)
        listed = [v.strip() for v in re.split(r"[,;/]", row.get("comparative", "")) if v.strip()]
        comparatives += listed or ru_forms.comparatives(lemma, row.get("short_f", ""))
    for row in _rows(source, "others.csv"):
        forms += ru_forms.adjective(row.get("accented", ""))
    for row in _rows(source, "nouns.csv"):
        if row.get("bare") not in OBSOLETE and not any(row.get(c) for c in NOUN_FORMS):
            forms += ru_forms.noun(row.get("accented", ""), row.get("gender", ""))
    for row in _rows(source, "verbs.csv"):
        past = row.get("past_m", "")
        forms += ru_forms.past_passive(
            row.get("accented", ""), past, row.get("presfut_sg1", ""), row.get("presfut_sg2", "")
        )
        for variant in re.split(r"[,;/]", past):
            forms += ru_forms.past_active(variant.strip(), row.get("accented", ""))
        if not row.get("presfut_sg1") and not row.get("presfut_sg3"):
            forms += ru_forms.present(row.get("accented", ""))
    forms += comparatives + [ru_forms.with_po(c) for c in comparatives]
    out: dict[str, list[int]] = {}
    for form in forms:
        if not FORM_RE.fullmatch(form):
            continue
        bare, positions, count = stress_positions(form)
        if not positions or (count < 2 and "ё" not in bare):
            continue
        listed = out.setdefault(bare, [])
        listed += [p for p in sorted(positions) if p not in listed]
    return out


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    marked = ranked(Path(sys.argv[1]))
    table = {form: [p for p, _ in entry] for form, entry in marked.items()}
    made = extra(Path(sys.argv[1]), table)
    derived_rows = {f: [(p, False) for p in ps] for f, ps in made.items()}
    for path, rows in ((OUT, marked), (DERIVED_OUT, derived_rows)):
        keys = sorted(rows, key=lambda k: k.encode())
        with open(path, "w", encoding="utf-8", newline="\n") as out:
            for key in keys:
                out.write(f"{key}\t{encode(rows[key])}\n")
        print(f"{len(keys)} forms -> {path}")
    yo = yo_only(all_forms(Path(sys.argv[1])))
    YO_OUT.write_text("".join(f + "\n" for f in yo), encoding="utf-8", newline="\n")
    print(f"{len(yo)} forms only with ё -> {YO_OUT}")


if __name__ == "__main__":
    main()
