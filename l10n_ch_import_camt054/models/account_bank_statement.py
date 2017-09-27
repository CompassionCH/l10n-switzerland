
from odoo import models, fields

class AccountBankStatement(models.Model):
    _inherit = 'account.bank.statement'

    def _prepare_reconciliation_move_line(self, move, amount):
        data = super(AccountBankStatement,self)._prepare_reconciliation_move_line(move, amount)
        data['acct_svcr_ref'] = self.acct_svcr_ref
        return data
