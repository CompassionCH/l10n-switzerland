# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
import re

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ResPartnerBank(models.Model):
    _inherit = "res.partner.bank"

    l10n_ch_isr_participant = fields.Char(
        string="ISR Participant Number",
        help="ISR (BVR/ESR) participant number linked to the LSV+ / BDD "
        "agreement, e.g. 01-12345-6. Required in direct debit files "
        "(CdtrAgt/FinInstnId/Othr/Id).",
    )

    @api.constrains("l10n_ch_isr_participant")
    def _check_l10n_ch_isr_participant(self):
        for bank in self.filtered("l10n_ch_isr_participant"):
            if not bank._get_l10n_ch_isr_participant_id():
                raise ValidationError(
                    self.env._(
                        "Invalid ISR participant number %s: expected format "
                        "01-12345-6 or 9 digits.",
                        bank.l10n_ch_isr_participant,
                    )
                )

    def _get_l10n_ch_isr_participant_id(self):
        """Return the ISR participant number on 9 digits (e.g. 010123456),
        or False if it is not set or invalid."""
        self.ensure_one()
        number = (self.l10n_ch_isr_participant or "").replace(" ", "")
        match = re.fullmatch(r"(\d{2})-(\d{1,6})-(\d)", number)
        if match:
            number = match[1] + match[2].rjust(6, "0") + match[3]
        return number if re.fullmatch(r"\d{9}", number) else False
