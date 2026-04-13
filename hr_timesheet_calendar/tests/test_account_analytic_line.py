from datetime import date, datetime

from freezegun import freeze_time

from odoo.addons.base.tests.common import BaseCommon


class TestAccountAnalyticLine(BaseCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.analytic_line_model = cls.env["account.analytic.line"]
        cls.test_user = cls.env.ref("base.user_admin")
        cls.employee = cls.env.ref("hr.employee_hne")
        cls.project = cls.env.ref("project.project_project_2")
        cls.task = cls.env.ref("project.project_2_task_6")

        cls.analytic_line_model = cls.env["account.analytic.line"]
        cls.uom_hour = cls.env.ref("uom.product_uom_hour")
        cls.env["ir.config_parameter"].sudo().set_param(
            "hr_timesheet_time_control.timesheet_alignment", "no-gap"
        )

    @freeze_time("2025-04-03")
    def test_duplicate_today(self):
        # Create a sample analytic line record
        analytic_line = self.analytic_line_model.create(
            {
                "name": "Test Analytic Line",
                "date": date(2025, 4, 2),
                "date_time": datetime(2025, 4, 2, 9, 0),
                "date_time_end": datetime(2025, 4, 2, 17, 0),
                "project_id": self.project.id,
                "account_id": self.project.account_id.id,
                "employee_id": self.employee.id,
            }
        )

        # Call the method to duplicate the record
        new_record_id = self.analytic_line_model.duplicate_today(analytic_line.id)
        new_record = self.analytic_line_model.browse(new_record_id)

        # Assert the new record has today's date
        self.assertEqual(new_record.date, date(2025, 4, 3))

        # Assert the time components are preserved
        self.assertEqual(new_record.date_time, datetime(2025, 4, 3, 9, 0))
        self.assertEqual(new_record.date_time_end, datetime(2025, 4, 3, 17, 0))

        # Assert the new record is not the same as the original
        self.assertNotEqual(new_record.id, analytic_line.id)

    @freeze_time("2025-04-03")
    def test_duplicate_today_no_end(self):
        # Create a sample analytic line record
        analytic_line = self.analytic_line_model.create(
            {
                "name": "Test Analytic Line",
                "date": date(2025, 4, 2),
                "date_time": datetime(2025, 4, 2, 9, 0),
                "project_id": self.project.id,
                "account_id": self.project.account_id.id,
                "employee_id": self.employee.id,
            }
        )

        # Call the method to duplicate the record
        new_record_id = self.analytic_line_model.duplicate_today(analytic_line.id)
        new_record = self.analytic_line_model.browse(new_record_id)

        # Assert the new record has today's date
        self.assertEqual(new_record.date, date(2025, 4, 3))

        # Assert the time components are preserved
        self.assertEqual(new_record.date_time, datetime(2025, 4, 3, 9, 0))
        self.assertEqual(new_record.date_time_end, datetime(2025, 4, 3, 9, 0))

        # Assert the new record is not the same as the original
        self.assertNotEqual(new_record.id, analytic_line.id)
