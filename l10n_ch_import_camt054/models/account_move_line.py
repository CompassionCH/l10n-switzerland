from odoo import models, fields

class accountMoveLine(models.Model):
    _inherit = 'account.move.line'
    # The new field would be use for an automatic reconciliation.
    acct_svcr_ref = fields.Char()
