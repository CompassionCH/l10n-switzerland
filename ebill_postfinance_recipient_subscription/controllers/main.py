from odoo import http
from odoo.http import request


class EbillSubscriptionController(http.Controller):

    @http.route('/ebill/subscribe', type='http', auth='public', website=True)
    def subscribe(self, **kw):
        """Zeigt die erste Seite an, auf der der Benutzer seine E-Mail eingeben kann."""
        return request.render('ebill_postfinance_recipient_subscription.subscribe_template', {})

    @http.route('/ebill/validate', type='http', auth='public', website=True, methods=['POST'])
    def validate(self, **post):
        """Nimmt die E-Mail entgegen und fordert den Validierungscode an."""
        email = post.get('email')
        ebill_service = request.env['ebill.postfinance.service'].browse(3)

        # API-Aufruf, um den Prozess zu starten
        token_sub = ebill_service.initiate_ebill_recipient_subscription(email)

        # Zeigt die zweite Seite für die Code-Eingabe an
        return request.render('ebill_postfinance_recipient_subscription.validate_template', {
            'token': token_sub.SubscriptionInitiationToken,
            'email': email,
        })
