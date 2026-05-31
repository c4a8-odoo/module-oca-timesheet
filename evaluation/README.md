# `c4a8-odoo/.github` migration-plugin evaluation harness

This directory rates the performance of the
[`c4a8-odoo/.github`](https://github.com/c4a8-odoo/.github) Odoo migration
agent and `odoo-migrate-module` skill against the
[`module-oca-timesheet`](https://github.com/c4a8-odoo/module-oca-timesheet)
repository.

## Method

For every module that exists on **both** the `18.0` and `19.0` branches
of this repository:

1. **Migrate (Phase 2).** A migration agent is launched in an isolated
   workspace (`/tmp/migrations/<module>/`) that contains only the
   `18.0` copy of that module. The agent is instructed to migrate the
   module to `19.0` using the plugin's `odoo-migrate-module` skill and
   rule files. The agent's output is its `candidate_19.0/` directory.

2. **Validate (Phase 3).** The candidate directory is compared against
   the reference `19.0/<module>` from the same repository. A
   deterministic rubric scorer (`harness/score.py`) computes weighted
   sub-scores and produces a per-module JSON file under
   `runs/<module>/score.json`, plus a focused `improvement_prompt.md`
   listing what the agent should learn for the next run.

3. **Aggregate (Phase 4).** `harness/aggregate.py` rolls the
   per-module scores into `reports/summary.md` and a single consolidated
   `reports/improvement_prompt.md` for plugin authors.

## Layout

```
evaluation/
├── README.md                 # this file
├── rubric.md                 # weighted 0-100 rubric definition
├── schema.json               # JSON schema for per-module score files
├── modules.txt               # list of modules covered by this run
├── harness/
│   ├── score.py              # deterministic rubric scorer (single module)
│   ├── aggregate.py          # rollup + plugin-level improvement prompt
│   └── run_all.sh            # entry point that loops through modules.txt
├── runs/<module>/
│   ├── score.json            # per-module score (see schema.json)
│   ├── diff.patch            # candidate vs reference diff
│   └── improvement_prompt.md # focused feedback for the agent
└── reports/
    ├── summary.md            # aggregate scores + failure patterns
    └── improvement_prompt.md # consolidated plugin-level prompt
```

## Reproducing

```bash
# 1. populate /tmp/migrations/<module>/candidate_19.0/<module>/ with the
#    migration agent's output for each module in modules.txt
# 2. then:
bash evaluation/harness/run_all.sh
```

The harness is deterministic: the same candidate trees produce the same
scores, which lets us close the loop in Phase 5 (re-run after plugin
improvements and measure the score delta).
