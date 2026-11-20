# Copyright 2026 Compassion Suisse
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from datetime import date

from lxml import etree

from odoo import Command
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestSalaryDeclaration(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env["res.lang"]._activate_lang("fr_CH")
        cls.employee = cls.env["hr.employee"].create(
            {
                "name": "Jean-Marc de Test",
                "lang": "fr_CH",
                "birthday": date(1980, 5, 17),
                "identification_id": "756.1234.5678.97",
                "private_street": "Rue du Lac 3",
                "private_street2": "Case 12",
                "private_zip": "1400",
                "private_city": "Yverdon-les-Bains",
                "private_country_id": cls.env.ref("base.ch").id,
            }
        )
        cls.declaration = cls.env["hr.salary.declaration"].create(
            {
                "employee_id": cls.employee.id,
                "date_from": date(2025, 1, 1),
                "date_to": date(2025, 12, 31),
                "gross_income": 60000,
                "income": 60000,
                "social_ded": 4000,
                "bvg_lpp_ded": 2500,
                "year": "2025",
            }
        )

    def _render(self):
        xml, _format = self.env["ir.actions.report"]._render_qweb_xml(
            "l10n_ch_hr_payroll_ecertificate.salary_declaration_report",
            self.declaration.ids,
        )
        return etree.fromstring(xml).xpath("//Person/Particulars")[0]

    def test_particulars_from_private_address(self):
        particulars = self._render()
        values = {
            tag: particulars.findtext(".//" + tag)
            for tag in (
                "Language",
                "DateOfBirth",
                "SV-AS-Number",
                "Street",
                "ZIP-Code",
                "City",
                "Country",
            )
        }
        self.assertEqual(
            values,
            {
                "Language": "fr-CH",
                "DateOfBirth": "1980-05-17",
                "SV-AS-Number": "756.1234.5678.97",
                "Street": "Rue du Lac 3 Case 12",
                "ZIP-Code": "1400",
                "City": "Yverdon-les-Bains",
                "Country": "Switzerland",
            },
        )

    def test_names(self):
        contact = self.employee.work_contact_id
        if "lastname" in contact._fields:
            # partner_firstname installed: names of the work contact
            contact.write({"firstname": "Jean-Marc", "lastname": "de Test"})
            expected = ("Jean-Marc", "de Test")
        else:
            # Last word of the employee name as last name
            expected = ("Jean-Marc de", "Test")
        particulars = self._render()
        self.assertEqual(
            (particulars.findtext("Firstname"), particulars.findtext("Lastname")),
            expected,
        )

    def test_english(self):
        self.employee.lang = "en_US"
        self.assertEqual(self._render().findtext("Language"), "en")

    def test_wizard_prefilled(self):
        Wizard = self.env["hr.salary.declaration.wizard"]
        rule = self.env["hr.salary.rule"].create({"name": "Gross test", "code": "GT"})
        wizard = Wizard.create({})
        last_year = date.today().year - 1
        self.assertEqual(wizard.date_from, date(last_year, 1, 1))
        self.assertEqual(wizard.date_to, date(last_year, 12, 31))
        wizard.gross_income = rule
        action = wizard.gen_sd()
        self.assertEqual(action["res_model"], "hr.salary.declaration")
        # The rule chosen is proposed the next time
        self.assertEqual(Wizard.create({}).gross_income, rule)
        self.assertFalse(Wizard.create({}).lpp_bvg)

    def test_lump_sum_expenses(self):
        """Home office allowances declared under 13.2.3 (Charges/LumpSum/Other)."""
        Rule = self.env["hr.salary.rule"]
        gross = Rule.create({"name": "Gross test", "code": "GT"})
        internet = Rule.create({"name": "Internet HO", "code": "INT_T"})
        office = Rule.create({"name": "Office HO", "code": "OFFU_T"})
        contract = self.env["hr.contract"].create(
            {"name": "Test", "employee_id": self.employee.id, "wage": 5000}
        )
        for month in (1, 2):
            self.env["hr.payslip"].create(
                {
                    "employee_id": self.employee.id,
                    "contract_id": contract.id,
                    "date_from": date(2025, month, 1),
                    "date_to": date(2025, month, 28),
                    "state": "done",
                    "line_ids": [
                        Command.create(
                            {
                                "name": rule.name,
                                "code": rule.code,
                                "salary_rule_id": rule.id,
                                "employee_id": self.employee.id,
                                "contract_id": contract.id,
                                "amount": amount,
                            }
                        )
                        for rule, amount in (
                            (gross, 5000),
                            (internet, 40.5),
                            (office, 60),
                        )
                    ],
                }
            )
        wizard = self.env["hr.salary.declaration.wizard"].create(
            {
                "date_from": date(2025, 1, 1),
                "date_to": date(2025, 12, 31),
                "gross_income": gross.id,
                "lump_sum_rule_ids": [Command.set((internet | office).ids)],
                "lump_sum_text": "Participation frais de télétravail",
                "child_allowance_by_fund": True,
            }
        )
        wizard.gen_sd()
        declaration = self.env["hr.salary.declaration"].search(
            [("employee_id", "=", self.employee.id), ("id", "!=", self.declaration.id)]
        )
        self.assertEqual(declaration.gross_income, 10000)
        self.assertEqual(declaration.lump_sum_other, 201)
        xml, _format = self.env["ir.actions.report"]._render_qweb_xml(
            "l10n_ch_hr_payroll_ecertificate.salary_declaration_report",
            declaration.ids,
        )
        other = etree.fromstring(xml).xpath("//TaxSalary/Charges/LumpSum/Other")[0]
        self.assertEqual(other.findtext("Sum"), "201")
        self.assertEqual(other.findtext("Text"), "Participation frais de télétravail")
        self.assertEqual(
            etree.fromstring(xml).findtext(
                ".//TaxSalary/StandardRemark/ChildAllowancePerAHV-AVS"
            ),
            "True",
        )
        # Remembered for next year
        next_wizard = self.env["hr.salary.declaration.wizard"].create({})
        self.assertEqual(next_wizard.lump_sum_rule_ids, internet | office)
        self.assertEqual(
            next_wizard.lump_sum_text, "Participation frais de télétravail"
        )
        # No lump-sum expenses: no Charges
        xml, _format = self.env["ir.actions.report"]._render_qweb_xml(
            "l10n_ch_hr_payroll_ecertificate.salary_declaration_report",
            self.declaration.ids,
        )
        self.assertFalse(etree.fromstring(xml).xpath("//Charges"))
        self.assertFalse(etree.fromstring(xml).xpath("//StandardRemark"))
