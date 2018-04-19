# -*- coding: utf-8 -*-
##############################################################################
#
#    Copyright (C) 2018 Compassion CH (http://www.compassion.ch)
#    @author: Sebastien Toth <popod@me.com>
#
#    The licence is in the file __manifest__.py
#
##############################################################################

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class AccountBankStatement(models.Model):
    _inherit = "account.bank.statement"

    can_be_closed = fields.Boolean(string="Can this statement be closed",
                                   default=False)

    IS_CAMT_52 = 'camt.052_'
    IS_CAMT_53 = 'camt.053_'

    @api.model
    def create(self, vals):
        params = self.env['ir.config_parameter']

        # this parameter should be set to use camt52
        postfinance_account_id = int(params.get_param(
            'l10n-switzerland.postfinance_account_id', 0))

        # Check configuration to prevent having duplicated lines if camt052
        # are used
        if self.IS_CAMT_52 in vals['reference'] \
           and not postfinance_account_id:
            raise UserError(_('The parameter l10n-switzerland.postfinance_'
                              'account_id should be set when you parse CAMT'
                              ' 52.'))

        # If this is a PostFinance statement, customize the create() function
        if postfinance_account_id and \
                vals['journal_id'] == postfinance_account_id:
            statement = self.search([
                ('date', '=', vals['date']),
                ('journal_id', '=', postfinance_account_id)
            ])
            # If the statement already exists, we only add missing lines
            if statement:
                bank_statement_line = self.env['account.bank.statement.line']
                new_lines_total_amount = 0.0

                for line in vals['line_ids']:
                    record = line[2]

                    statement_line = statement.line_ids.search([
                        ('acct_svcr_ref', '=', record['acct_svcr_ref'])
                    ])

                    # If the line does not exists, we create it
                    if not statement_line:
                        # Create a statement line
                        record['statement_id'] = statement.id
                        bank_statement_line.create(record)

                        new_lines_total_amount += record['amount']

                    # If the line already exists and is a CAMT53, we update
                    # its fields
                    elif self.IS_CAMT_53 in vals['reference']:
                        line_fields_to_update = {
                            'name': record.get('name', ''),
                            'note': record.get('note', ''),
                            'partner_address': record.get(
                                'partner_address', ''),
                            'partner_account': record.get(
                                'partner_account', ''),
                            'partner_name': record.get('partner_name', ''),
                            'partner_bic': record.get('partner_bic', '')
                        }

                        acct_svcr_ref = record.get('acct_svcr_ref', False)
                        if acct_svcr_ref:
                            line_fields_to_update['acct_svcr_ref'] = \
                                acct_svcr_ref

                        statement_line.write(line_fields_to_update)

                # Update balance amounts
                if self.IS_CAMT_53 in vals['reference']:
                    statement.write({
                        'balance_start': vals['balance_start'],
                        'balance_end_real': vals['balance_end_real'],
                        'can_be_closed': True
                    })
                else:
                    statement.balance_end_real += new_lines_total_amount

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
            raise UserError(_('You cannot close an opened statement.'))
