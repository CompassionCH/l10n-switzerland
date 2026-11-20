# Copyright 2020 David Wulliamoz
# License AGPL-3.0 or later (https://www.gnuorg/licenses/agpl).

from datetime import date

from odoo import Command, api, fields, models

# Salary rules of the wizard, remembered from one year to the next
RULE_FIELDS = ("gross_income", "lpp_bvg", "company_car", "deduction")
PARAM = "l10n_ch_hr_payroll_ecertificate.%s_rule_id"
PARAM_CHILD_ALLOWANCE = "l10n_ch_hr_payroll_ecertificate.child_allowance_by_fund"


class GenSdWizard(models.TransientModel):
    _name = "hr.salary.declaration.wizard"
    _description = "Generate salary declaration"

    date_from = fields.Date(
        string="Date from",
        default=lambda self: date(fields.Date.context_today(self).year - 1, 1, 1),
    )
    date_to = fields.Date(
        string="Date to",
        default=lambda self: date(fields.Date.context_today(self).year - 1, 12, 31),
    )
    gross_income = fields.Many2one("hr.salary.rule", string="Gross income / N°8")
    lpp_bvg = fields.Many2one("hr.salary.rule", string="BVG/LPP / N°10.1")
    company_car = fields.Many2one(
        "hr.salary.rule", string="Private use of company car / N°2.2"
    )
    deduction = fields.Many2one("hr.salary.rule", string="Total deduction / N°9")
    lump_sum_rule_ids = fields.Many2many(
        "hr.salary.rule",
        string="Other lump-sum expenses / N°13.2.3",
        help="E.g. the home office allowances. Their sum is declared under "
        "13.2.3 with the kind below.",
    )
    lump_sum_text = fields.Char(
        string="Kind of lump-sum expenses", default="Home office"
    )
    child_allowance_by_fund = fields.Boolean(
        string="Child allowances paid by the compensation fund / N°15",
        help="Standard remark: the child allowances are paid directly by the "
        "compensation fund and are not in the certificate.",
    )

    @api.model
    def default_get(self, fields_list):
        """The salary rules used the last time (the declaration is done once
        a year)."""
        res = super().default_get(fields_list)
        params = self.env["ir.config_parameter"].sudo()
        for name in RULE_FIELDS:
            rule_id = params.get_param(PARAM % name)
            if name in fields_list and rule_id and rule_id.isdigit():
                rule = self.env["hr.salary.rule"].browse(int(rule_id)).exists()
                if rule:
                    res[name] = rule.id
        if "lump_sum_rule_ids" in fields_list:
            ids = params.get_param(PARAM % "lump_sum", "").split(",")
            rules = self.env["hr.salary.rule"].browse(
                [int(i) for i in ids if i.isdigit()]
            )
            res["lump_sum_rule_ids"] = [Command.set(rules.exists().ids)]
        text = params.get_param("l10n_ch_hr_payroll_ecertificate.lump_sum_text")
        if "lump_sum_text" in fields_list and text:
            res["lump_sum_text"] = text
        if "child_allowance_by_fund" in fields_list:
            res["child_allowance_by_fund"] = (
                params.get_param(PARAM_CHILD_ALLOWANCE) == "1"
            )
        return res

    def gen_sd(self):
        params = self.env["ir.config_parameter"].sudo()
        for name in RULE_FIELDS:
            params.set_param(PARAM % name, self[name].id or "")
        params.set_param(
            PARAM % "lump_sum", ",".join(map(str, self.lump_sum_rule_ids.ids))
        )
        params.set_param(
            "l10n_ch_hr_payroll_ecertificate.lump_sum_text", self.lump_sum_text or ""
        )
        params.set_param(
            PARAM_CHILD_ALLOWANCE, "1" if self.child_allowance_by_fund else "0"
        )
        sd_obj = self.env["hr.salary.declaration"]
        sd_obj.generate_yearly_declaration(
            self.date_from,
            self.date_to,
            self.company_car,
            self.gross_income,
            self.deduction,
            self.lpp_bvg,
            lump_sum_rules=self.lump_sum_rule_ids,
            lump_sum_text=self.lump_sum_text,
            child_allowance_by_fund=self.child_allowance_by_fund,
        )
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "l10n_ch_hr_payroll_ecertificate.open_view_sd_tree"
        )
        action["domain"] = [("year", "=", str(self.date_to.year))]
        action["context"] = {}
        return action
