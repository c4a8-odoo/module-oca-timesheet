# Scoring rubric (0–100)

Each migrated module is scored against the reference `19.0/<module>`
on seven weighted categories. All sub-scores are normalized to `[0, 1]`
and combined as a weighted mean, then multiplied by 100.

| #   | Category                     | Weight | What it measures                                                                                                              |
| --- | ---------------------------- | ------ | ----------------------------------------------------------------------------------------------------------------------------- |
| 1   | **Manifest correctness**     | 0.15   | `__manifest__.py` version updated to `19.0.x.y.z`; `depends`, `data`, `installable`, license and `external_dependencies` align with the reference. |
| 2   | **API / ORM call updates**   | 0.20   | Python-level changes (e.g. `self._cr` → `self.env.cr`, `self._context` → `self.env.context`, removed legacy decorators, new `Domain` API, removed `@api.multi`, etc.) match the reference. |
| 3   | **View XML migration**       | 0.15   | XML view updates: `attrs=`/`states=` removed, `type="json"` → `type="jsonrpc"`, tree→list rename, button/menu attrs, removed deprecated elements. |
| 4   | **Removed deprecated bits**  | 0.10   | Legacy `migrations/` directory removed, deprecated assets dropped, removed unused imports/fields that the reference also dropped. |
| 5   | **Tests still discoverable** | 0.15   | Module imports cleanly with `python -c 'import ast; ast.parse(...)'`, every `.py` parses, every `.xml` parses, `tests/__init__.py` still exposes the same test modules as the reference. |
| 6   | **Code style / linters**     | 0.10   | No new flake8/pylint-odoo blocking findings introduced relative to the 18.0 baseline (checked with `pyflakes` + XML well-formedness, which are the linters available in this sandbox). |
| 7   | **No spurious diffs**        | 0.15   | Files that are byte-identical in `18.0` and `19.0` reference must remain byte-identical in candidate. Copyright years, author lines, README boilerplate and translations must not drift. |

## Scoring procedure (per category)

For each category the scorer derives a `(achieved, expected)` pair:

* `expected` = number of distinct *required changes* identified by
  comparing `18.0/<module>` to `reference 19.0/<module>` within that
  category.
* `achieved` = number of those required changes that are also present
  in `candidate 19.0/<module>`.

Sub-score:

```
sub_score = achieved / max(expected, 1)   # in [0, 1]
```

Penalties:

* **Missing required change** → counts as `0` in `achieved`.
* **Regression** (the candidate undoes something the reference keeps
  from 18.0) → subtracts `1` from `achieved` (floored at `0`) in the
  affected category.
* **Spurious change** (the candidate modifies a file that the reference
  does not) → counts against category 7 only.

## Final score

```
final = 100 * Σ(weight_i * sub_score_i)
```

Bands:

| Score   | Band                                                                |
| ------- | ------------------------------------------------------------------- |
| 90–100  | **Excellent** – ready to merge with light review.                   |
| 75–89   | **Good** – minor follow-ups expected, but migration is essentially correct. |
| 50–74   | **Acceptable** – meaningful gaps, agent shipped a partial migration.|
| 25–49   | **Poor** – major rules missed; manual rework dominates.             |
| 0–24    | **Failed** – candidate is not usable.                               |

## Failure-pattern taxonomy

Each missing change is tagged with one of these reason codes so that
the aggregate report can identify systemic weaknesses in the plugin:

* `MANIFEST_VERSION_NOT_BUMPED`
* `MANIFEST_DEPENDS_DRIFT`
* `LEGACY_CR_CONTEXT_NOT_REPLACED`
* `JSONRPC_RENAME_MISSED`
* `ATTRS_STATES_NOT_REMOVED`
* `LIST_VIEW_RENAME_MISSED`
* `LEGACY_MIGRATIONS_DIR_KEPT`
* `DOMAIN_API_NOT_UPDATED`
* `SPURIOUS_FILE_MODIFIED`
* `REGRESSION_REVERTED_18_0_FIX`
* `XML_NOT_WELLFORMED`
* `PY_NOT_PARSEABLE`
* `IMPORT_DRIFT`
* `TEST_MODULE_DROPPED`
* `OTHER`
