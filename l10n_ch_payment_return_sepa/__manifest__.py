# © 2017-2018 Compassion CH (Marco Monzione)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
{
    'name': 'Import pain002',
    'version': '11.0.0.0.0',
    'license': 'AGPL-3',
    'author': 'Compassion CH, Odoo Community Association (OCA)',
    'website': 'https://www.compassion.ch',
    'category': 'Banking addons',
    'depends': [
        'account_payment_order',
        'account_bank_statement_import_camt_oca',  # oca_addons/bank-payment
        'account_payment_return_import_sepa_pain',
            # oca_addons/account-payment
        'l10n_ch_pain_direct_debit',
        'l10n_ch_pain_credit_transfer'
    ],
    'demo': [
        'demo/demo.yml'
    ],
    'installable': True
}
