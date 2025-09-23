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

        try:
            partner_data = ebill_service.confirm_ebill_recipient_subscription(
                token, activation_code
            )
        except ValueError as e:
            print("validation failed", e)
            # show resend email button

        if partner_data and partner_data.get('EbillAccountID'):
            # 1. Partner in Odoo finden oder erstellen
            partner_email = partner_data.get('EmailAddress')
            partner = request.env['res.partner'].sudo().search([('email', '=', partner_email)], limit=1)
            if not partner:
                print("partner should be created")

            # 2. Den korrekten E-Bill-Vertrag erstellen
            if partner:
                contract_vals = {
                    'partner_id': partner.id,
                    'postfinance_service_id': ebill_service.id,
                    'ebill_account_id': partner_data.get('EbillAccountID'),
                    'state': 'open',  # Setzt den Vertrag direkt auf "offen" und damit gültig
                }
                # new_contract = request.env['ebill.payment.contract'].sudo().create(contract_vals)
                print("new contract gets created")

            return request.render('ebill_postfinance_recipient_subscription.success_template', {})


        return request.render('ebill_postfinance_recipient_subscription.subscribe_template',
                          {'error': 'Validierung fehlgeschlagen'})
