# -*- coding: utf-8 -*-
"""Add process_camt method to account.bank.statement.import."""
# © 2017 Compassion CH <http://www.compassion.ch>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import models, fields


class AccountBankStatementLine(models.Model):
    """Add process_camt method to account.bank.statement.import."""
    _inherit = 'account.bank.statement.line'

    acctSvcrRef = fields.Char()

    def camt054_reconcile(self, account_code):
        move_line_obj = self.env['account.move.line']

        move_line_obj = move_line_obj.search([
            ('reconciled', '!=', 'False'),
            ('account_id.code', '=', account_code)
        ])

        list_line = dict()

        # Group each line by acctsvcrref
        for line in move_line_obj:
            acctSvcrRef = line.acctSvcrRef
            # If there is no acctSvcrRef, check in the counterpart to find one
            if not acctSvcrRef:
                line_move_id = line.move_id
                # Search for all line with te given move_id
                move_line_obj_tmp = move_line_obj.search([
                    ('move_id.id', '=', line_move_id.id)])

                line_init_acct_svcr_ref = move_line_obj_tmp[0].acctSvcrRef
                for line_tmp in move_line_obj_tmp:
                    if line_tmp.acctSvcrRef:
                        # Check if all the counter part have the same acctSvcrRef
                        if line_init_acct_svcr_ref == line_tmp.acctSvcrRef:
                            acctSvcrRef = line_tmp.acctSvcrRef
                        else:
                            acctSvcrRef = False
                            break
                line.acctSvcrRef = acctSvcrRef

            if acctSvcrRef:
                # Add the acctSvcrRef to the list if it's not already present
                if acctSvcrRef not in list_line:
                    list_line[acctSvcrRef] = []
                # If it is already present we add the line the the list of
                # this acctSvcrRef
                list_line[acctSvcrRef].append(line)

        for list_acctsvcrref in list_line:
            credit = 0
            debit = 0
            move_line_obj = move_line_obj.search([
                ('acctSvcrRef', '=', list_acctsvcrref),
                ('reconciled', '!=', 'False'),
                ('account_id.code', '=', account_code)])

            # Check if credit = debit
            for line in list_line[list_acctsvcrref]:
                credit += line.credit
                debit += line.debit
            if credit == debit:
                move_line_obj.process_reconciliation(dict())




