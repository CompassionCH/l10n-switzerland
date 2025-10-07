from odoo import http
from odoo.http import request
from odoo.tools import email_normalize


class EbillSubscriptionController(http.Controller):


    def _get_ebill_service(self):
        return request.env['ebill.postfinance.service'].sudo().browse(3)

    @http.route('/ebill/subscribe', type='http', auth='public', website=True)
    def subscribe(self, **kw):
        email = kw.get('email')

        if email:
            try:
                normalized_email = email_normalize(email)
                if not normalized_email:
                    return request.render('ebill_postfinance_recipient_subscription.subscribe_template', {
                        'submitted_email': email
                    })

                ebill_service = self._get_ebill_service()
                token_sub = ebill_service.initiate_ebill_recipient_subscription(email)

                return request.render('ebill_postfinance_recipient_subscription.validate_template', {
                    'token': token_sub.SubscriptionInitiationToken,
                    'email': email,
                })
            except Exception as e:
                return request.render('ebill_postfinance_recipient_subscription.subscribe_template', {
                    'error': f'{e}',
                    'submitted_email': email
                })

        return request.render('ebill_postfinance_recipient_subscription.subscribe_template', {})

    @http.route('/ebill/validate', type='http', auth='public', website=True, methods=['POST'])
    def validate(self, **post):
        email = post.get('email')
        ebill_service = self._get_ebill_service()

        token_sub = ebill_service.initiate_ebill_recipient_subscription(email)

        return request.render('ebill_postfinance_recipient_subscription.validate_template', {
            'token': token_sub.SubscriptionInitiationToken,
            'email': email,
        })

    @http.route('/ebill/confirm', type='http', auth='public', website=True, methods=['POST'])
    def confirm(self, **post):
        token = post.get('token')
        activation_code = post.get('validation_code')
        ebill_service = self._get_ebill_service()

        partner_data = None
        try:
            partner_data = ebill_service.confirm_ebill_recipient_subscription(
                token, activation_code
            )
        except ValueError as e:
            print("validation failed", e)

        if partner_data and partner_data.get('EbillAccountID'):
            partner_email = partner_data.get('EmailAddress')
            partner = request.env['res.partner'].sudo().search([('email', '=', partner_email)], limit=1)
            if not partner:
                print("partner should be created")
                name = partner_email.split('@')[0]
                partner = request.env['res.partner'].sudo().create({'name': name, 'email': partner_email})

            if partner:
                contract_vals = {
                    'partner_id': partner.id,
                    'postfinance_service_id': ebill_service.id,
                    'ebill_account_id': partner_data.get('EbillAccountID'),
                    'state': 'open',
                }
                request.env['ebill.payment.contract'].sudo().create(contract_vals)
                print("new contract gets created")

            return request.render('ebill_postfinance_recipient_subscription.success_template', {})

        return request.render('ebill_postfinance_recipient_subscription.subscribe_template',
                          {'error': 'Validierung fehlgeschlagen'})
