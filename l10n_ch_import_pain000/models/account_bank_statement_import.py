from odoo import models


class AccountBankStatementImportCustom(models.TransientModel):
    _inherit = 'account.bank.statement.import'
    # _name = 'account.bank.statement.import'

    # def _check_parsed_data(self, stmts_vals):
    #     if stmts_vals == 'pain.001':
    #         return None, stmts_vals
    #     else:
    #         return super(AccountBankStatementImportCustom,self)._check_parsed_data(stmts_vals)
    #
    #
    # def _find_additional_data(self, currency_code, account_number):
    #     if account_number == 'pain.001':
    #         return currency_code, account_number
    #     else:
    #         return super(AccountBankStatementImportCustom,self)._find_additional_data(currency_code,account_number)

    def import_file(self):
        try:
            super(AccountBankStatementImportCustom, self).import_file()
        except :
            action = self.env.ref('account.action_bank_reconcile_bank_statements')

            import_result = {
                'name': action.name,
                'tag': action.tag,
                'context': {
                    'statement_ids': 'dsadasda',
                    'notifications': 'dsadasda'
                },
                'type': 'ir.actions.client',
            }

            test = import_result['context']['statement_ids'][0]

            return {
                'name': action.name,
                'tag': action.tag,
                'context': {
                    'statement_ids': None,
                    'notifications': None
                },
                'type': 'ir.actions.client',
            }
        a = 10
