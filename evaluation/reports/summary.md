# Migration plugin evaluation — summary

Modules evaluated: **10**
Overall mean score: **88.33 / 100**

## Score per module

| Module | Score | Band |
| --- | ---: | --- |
| `crm_timesheet` | 100.00 | Excellent |
| `hr_timesheet_autofill_project_off` | 100.00 | Excellent |
| `hr_timesheet_day_week` | 100.00 | Excellent |
| `sale_timesheet_invoice_link` | 100.00 | Excellent |
| `hr_timesheet_task_required` | 95.00 | Excellent |
| `hr_timesheet_begin_end` | 86.67 | Good |
| `hr_timesheet_task_stage` | 86.67 | Good |
| `sale_timesheet_line_exclude` | 80.00 | Good |
| `hr_timesheet_time_control_begin_end` | 72.50 | Acceptable |
| `project_timesheet_holidays_dynamic_description` | 62.50 | Acceptable |

## Band distribution

| Band | Modules |
| --- | ---: |
| Excellent | 5 |
| Good | 3 |
| Acceptable | 2 |
| Poor | 0 |
| Failed | 0 |

## Mean sub-scores

| Category | Mean score | Weight |
| --- | ---: | ---: |
| `manifest_correctness` | 0.90 | 0.15 |
| `api_orm_updates` | 0.54 | 0.2 |
| `view_xml_migration` | 1.00 | 0.15 |
| `removed_deprecated` | 0.90 | 0.1 |
| `tests_discoverable` | 1.00 | 0.15 |
| `code_style` | 1.00 | 0.1 |
| `no_spurious_diffs` | 1.00 | 0.15 |

## Top failure patterns

| Reason code | Findings | Affected modules |
| --- | ---: | --- |
| `LEGACY_CR_CONTEXT_NOT_REPLACED` | 15 | `hr_timesheet_begin_end`, `hr_timesheet_task_required`, `hr_timesheet_task_stage`, `hr_timesheet_time_control_begin_end`, `project_timesheet_holidays_dynamic_description`, `sale_timesheet_line_exclude` |
| `MANIFEST_DEPENDS_DRIFT` | 2 | `hr_timesheet_time_control_begin_end`, `project_timesheet_holidays_dynamic_description` |
| `OTHER` | 2 | `project_timesheet_holidays_dynamic_description` |
