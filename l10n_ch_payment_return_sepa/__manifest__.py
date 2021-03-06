# © 2017-2018 Compassion CH (Marco Monzione)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
{
    'name': 'Parse payment return',
    'version': '12.0.1.0.0',
    'license': 'AGPL-3',
    'author': 'Compassion CH, Odoo Community Association (OCA)',
    'website': 'https://www.compassion.ch',
    'category': 'Banking addons',
    'depends': [
        'account_payment_order',  # OCA/bank-payment
        'account_payment_return_import_iso20022',  # OCA/account-payment
        'l10n_ch_pain_direct_debit',
        'l10n_ch_pain_credit_transfer'
    ],
    'demo': [],
    'installable': True,
    'auto_install': True,
}
