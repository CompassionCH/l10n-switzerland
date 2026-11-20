# Copyright 2023 David Wulliamoz
# License AGPL-3.0 or later (https://www.gnuorg/licenses/agpl).

import logging
import math
from collections import defaultdict

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class HrSalaryDeclaration(models.Model):
    _name = "hr.salary.declaration"
    _description = "Salary declaration for generating xml"

    employee_id = fields.Many2one(comodel_name="hr.employee", string="Employee")
    date_from = fields.Date()
    date_to = fields.Date()
    gross_income = fields.Integer()
    income = fields.Integer()
    company_car = fields.Integer()
    social_ded = fields.Integer()
    bvg_lpp_ded = fields.Integer()
    lump_sum_other = fields.Integer(string="Other lump-sum expenses / N°13.2.3")
    lump_sum_other_text = fields.Char(string="Other lump-sum expenses (kind)")
    child_allowance_by_fund = fields.Boolean(
        string="Child allowances paid by the compensation fund",
        help="Standard remark of field 15: the child allowances are paid "
        "directly by the compensation fund and are not in the certificate.",
    )
    year = fields.Char()

    def _get_particulars(self):
        """Personal data of the employee for the certificate. Since 17.0 the
        private address is on the employee (``private_*`` fields), not on a
        home partner. First and last name come from the work contact when
        partner_firstname splits them, else from the employee name (last word
        as last name)."""
        self.ensure_one()
        # Private data are restricted to HR officers
        employee = self.employee_id.sudo()
        contact = employee.work_contact_id
        if "lastname" in contact._fields and contact.lastname:
            firstname, lastname = contact.firstname or "", contact.lastname
        else:
            names = (employee.name or "").rsplit(" ", 1)
            firstname, lastname = (
                (names[0], names[1]) if len(names) == 2 else ("", names[0])
            )
        lang = (employee.lang or contact.lang or "")[:2]
        return {
            "language": lang if lang in ("", "en") else f"{lang}-CH",
            "firstname": firstname,
            "lastname": lastname,
            "street": " ".join(
                filter(None, [employee.private_street, employee.private_street2])
            ),
            "zip": employee.private_zip or "",
            "city": employee.private_city or "",
            "country": employee.private_country_id.name or "",
        }

    @api.model
    def generate_yearly_declaration(
        self,
        date_from,
        date_to,
        company_car,
        gross_income,
        deduction,
        lpp_bvg,
        lump_sum_rules=None,
        lump_sum_text="",
        child_allowance_by_fund=False,
    ):
        payslip_lines = self.env["hr.payslip.line"].search(
            [
                ("slip_id.date_from", ">=", date_from),
                ("slip_id.date_to", "<=", date_to),
                ("slip_id.state", "=", "done"),
            ]
        )
        employee_ids = payslip_lines.employee_id.ids
        grossincome = defaultdict(float)
        companycar = defaultdict(float)
        social_ded = defaultdict(float)
        bvg_lpp_ded = defaultdict(float)
        lump_sum = defaultdict(float)
        d_from = {}
        d_to = {}
        for line in payslip_lines:
            emp_id = line.employee_id.id
            if line.salary_rule_id == gross_income:
                grossincome[emp_id] += line.total
            elif line.salary_rule_id == lpp_bvg:
                bvg_lpp_ded[emp_id] -= line.total
            elif line.salary_rule_id == deduction:
                social_ded[emp_id] -= line.total
            elif line.salary_rule_id == company_car:
                companycar[emp_id] -= line.total
            elif lump_sum_rules and line.salary_rule_id in lump_sum_rules:
                lump_sum[emp_id] += line.total

            slip_date_from = line.slip_id.date_from
            slip_date_to = line.slip_id.date_to
            if emp_id not in d_from or slip_date_from < d_from[emp_id]:
                d_from[emp_id] = slip_date_from
            if emp_id not in d_to or slip_date_to > d_to[emp_id]:
                d_to[emp_id] = slip_date_to
        _logger.info("generating '%s' salary declaration", len(employee_ids))

        salary_declarations = []
        for emp in employee_ids:
            sd_vals = {
                "employee_id": emp,
                "date_from": d_from[emp],
                "date_to": d_to[emp],
                "gross_income": math.floor(grossincome[emp]),
                "income": math.floor(grossincome[emp] - companycar[emp]),
                "company_car": math.floor(companycar[emp]),
                "social_ded": math.ceil(social_ded[emp] - bvg_lpp_ded[emp]),
                "bvg_lpp_ded": math.ceil(bvg_lpp_ded[emp]),
                "lump_sum_other": round(lump_sum[emp]),
                "lump_sum_other_text": lump_sum[emp] and lump_sum_text or False,
                "child_allowance_by_fund": child_allowance_by_fund,
                "year": date_to.strftime("%Y-%m-%d")[:4],
            }
            salary_declarations.append(sd_vals)

        self.create(salary_declarations)
