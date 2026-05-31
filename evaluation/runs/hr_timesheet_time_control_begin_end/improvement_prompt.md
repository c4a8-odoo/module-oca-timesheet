# Improvement prompt for `hr_timesheet_time_control_begin_end`

When you re-run the migration agent on this module, focus on the
following gaps the previous run left:

## Weakest rubric categories

- **api_orm_updates** (score `0.00`, weight `0.2`, 0/3 required changes applied)
- **manifest_correctness** (score `0.50`, weight `0.15`, 1/2 required changes applied)
- **view_xml_migration** (score `1.00`, weight `0.15`, 0/0 required changes applied)

## Top failure patterns (reason codes)

- `LEGACY_CR_CONTEXT_NOT_REPLACED` × 3
- `MANIFEST_DEPENDS_DRIFT` × 1

## Concrete instructions for the next run

- Apply `self._cr` → `self.env.cr`, `self._context` → `self.env.context`, drop `@api.multi`/`@api.one`. The rule is marked `auto_apply: false` in the YAML — promote it to auto-apply for safe cases or stop bailing out.
- Re-evaluate `depends`/`data`/`license`/`external_dependencies` against the target branch; do not blindly preserve the 18.0 manifest.
