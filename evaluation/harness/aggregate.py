#!/usr/bin/env python3
"""Aggregate per-module scores into a summary report and a consolidated
plugin-level improvement prompt."""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "runs"
REPORTS = ROOT / "reports"


def load_runs() -> list[dict]:
    out = []
    for p in sorted(RUNS.glob("*/score.json")):
        out.append(json.loads(p.read_text()))
    return out


def main() -> int:
    REPORTS.mkdir(parents=True, exist_ok=True)
    runs = load_runs()
    if not runs:
        print("no runs to aggregate", file=sys.stderr)
        return 1

    n = len(runs)
    mean_total = sum(r["score"] for r in runs) / n

    # Per-category means.
    cat_keys = list(runs[0]["sub_scores"].keys())
    cat_means = {
        k: sum(r["sub_scores"][k]["score"] for r in runs) / n for k in cat_keys
    }
    band_counts = Counter(r["band"] for r in runs)

    # Failure-pattern aggregate.
    reason_counts: Counter = Counter()
    reason_modules: dict[str, set[str]] = defaultdict(set)
    for r in runs:
        for f in r["missing_changes"] + r["extra_changes"]:
            reason_counts[f["reason_code"]] += 1
            reason_modules[f["reason_code"]].add(r["module"])

    # ------------------------------------------------------------------ summary
    lines = [
        "# Migration plugin evaluation — summary",
        "",
        f"Modules evaluated: **{n}**",
        f"Overall mean score: **{mean_total:.2f} / 100**",
        "",
        "## Score per module",
        "",
        "| Module | Score | Band |",
        "| --- | ---: | --- |",
    ]
    for r in sorted(runs, key=lambda x: -x["score"]):
        lines.append(f"| `{r['module']}` | {r['score']:.2f} | {r['band']} |")

    lines += [
        "",
        "## Band distribution",
        "",
        "| Band | Modules |",
        "| --- | ---: |",
    ]
    for b in ["Excellent", "Good", "Acceptable", "Poor", "Failed"]:
        lines.append(f"| {b} | {band_counts.get(b, 0)} |")

    lines += [
        "",
        "## Mean sub-scores",
        "",
        "| Category | Mean score | Weight |",
        "| --- | ---: | ---: |",
    ]
    for k in cat_keys:
        w = runs[0]["sub_scores"][k]["weight"]
        lines.append(f"| `{k}` | {cat_means[k]:.2f} | {w} |")

    lines += [
        "",
        "## Top failure patterns",
        "",
        "| Reason code | Findings | Affected modules |",
        "| --- | ---: | --- |",
    ]
    for code, count in reason_counts.most_common(20):
        mods = ", ".join(f"`{m}`" for m in sorted(reason_modules[code]))
        lines.append(f"| `{code}` | {count} | {mods} |")

    (REPORTS / "summary.md").write_text("\n".join(lines) + "\n")

    # -------------------------------------------------- consolidated prompt
    advisory = {
        "MANIFEST_VERSION_NOT_BUMPED":
            "Always bump `__manifest__.py` `version` to `19.0.x.y.z` "
            "(rule `manifest.version.bump`). The current agent leaves 18.0 versions.",
        "MANIFEST_DEPENDS_DRIFT":
            "Re-evaluate `depends`, `data`, `license`, `external_dependencies` "
            "against the target branch instead of preserving the 18.0 manifest verbatim.",
        "LEGACY_CR_CONTEXT_NOT_REPLACED":
            "Apply `self._cr` → `self.env.cr`, `self._context` → `self.env.context`, "
            "`self._uid` → `self.env.uid`, drop `@api.multi`/`@api.one`. These rules "
            "are `auto_apply: false` in the YAML — promote them, or stop escalating "
            "trivially-safe cases to manual review.",
        "JSONRPC_RENAME_MISSED":
            "Always apply `xml.request.type.jsonrpc`: `type=\"json\"` → `type=\"jsonrpc\"` "
            "in both `.py` and `.xml`.",
        "ATTRS_STATES_NOT_REMOVED":
            "Strip `attrs=` and `states=` from views; translate the condition into the "
            "Odoo 17+ view syntax with `invisible=`, `readonly=`, `required=` directly.",
        "LIST_VIEW_RENAME_MISSED":
            "Rename `<tree>` to `<list>` and update `view_mode` strings from `tree` "
            "to `list`. The current agent forgets the `view_mode` half.",
        "LEGACY_MIGRATIONS_DIR_KEPT":
            "Always run rule `cleanup.legacy.migrations` — delete the `migrations/` "
            "directory copied from the source branch.",
        "DOMAIN_API_NOT_UPDATED":
            "Domain rewrites are flagged for manual review. Provide a sharper "
            "heuristic so the agent at least attempts the trivial cases.",
        "SPURIOUS_FILE_MODIFIED":
            "Never touch files that are byte-identical between source and target "
            "(README boilerplate, translations, copyright headers, static assets).",
        "REGRESSION_REVERTED_18_0_FIX":
            "Do not undo edits that were correct in 18.0; the agent must diff *forward* "
            "from source, not reset to a pristine 18.0 template.",
        "XML_NOT_WELLFORMED":
            "Add an XML well-formedness pre-commit check; the agent currently ships "
            "malformed XML in some modules.",
        "PY_NOT_PARSEABLE":
            "Add a `python -m compileall` pre-commit check; the agent ships "
            "unparseable Python in some modules.",
        "IMPORT_DRIFT":
            "Run `pyflakes`/`ruff` on changed files and remove imports left "
            "unused by the migration.",
        "TEST_MODULE_DROPPED":
            "Keep `tests/__init__.py` aligned with the reference — do not drop "
            "test modules during migration.",
    }

    out = [
        "# Consolidated improvement prompt for the `c4a8-odoo/.github` migration plugin",
        "",
        f"Across **{n}** migrated modules, the agent achieved a mean score of "
        f"**{mean_total:.2f} / 100**.",
        "",
        "Apply the following changes to the agent and skill so the next evaluation "
        "loop produces a higher score:",
        "",
        "## Highest-impact agent instructions",
        "",
    ]
    if not reason_counts:
        out.append("_No findings — the plugin already meets the rubric._")
    for code, count in reason_counts.most_common():
        msg = advisory.get(code, f"Address `{code}` findings — no advisory mapped.")
        out.append(f"- **`{code}`** ({count} findings across "
                   f"{len(reason_modules[code])} module(s)): {msg}")

    out += [
        "",
        "## Suggested rubric-driven changes",
        "",
    ]
    weakest_cats = sorted(cat_means.items(), key=lambda kv: kv[1])[:3]
    for cat, mean in weakest_cats:
        out.append(f"- The `{cat}` category averaged `{mean:.2f}`. "
                   f"Tighten the corresponding skill rules in "
                   f"`skills/odoo-migrate-module/resources/migration-rules-18.0-19.0.yaml` "
                   f"and the agent gate in `agents/odoo-migration.agent.md`.")

    out += [
        "",
        "## How to validate the next iteration",
        "",
        "1. Apply the changes above to `c4a8-odoo/.github`.",
        "2. Re-run the agent on every module in `evaluation/modules.txt`, ",
        "   writing each output to `/tmp/migrations/<module>/candidate_19.0/<module>/`.",
        "3. Re-run `bash evaluation/harness/run_all.sh` and compare the new ",
        "   `reports/summary.md` against this one. The plugin must regress on no ",
        "   reason code and improve on at least the three weakest categories above.",
    ]
    (REPORTS / "improvement_prompt.md").write_text("\n".join(out) + "\n")

    print(f"wrote {REPORTS/'summary.md'} and {REPORTS/'improvement_prompt.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
