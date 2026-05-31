#!/usr/bin/env python3
"""Deterministic rubric scorer for the c4a8-odoo migration plugin.

Compares a candidate migrated module (produced by the agent under
evaluation) against the human-authored reference module on the 19.0
branch. Writes ``score.json``, ``diff.patch`` and
``improvement_prompt.md`` to ``runs/<module>/``.

Usage::

    python evaluation/harness/score.py <module> \
        --source /tmp/migrations/<module>/source_18.0/<module> \
        --candidate /tmp/migrations/<module>/candidate_19.0/<module> \
        --reference /tmp/migrations/<module>/reference_19.0/<module> \
        --out evaluation/runs/<module>

The scorer is intentionally simple and side-effect free so the harness
can be replayed deterministically across plugin versions.
"""

from __future__ import annotations

import argparse
import ast
import datetime as _dt
import difflib
import json
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

# ---------------------------------------------------------------------------
# Rubric weights (must match evaluation/rubric.md).
# ---------------------------------------------------------------------------
WEIGHTS = {
    "manifest_correctness": 0.15,
    "api_orm_updates": 0.20,
    "view_xml_migration": 0.15,
    "removed_deprecated": 0.10,
    "tests_discoverable": 0.15,
    "code_style": 0.10,
    "no_spurious_diffs": 0.15,
}

BAND_THRESHOLDS = [
    (90, "Excellent"),
    (75, "Good"),
    (50, "Acceptable"),
    (25, "Poor"),
    (0, "Failed"),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@dataclass
class Finding:
    category: str
    reason_code: str
    detail: str
    file: str | None = None

    def to_dict(self) -> dict:
        out = {
            "category": self.category,
            "reason_code": self.reason_code,
            "detail": self.detail,
        }
        if self.file:
            out["file"] = self.file
        return out


@dataclass
class SubScore:
    weight: float
    expected: int = 0
    achieved: int = 0
    notes: str = ""

    @property
    def score(self) -> float:
        if self.expected == 0:
            # No required changes in this category for this module → full
            # credit (the agent had nothing to do).
            return 1.0
        return max(0.0, min(1.0, self.achieved / self.expected))

    def to_dict(self) -> dict:
        return {
            "score": round(self.score, 4),
            "weight": self.weight,
            "expected": self.expected,
            "achieved": self.achieved,
            "notes": self.notes,
        }


def list_files(root: Path) -> set[str]:
    if not root.exists():
        return set()
    out = set()
    for p in root.rglob("*"):
        if p.is_file():
            out.add(str(p.relative_to(root)))
    return out


def read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, FileNotFoundError):
        return ""


def parse_manifest(text: str) -> dict:
    """Parse an Odoo ``__manifest__.py`` (a single dict literal)."""
    try:
        tree = ast.parse(text, mode="exec")
        for node in tree.body:
            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Dict):
                return ast.literal_eval(node.value)
    except Exception:
        pass
    return {}


def band_for(score: float) -> str:
    for threshold, name in BAND_THRESHOLDS:
        if score >= threshold:
            return name
    return "Failed"


# ---------------------------------------------------------------------------
# Per-category scoring
# ---------------------------------------------------------------------------

def score_manifest(src: Path, cand: Path, ref: Path, findings: list[Finding]) -> SubScore:
    sub = SubScore(weight=WEIGHTS["manifest_correctness"])

    src_m = parse_manifest(read(src / "__manifest__.py"))
    cand_m = parse_manifest(read(cand / "__manifest__.py"))
    ref_m = parse_manifest(read(ref / "__manifest__.py"))

    checks: list[tuple[str, bool, str, str]] = []

    # 1. version bumped to 19.0.*
    if "version" in ref_m and ref_m.get("version") != src_m.get("version"):
        ok = str(cand_m.get("version", "")).startswith("19.0")
        checks.append(("version_bump", ok, "MANIFEST_VERSION_NOT_BUMPED",
                       f"version should start with 19.0 (got {cand_m.get('version')!r}, "
                       f"reference={ref_m.get('version')!r})"))

    # 2. depends list aligned with reference
    if set(ref_m.get("depends", [])) != set(src_m.get("depends", [])):
        ok = set(cand_m.get("depends", [])) == set(ref_m.get("depends", []))
        checks.append(("depends", ok, "MANIFEST_DEPENDS_DRIFT",
                       f"depends mismatch: candidate={sorted(cand_m.get('depends', []))} "
                       f"reference={sorted(ref_m.get('depends', []))}"))

    # 3. data list aligned with reference (order-insensitive)
    if set(ref_m.get("data", [])) != set(src_m.get("data", [])):
        ok = set(cand_m.get("data", [])) == set(ref_m.get("data", []))
        checks.append(("data", ok, "MANIFEST_DEPENDS_DRIFT",
                       "manifest 'data' list differs from reference"))

    # 4. license / installable / external_dependencies preserved
    for key in ("license", "installable", "external_dependencies"):
        if key in ref_m and ref_m.get(key) != src_m.get(key):
            ok = cand_m.get(key) == ref_m.get(key)
            checks.append((key, ok, "MANIFEST_DEPENDS_DRIFT",
                           f"manifest {key!r} differs from reference"))

    for name, ok, code, detail in checks:
        sub.expected += 1
        if ok:
            sub.achieved += 1
        else:
            findings.append(Finding("manifest_correctness", code, detail, "__manifest__.py"))

    if sub.expected == 0:
        sub.notes = "Manifest already aligned in source; no required changes."
    return sub


_PY_RENAMES = [
    ("self._cr", "self.env.cr", "LEGACY_CR_CONTEXT_NOT_REPLACED"),
    ("self._context", "self.env.context", "LEGACY_CR_CONTEXT_NOT_REPLACED"),
    ("self._uid", "self.env.uid", "LEGACY_CR_CONTEXT_NOT_REPLACED"),
    ("@api.multi", "", "LEGACY_CR_CONTEXT_NOT_REPLACED"),
    ("@api.one", "", "LEGACY_CR_CONTEXT_NOT_REPLACED"),
]


def score_api_updates(src: Path, cand: Path, ref: Path, findings: list[Finding]) -> SubScore:
    sub = SubScore(weight=WEIGHTS["api_orm_updates"])

    py_files = sorted({p for p in list_files(src) if p.endswith(".py")} |
                      {p for p in list_files(ref) if p.endswith(".py")})

    for rel in py_files:
        s = read(src / rel)
        r = read(ref / rel)
        c = read(cand / rel)
        # For every well-known rename rule, if the source contained the old
        # token AND the reference no longer does, the agent was required to
        # remove it.
        for old, _new, code in _PY_RENAMES:
            if old and old in s and old not in r:
                sub.expected += 1
                if old not in c:
                    sub.achieved += 1
                else:
                    findings.append(Finding(
                        "api_orm_updates", code,
                        f"legacy token {old!r} still present in candidate",
                        rel,
                    ))

        # Line-level required changes: any source line absent from the
        # reference but still present in the candidate is a missed edit.
        s_lines = set(s.splitlines())
        r_lines = set(r.splitlines())
        c_lines = set(c.splitlines())
        removed = s_lines - r_lines
        # Only count *non-trivial* removals to keep the signal high.
        removed = {ln for ln in removed
                   if ln.strip() and not ln.strip().startswith(("#", '"""', "'''"))}
        if not removed:
            continue
        # Required removals overall
        sub.expected += 1
        if removed.isdisjoint(c_lines):
            sub.achieved += 1
        else:
            still = sorted(removed & c_lines)[:3]
            findings.append(Finding(
                "api_orm_updates", "LEGACY_CR_CONTEXT_NOT_REPLACED",
                f"{len(removed & c_lines)} reference-removed line(s) still in candidate, "
                f"e.g. {still!r}",
                rel,
            ))

    if sub.expected == 0:
        sub.notes = "No Python-level required changes detected in reference."
    return sub


def score_view_xml(src: Path, cand: Path, ref: Path, findings: list[Finding]) -> SubScore:
    sub = SubScore(weight=WEIGHTS["view_xml_migration"])

    xml_files = sorted({p for p in list_files(src) if p.endswith(".xml")} |
                       {p for p in list_files(ref) if p.endswith(".xml")})

    rules = [
        (re.compile(r'\battrs\s*=\s*"'), "ATTRS_STATES_NOT_REMOVED",
         "attrs= attribute should be removed in 19.0"),
        (re.compile(r'\bstates\s*=\s*"'), "ATTRS_STATES_NOT_REMOVED",
         "states= attribute should be removed in 19.0"),
        (re.compile(r'type="json"'), "JSONRPC_RENAME_MISSED",
         'type="json" should become type="jsonrpc"'),
        (re.compile(r"<tree\b"), "LIST_VIEW_RENAME_MISSED",
         "<tree> element should be renamed to <list>"),
        (re.compile(r'view_mode="[^"]*\btree\b'), "LIST_VIEW_RENAME_MISSED",
         'view_mode containing "tree" should use "list"'),
    ]

    for rel in xml_files:
        s = read(src / rel)
        r = read(ref / rel)
        c = read(cand / rel)
        for pat, code, msg in rules:
            in_src = bool(pat.search(s))
            in_ref = bool(pat.search(r))
            if in_src and not in_ref:
                sub.expected += 1
                if not pat.search(c):
                    sub.achieved += 1
                else:
                    findings.append(Finding("view_xml_migration", code, msg, rel))

    if sub.expected == 0:
        sub.notes = "No XML migration patterns triggered for this module."
    return sub


def score_removed_deprecated(src: Path, cand: Path, ref: Path, findings: list[Finding]) -> SubScore:
    sub = SubScore(weight=WEIGHTS["removed_deprecated"])
    src_files = list_files(src)
    ref_files = list_files(ref)
    cand_files = list_files(cand)

    # Files the reference deleted relative to source.
    deleted = src_files - ref_files
    if deleted:
        sub.expected += len(deleted)
        for rel in sorted(deleted):
            if rel not in cand_files:
                sub.achieved += 1
            else:
                code = ("LEGACY_MIGRATIONS_DIR_KEPT"
                        if rel.startswith("migrations/") else "OTHER")
                findings.append(Finding(
                    "removed_deprecated", code,
                    f"file should have been deleted in 19.0",
                    rel,
                ))
    else:
        sub.notes = "Reference did not delete any source files."
    return sub


def score_tests_discoverable(cand: Path, ref: Path, findings: list[Finding]) -> SubScore:
    sub = SubScore(weight=WEIGHTS["tests_discoverable"])

    # 1. Every .py parses.
    py_files = [p for p in cand.rglob("*.py") if p.is_file()]
    sub.expected += 1
    py_ok = True
    for p in py_files:
        try:
            ast.parse(p.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError) as e:
            py_ok = False
            findings.append(Finding(
                "tests_discoverable", "PY_NOT_PARSEABLE",
                f"failed to parse: {e}", str(p.relative_to(cand)),
            ))
    if py_ok:
        sub.achieved += 1

    # 2. Every .xml is well-formed.
    xml_files = [p for p in cand.rglob("*.xml") if p.is_file()]
    sub.expected += 1
    xml_ok = True
    for p in xml_files:
        try:
            ET.parse(p)
        except ET.ParseError as e:
            xml_ok = False
            findings.append(Finding(
                "tests_discoverable", "XML_NOT_WELLFORMED",
                f"malformed XML: {e}", str(p.relative_to(cand)),
            ))
    if xml_ok:
        sub.achieved += 1

    # 3. tests/__init__.py exposes the same modules as the reference.
    ref_tests = ref / "tests" / "__init__.py"
    cand_tests = cand / "tests" / "__init__.py"
    if ref_tests.exists():
        sub.expected += 1
        ref_imports = set(re.findall(r"from \. import (\w+)", read(ref_tests)))
        cand_imports = set(re.findall(r"from \. import (\w+)", read(cand_tests)))
        if ref_imports.issubset(cand_imports):
            sub.achieved += 1
        else:
            findings.append(Finding(
                "tests_discoverable", "TEST_MODULE_DROPPED",
                f"missing test imports: {sorted(ref_imports - cand_imports)}",
                "tests/__init__.py",
            ))

    return sub


def score_code_style(src: Path, cand: Path, ref: Path, findings: list[Finding]) -> SubScore:
    sub = SubScore(weight=WEIGHTS["code_style"])

    def pyflakes_count(root: Path) -> int:
        out = subprocess.run(
            [sys.executable, "-m", "pyflakes", str(root)],
            capture_output=True, text=True,
        )
        # one finding per line
        return sum(1 for ln in out.stdout.splitlines() if ln.strip())

    try:
        src_n = pyflakes_count(src)
        cand_n = pyflakes_count(cand)
        ref_n = pyflakes_count(ref)
    except FileNotFoundError:
        sub.notes = "pyflakes unavailable; skipped."
        return sub

    # Bar = max(source, reference). The reference itself sometimes adds
    # benign findings (e.g. unused imports retained for backwards
    # compatibility) — a perfect-mimic agent must not be penalised for them.
    bar = max(src_n, ref_n)
    sub.expected = 1
    if cand_n <= bar:
        sub.achieved = 1
        sub.notes = f"pyflakes: src={src_n}, ref={ref_n}, candidate={cand_n} (≤ bar {bar})"
    else:
        findings.append(Finding(
            "code_style", "IMPORT_DRIFT",
            f"pyflakes regressed: src={src_n}, ref={ref_n} → candidate={cand_n}",
        ))
        sub.notes = f"pyflakes: src={src_n}, ref={ref_n}, candidate={cand_n} (regression)"
    return sub


def score_no_spurious(src: Path, cand: Path, ref: Path, findings: list[Finding]) -> SubScore:
    sub = SubScore(weight=WEIGHTS["no_spurious_diffs"])
    src_files = list_files(src)
    ref_files = list_files(ref)
    cand_files = list_files(cand)

    # Files unchanged between source and reference: should be unchanged in
    # the candidate too.
    untouched = []
    for rel in sorted(src_files & ref_files):
        if read(src / rel) == read(ref / rel):
            untouched.append(rel)

    if not untouched:
        sub.notes = "No untouched files to compare; trivially clean."
        return sub

    sub.expected = len(untouched)
    for rel in untouched:
        if rel in cand_files and read(cand / rel) == read(src / rel):
            sub.achieved += 1
        else:
            findings.append(Finding(
                "no_spurious_diffs", "SPURIOUS_FILE_MODIFIED",
                "file was identical in 18.0 and reference 19.0 but candidate changed it",
                rel,
            ))
    return sub


# ---------------------------------------------------------------------------
# Improvement prompt synthesis
# ---------------------------------------------------------------------------

def build_improvement_prompt(module: str, sub_scores: dict[str, SubScore],
                             findings: list[Finding]) -> str:
    counts: dict[str, int] = {}
    for f in findings:
        counts[f.reason_code] = counts.get(f.reason_code, 0) + 1
    top = sorted(counts.items(), key=lambda kv: -kv[1])

    weakest = sorted(
        sub_scores.items(),
        key=lambda kv: (kv[1].score, -kv[1].weight),
    )[:3]

    lines = [
        f"# Improvement prompt for `{module}`",
        "",
        "When you re-run the migration agent on this module, focus on the",
        "following gaps the previous run left:",
        "",
        "## Weakest rubric categories",
        "",
    ]
    for name, s in weakest:
        if s.score >= 0.99 and s.expected > 0:
            continue
        lines.append(
            f"- **{name}** (score `{s.score:.2f}`, weight `{s.weight}`, "
            f"{s.achieved}/{s.expected} required changes applied)"
        )
    if not any(s.score < 0.99 or s.expected == 0 for _, s in weakest):
        lines.append("- _(no weak category — module migrated cleanly)_")

    lines += ["", "## Top failure patterns (reason codes)", ""]
    if not top:
        lines.append("- _(no findings — nothing to learn from this run)_")
    for code, n in top[:10]:
        lines.append(f"- `{code}` × {n}")

    lines += ["", "## Concrete instructions for the next run", ""]
    # Map reason codes to concrete agent instructions.
    advisory = {
        "MANIFEST_VERSION_NOT_BUMPED":
            "Always bump `__manifest__.py` `version` to the `19.0.x.y.z` baseline "
            "(rule `manifest.version.bump` in `migration-rules-18.0-19.0.yaml`).",
        "MANIFEST_DEPENDS_DRIFT":
            "Re-evaluate `depends`/`data`/`license`/`external_dependencies` against "
            "the target branch; do not blindly preserve the 18.0 manifest.",
        "LEGACY_CR_CONTEXT_NOT_REPLACED":
            "Apply `self._cr` → `self.env.cr`, `self._context` → `self.env.context`, "
            "drop `@api.multi`/`@api.one`. The rule is marked `auto_apply: false` in "
            "the YAML — promote it to auto-apply for safe cases or stop bailing out.",
        "JSONRPC_RENAME_MISSED":
            "Apply rule `xml.request.type.jsonrpc`: replace `type=\"json\"` with "
            "`type=\"jsonrpc\"` in every `.py` and `.xml`.",
        "ATTRS_STATES_NOT_REMOVED":
            "Strip `attrs=` and `states=` from XML views and translate the condition "
            "into the new view syntax (rule family `xml.view.attrs_removal`).",
        "LIST_VIEW_RENAME_MISSED":
            "Rename `<tree>` to `<list>` and update `view_mode` strings to `list`.",
        "LEGACY_MIGRATIONS_DIR_KEPT":
            "Delete the legacy `migrations/` directory copied from the source branch "
            "(rule `cleanup.legacy.migrations`).",
        "DOMAIN_API_NOT_UPDATED":
            "Domain rewrites are flagged for manual review — surface a clearer signal "
            "when the agent encounters them rather than leaving 18.0 syntax.",
        "SPURIOUS_FILE_MODIFIED":
            "Do not touch files that are byte-identical between 18.0 and the target "
            "(README boilerplate, translations, copyright headers).",
        "REGRESSION_REVERTED_18_0_FIX":
            "Never revert changes that were already correct in 18.0.",
        "XML_NOT_WELLFORMED":
            "Run an XML well-formedness check before committing — the candidate left "
            "malformed XML.",
        "PY_NOT_PARSEABLE":
            "Run `python -m compileall` on the module before committing — the "
            "candidate left unparseable Python.",
        "IMPORT_DRIFT":
            "Run a `pyflakes` pass and clean up unused imports introduced by the "
            "migration before finishing.",
        "TEST_MODULE_DROPPED":
            "Keep `tests/__init__.py` in sync with the reference — do not drop test "
            "modules during migration.",
    }
    seen = set()
    for code, _ in top:
        if code in advisory and code not in seen:
            lines.append(f"- {advisory[code]}")
            seen.add(code)
    if not seen:
        lines.append("- _(no actionable advice — nothing to change)_")

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("module")
    ap.add_argument("--source", required=True, type=Path)
    ap.add_argument("--candidate", required=True, type=Path)
    ap.add_argument("--reference", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)

    findings: list[Finding] = []
    sub_scores: dict[str, SubScore] = {
        "manifest_correctness": score_manifest(args.source, args.candidate,
                                               args.reference, findings),
        "api_orm_updates": score_api_updates(args.source, args.candidate,
                                             args.reference, findings),
        "view_xml_migration": score_view_xml(args.source, args.candidate,
                                             args.reference, findings),
        "removed_deprecated": score_removed_deprecated(args.source, args.candidate,
                                                       args.reference, findings),
        "tests_discoverable": score_tests_discoverable(args.candidate,
                                                       args.reference, findings),
        "code_style": score_code_style(args.source, args.candidate,
                                       args.reference, findings),
        "no_spurious_diffs": score_no_spurious(args.source, args.candidate,
                                               args.reference, findings),
    }

    final = round(100 * sum(s.score * s.weight for s in sub_scores.values()), 2)
    band = band_for(final)

    # Diff
    diff = subprocess.run(
        ["diff", "-ruN", str(args.reference), str(args.candidate)],
        capture_output=True, text=True,
    ).stdout
    (args.out / "diff.patch").write_text(diff)

    ref_files = list_files(args.reference)
    cand_files = list_files(args.candidate)
    files_changed = sorted(
        rel for rel in ref_files & cand_files
        if read(args.reference / rel) != read(args.candidate / rel)
    )

    missing = [f.to_dict() for f in findings if f.category != "no_spurious_diffs"]
    extra = [f.to_dict() for f in findings if f.category == "no_spurious_diffs"]

    prompt = build_improvement_prompt(args.module, sub_scores, findings)
    (args.out / "improvement_prompt.md").write_text(prompt)

    result = {
        "module": args.module,
        "source_version": "18.0",
        "target_version": "19.0",
        "scored_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "score": final,
        "band": band,
        "sub_scores": {k: v.to_dict() for k, v in sub_scores.items()},
        "agent_diff_vs_reference": {
            "files_changed": files_changed,
            "files_only_in_candidate": sorted(cand_files - ref_files),
            "files_only_in_reference": sorted(ref_files - cand_files),
            "diff_path": "diff.patch",
        },
        "missing_changes": missing,
        "extra_changes": extra,
        "improvement_prompt": prompt,
    }
    (args.out / "score.json").write_text(json.dumps(result, indent=2) + "\n")
    print(f"{args.module}: {final} ({band})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
