# © 2015 Compassion CH (Nicolas Tran)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import models, fields, api
import logging
from odoo.addons.l10n_ch_payment_return_sepa.models.errors import\
    NoTransactionsError, FileAlreadyImported
from odoo.exceptions import Warning as UserError

_logger = logging.getLogger(__name__)


class FdsPostfinanceFile(models.Model):
    _inherit = 'fds.postfinance.file'

    payment_return_id = fields.Many2one(
        comodel_name='payment.return',
        string='Payment Return',
        ondelete='restrict',
        readonly=True,
    )
    payment_order = fields.Many2one(
        'account.payment.order',
        string='Payment order',
        ondelete='restrict',
        readonly=True,
    )
    file_type = fields.Selection(selection_add=[
        ('pain.002.001.03.ch.02',
         'pain.002.001.03.ch.02 (payment return)')
    ])

    @api.multi
    def import_to_payment_return_button(self):
        """ convert the file to record of model payment return.
            Called by pressing import button.

            :return None:
        """
        valid_files = self.filtered(lambda f: f.state == 'draft')
        valid_files.import_to_payment_return()

    @api.multi
    def import_to_payment_return(self):
        """ convert the file to a record of model payment return."""
        try:
            values = {
                'data_file': self.data,
                'filename': self.filename
            }
            pr_import_obj = self.env['payment.return.import']
            pr_wiz_imp = pr_import_obj.create(values)
            import_result = pr_wiz_imp.import_file()
            payment_return = self.env["payment.return"].browse(import_result['res_id'])
            # Mark the file as imported, remove binary as it should be
            # attached to the statement.
            self.write({
                'state': 'done',
                'payment_return_id': payment_return.id,
                'payment_order': payment_return.payment_order_id.id,
                'error_message': False
            })
            # Automatically confirm payment returns
            payment_return.action_confirm()
            _logger.info("[OK] import file '%s'", self.filename)
        except NoTransactionsError as e:
            _logger.info(e.name, self.filename)
            self.write({
                'state': 'done',
                'error_message': e.name
            })
        except FileAlreadyImported as e:
            _logger.info(e.name, self.filename)
            references = [x['reference'] for x in e.object[0]['transactions']]
            payment_return = self.env['payment.return']\
                .search([('line_ids.reference', 'in', references)])
            self.write({
                'state': 'done',
                'payment_return_id': payment_return.id,
                'error_message': e.name
            })
        except UserError as e:
            # wrong parser used, raise the error to the parent so it's not
            # catch by the following except Exception
            raise e
        except Exception as e:
            self.env.cr.rollback()
            self.invalidate_cache()
            # Write the error in the postfinance file
            if self.state != 'error':
                self.write({
                    'state': 'error',
                    'error_message': e.args and e.args[0]
                })
                # Here we must commit the error message otherwise it
                # can be unset by a next file producing an error
                # pylint: disable=invalid-commit
                self.env.cr.commit()
            _logger.error(
                "[FAIL] import file '%s' to bank Statements",
                self.filename,
                exc_info=True
            )
