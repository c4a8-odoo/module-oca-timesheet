This module enhances the timesheet experience by adding a **calendar view** to
timesheet entries, allowing employees to visualize and manage their work hours
in a familiar calendar interface.

Key features:

- **Calendar view**: A new calendar view is added to the Timesheets menu,
  displaying entries by their start and end times and color-coded by project.
- **Smart default start time**: When creating a new timesheet entry, the start
  time is automatically determined based on a configurable alignment policy:
  - *Set Start Date to Now*: Default start time is the current time.
  - *Align to previous entry*: Start time is set to the end time of the
    previous entry on the same day. For the first entry of the day, the
    start time is taken from the employee's work schedule (resource calendar).
- **Automatic duration calculation**: The duration (unit amount) is
  automatically computed from the start and end times whenever both are set.
- **Duplicate to today**: Timesheet entries can be duplicated to the current
  day while preserving the original start and end times.

This module depends on the `project_timesheet_time_control` module from the
OCA/project repository to use the `date_time_end` field.
