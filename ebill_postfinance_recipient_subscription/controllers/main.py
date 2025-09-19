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

    @http.route('/ebill/confirm', type='http', auth='public', website=True, methods=['POST'])
    def confirm(self, **post):
        """Nimmt den Code entgegen, validiert ihn und erstellt den Vertrag."""
        token = post.get('token')
        activation_code = post.get('validation_code')
        ebill_service = request.env['ebill.postfinance.service'].browse(3)

        # API-Aufruf zur Bestätigung
        partner_data = ebill_service.confirm_ebill_recipient_subscription(token, activation_code)

        # Partner in Odoo finden oder erstellen
        partner = request.env['res.partner'].search([('email', '=', partner_data['EmailAddress'])], limit=1)
        if not partner:
            # Erstellen Sie hier eine Logik, um einen neuen Partner zu erstellen, falls gewünscht
            pass

        if partner:
            # Erstellen des ebill.payment.contract
            request.env['ebill.payment.contract'].create({
                'partner_id': partner.id,
                'ebill_account_id': partner_data['EbillAccountID'],
                'type': 'private',  # Passen Sie dies bei Bedarf an
            })

        # Zeigt die Erfolgsseite an
        return request.render('ebill_postfinance_recipient_subscription.success_template', {})
