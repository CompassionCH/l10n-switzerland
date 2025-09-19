from odoo import http
from odoo.http import request


class EbillSubscriptionController(http.Controller):

    @http.route('/ebill/subscribe', type='http', auth='public', website=True)
    def subscribe(self, **kw):
        """Zeigt die erste Seite an, auf der der Benutzer seine E-Mail eingeben kann."""
        return request.render('ebill_postfinance_recipient_subscription.subscribe_template', {})

