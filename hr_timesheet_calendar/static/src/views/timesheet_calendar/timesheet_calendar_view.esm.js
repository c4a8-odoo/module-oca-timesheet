import {TimesheetCalendarController} from "@hr_timesheet_calendar/views/timesheet_calendar/timesheet_calendar_controller.esm";
import {TimesheetCalendarRenderer} from "@hr_timesheet_calendar/views/timesheet_calendar/timesheet_calendar_renderer.esm";
import {timesheetCalendarView as baseTimesheetCalendarView} from "@hr_timesheet/views/timesheet_calendar/timesheet_calendar_view";
import {registry} from "@web/core/registry";

export const timesheetCalendarView = {
    ...baseTimesheetCalendarView,
    Controller: TimesheetCalendarController,
    Renderer: TimesheetCalendarRenderer,
};
// Use {force: true} because @hr_timesheet already registers "timesheet_calendar"
// with its own view. This module extends that view with OCA's Controller and
// Renderer (adding the "copy to today" action), so we intentionally override it.
registry
    .category("views")
    .add("timesheet_calendar", timesheetCalendarView, {force: true});
