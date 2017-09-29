from odoo import models, api

import base64
import logging

_logger = logging.getLogger(__name__)


class FdsFilesImportToBankStatementsWizardPain000(models.TransientModel):
    _inherit = 'fds.files.import.tobankstatments.wizard'

    @api.multi
    def _import2bankStatements(self, fds_files_ids):
        account_pain000 = self.env['account.pain000.parser']
        for fds_file in fds_files_ids:
            for pf_file in fds_file:
                values = {'data_file': pf_file.data}
                bs_import_obj = self.env['account.bank.statement.import']
                bank_wiz_imp = bs_import_obj.create(values)

                decoded_file = base64.b64decode(bank_wiz_imp.data_file)
                if account_pain000.parse(decoded_file):
                    pf_file.write({
                        'state': 'done',
                        'data': None,
                     })

                    _logger.info("[OK] import file '%s' to bank Statements",(pf_file.filename))
                else:
                    return super(
                        FdsFilesImportToBankStatementsWizardPain000, self)._import2bankStatements(fds_files_ids)

        self.msg_file_imported += fds_file.filename + "; "
        return True
