from odoo import models, fields

class accountMoveLine(models.Model):
    """Add process_camt method to account.bank.statement.import."""
    _inherit = 'account.move.line'

    acctSvcrRef = fields.Char()
