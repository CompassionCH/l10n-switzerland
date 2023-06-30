# Copyright 2023 Compassion CH <https://compassion.ch>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models, _, api


class AccountJournal(models.Model):
    _inherit = "account.journal"

    should_qr_parsing = fields.Boolean(
        string="QR IBAN for import",
        help="Parse the account QR iban field for CAMT54\n"
             "This field can't accept three journals with the same account number."
    )
    
    @api.model
    def _qr_iban_defined_qr_parsing(self):
        for journal in self:
            if journal.should_qr_parsing and not journal.bank_account_id.l10n_ch_qr_iban:
                return False
        return True

    _constraints = [(
        _qr_iban_defined_qr_parsing,
        'The QR IBAN should be defined on the bank account if you use QR IBAN for import on the journal',
        ['should_qr_parsing']
    )]
