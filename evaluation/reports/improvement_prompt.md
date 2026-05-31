# Consolidated improvement prompt for the `c4a8-odoo/.github` migration plugin

Across **10** migrated modules, the agent achieved a mean score of **88.33 / 100**.

Apply the following changes to the agent and skill so the next evaluation loop produces a higher score:

## Highest-impact agent instructions

- **`LEGACY_CR_CONTEXT_NOT_REPLACED`** (15 findings across 6 module(s)): Apply `self._cr` → `self.env.cr`, `self._context` → `self.env.context`, `self._uid` → `self.env.uid`, drop `@api.multi`/`@api.one`. These rules are `auto_apply: false` in the YAML — promote them, or stop escalating trivially-safe cases to manual review.
- **`MANIFEST_DEPENDS_DRIFT`** (2 findings across 2 module(s)): Re-evaluate `depends`, `data`, `license`, `external_dependencies` against the target branch instead of preserving the 18.0 manifest verbatim.
- **`OTHER`** (2 findings across 1 module(s)): Address `OTHER` findings — no advisory mapped.

## Suggested rubric-driven changes

- The `api_orm_updates` category averaged `0.54`. Tighten the corresponding skill rules in `skills/odoo-migrate-module/resources/migration-rules-18.0-19.0.yaml` and the agent gate in `agents/odoo-migration.agent.md`.
- The `manifest_correctness` category averaged `0.90`. Tighten the corresponding skill rules in `skills/odoo-migrate-module/resources/migration-rules-18.0-19.0.yaml` and the agent gate in `agents/odoo-migration.agent.md`.
- The `removed_deprecated` category averaged `0.90`. Tighten the corresponding skill rules in `skills/odoo-migrate-module/resources/migration-rules-18.0-19.0.yaml` and the agent gate in `agents/odoo-migration.agent.md`.

## How to validate the next iteration

1. Apply the changes above to `c4a8-odoo/.github`.
2. Re-run the agent on every module in `evaluation/modules.txt`, 
   writing each output to `/tmp/migrations/<module>/candidate_19.0/<module>/`.
3. Re-run `bash evaluation/harness/run_all.sh` and compare the new 
   `reports/summary.md` against this one. The plugin must regress on no 
   reason code and improve on at least the three weakest categories above.
