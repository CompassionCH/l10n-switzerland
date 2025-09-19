{
    'name': 'E-Bill PostFinance Recipient Subscription',
    'version': '14.0.1.0.0',
    'category': 'Finance',
    'summary': 'Module for e-bill recipient subscription via PostFinance website workflow.',
    "author": "Compassion CH,Odoo Community Association (OCA)",
    'website': 'https://github.com/CompassionCH/l10n-switzerland',
    'license': 'AGPL-3',
    'depends': [
        'ebill_postfinance',
        'website',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/templates.xml',
    ],
    'installable': True,
}

