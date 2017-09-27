# -*- coding: utf-8 -*-
"""Add process_camt method to account.bank.statement.import."""
# © 2017 Compassion CH <http://www.compassion.ch>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import models, fields


class AccountBankStatementLine(models.Model):
    """Add process_camt method to account.bank.statement.import."""
    _inherit = 'account.bank.statement.line'

    acct_svcr_ref = fields.Char()

    def camt054_reconcile(self, account_code):
        move_line_obj = self.env['account.move.line']

        move_line_obj = move_line_obj.search([
            ('reconciled', '!=', 'False'),
            ('account_id.code', '=', account_code)
        ])

        list_line = dict()

        # Group each line by acct_svcr_ref
        for line in move_line_obj:
            acct_svcr_ref = line.acct_svcr_ref
            # If there is no acct_svcr_ref, check in the counterpart to find one
            if not acct_svcr_ref:
                line_move_id = line.move_id
                # Search for all line with te given move_id
                move_line_obj_tmp = move_line_obj.search([
                    ('move_id.id', '=', line_move_id.id)])

                line_init_acct_svcr_ref = move_line_obj_tmp[0].acct_svcr_ref
                for line_tmp in move_line_obj_tmp:
                    if line_tmp.acct_svcr_ref:
                        # Check if all the counter part have the same acct_svcr_ref
                        if line_init_acct_svcr_ref == line_tmp.acct_svcr_ref:
                            acct_svcr_ref = line_tmp.acct_svcr_ref
                        else:
                            acct_svcr_ref = False
                            break
                line.acct_svcr_ref = acct_svcr_ref

            if acct_svcr_ref:
                # Add the acct_svcr_ref to the list if it's not already present
                if acct_svcr_ref not in list_line:
                    list_line[acct_svcr_ref] = []
                # If it is already present we add the line the the list of
                # this acct_svcr_ref
                list_line[acct_svcr_ref].append(line)

        for list_acct_svcr_ref in list_line:
            credit = 0
            debit = 0
            move_line_obj = move_line_obj.search([
                ('acct_svcr_ref', '=', list_acct_svcr_ref),
                ('reconciled', '!=', 'False'),
                ('account_id.code', '=', account_code)])

            # Check if credit = debit
            for line in list_line[list_acct_svcr_ref]:
                credit += line.credit
                debit += line.debit
            if credit == debit:
                move_line_obj.process_reconciliation(dict())




