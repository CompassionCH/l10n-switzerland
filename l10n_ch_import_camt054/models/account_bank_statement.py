
from odoo import models, fields

class AccountBankStatement(models.Model):
    _inherit = 'account.bank.statement.line'

    def _prepare_reconciliation_move_line(self, move, amount):
        data = super(AccountBankStatement,self)._prepare_reconciliation_move_line(move, amount)
        data['acctSvcrRef'] = self.acctSvcrRef
        return data
