# Copyright 2025 Odoo Community Association (OCA)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Rename ir.config_parameter key from project_timesheet_time_control
    to hr_timesheet_time_control for timesheet_alignment setting."""
    old_key = "project_timesheet_time_control.timesheet_alignment"
    new_key = "hr_timesheet_time_control.timesheet_alignment"
    cr.execute(
        """
        UPDATE ir_config_parameter
        SET key = %s
        WHERE key = %s
        """,
        (new_key, old_key),
    )
    if cr.rowcount:
        _logger.info(
            "Renamed ir.config_parameter key %r to %r (%d row(s) updated)",
            old_key,
            new_key,
            cr.rowcount,
        )
