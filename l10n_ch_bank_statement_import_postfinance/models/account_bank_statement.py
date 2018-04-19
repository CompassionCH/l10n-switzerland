# -*- coding: utf-8 -*-
##############################################################################
#
#    Copyright (C) 2018 Compassion CH (http://www.compassion.ch)
#    @author: Sebastien Toth <popod@me.com>
#
#    The licence is in the file __manifest__.py
#
##############################################################################

from odoo import models, fields, api
from odoo.exceptions import UserError


class AccountBankStatement(models.Model):
    _inherit = "account.bank.statement"

    can_be_closed = fields.Boolean(string="Can this statement be closed",
                                   default=False)

    POSTFINANCE_ACCOUNT_ID = 212
    CHECK_IF_IS_CAMT_53 = 'camt.053_'

    @api.model
    def create(self, vals):
        # If this is a PostFinance statement, customize the create() function
        if vals['journal_id'] == self.POSTFINANCE_ACCOUNT_ID:
            statement = self.search([
                ('date', '=', vals['date']),
                ('journal_id', '=', self.POSTFINANCE_ACCOUNT_ID)
            ])
            # If the statement already exists, we only add missing lines
            if statement:
                BankStatementLine = self.env['account.bank.statement.line']
                new_lines_total = 0.0

                for line in vals['line_ids']:
                    record = line[2]

                    statement_line = statement.line_ids.search([
                        ('svcr_ref', '=', record['svcr_ref'])
                    ])

                    # If the line does not exists, we create it
                    if not statement_line:
                        # Create a statement line
                        record['statement_id'] = statement.id
                        BankStatementLine.create(record)

                        new_lines_total += record['amount']

                    # If the line already exists and is a CAMT53, we update
                    # its fields
                    elif self.CHECK_IF_IS_CAMT_53 in vals['reference']:

                        svcr_ref = record.get('acct_svcr_ref', False)
                        if svcr_ref:
                            statement_line.acct_svcr_ref = svcr_ref
                        statement_line.name = record.get('name', '')
                        statement_line.note = record.get('note', '')
                        statement_line.partner_address = record.get(
                            'partner_address', '')
                        statement_line.partner_account = record.get(
                            'partner_account', '')
                        statement_line.partner_name = record.get(
                            'partner_name', '')
                        statement_line.partner_bic = record.get(
                            'partner_bic', '')

                        statement['balance_start'] = vals['balance_start']
                        statement.can_be_closed = True

                # Update balance amounts
                if self.CHECK_IF_IS_CAMT_53 in vals['reference']:
                    statement['balance_start'] = vals['balance_start']
                    statement['balance_end_real'] = vals['balance_end_real']
                else:
                    statement['balance_end_real'] += new_lines_total

                return statement
            else:
                return super(AccountBankStatement, self).create(vals)
        else:
            return super(AccountBankStatement, self).create(vals)

    @api.multi
    def button_confirm_bank(self):
        if self.can_be_closed:
            return super(AccountBankStatement, self).button_confirm_bank()
        else:
            raise UserError('You cannot close an opened statement.')
