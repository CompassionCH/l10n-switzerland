# Copyright 2019 ACSONE SA/NV <thomas.binsfeld@acsone.eu>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models, _


class AccountJournal(models.Model):
    _inherit = "account.journal"

    should_qr_parsing = fields.Boolean(
        string="QR IBAN for import",
        help="Parse the account QR iban field for CAMT54\n"
             "This field can't accept three journals with the same account number."
    )
