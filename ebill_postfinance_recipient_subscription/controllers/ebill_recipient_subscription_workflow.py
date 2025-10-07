import logging
from odoo import http
from odoo.http import request
from odoo.tools import email_normalize

_logger = logging.getLogger(__name__)


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
                _logger.warning(f"Failed to initiate eBill subscription for email '{email}'.", exc_info=True)
                return request.render('ebill_postfinance_recipient_subscription.subscribe_template', {
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

        try:
            ebill_service = self._get_ebill_service()
            partner_data = ebill_service.confirm_ebill_recipient_subscription(
                token, activation_code
            )

            if not (partner_data and partner_data.get('EbillAccountID')):
                _logger.warning(f"eBill validation failed for activation code '{activation_code}' (e.g., incorrect code).")
                return request.render('ebill_postfinance_recipient_subscription.subscribe_template',
                                      {'error': 'Validation failed. Please check the code.'})

            if partner_data and partner_data.get('EbillAccountID'):
                partner_email = partner_data.get('EmailAddress')
                partner = request.env['res.partner'].sudo().search([('email', '=', partner_email)], limit=1)
                if not partner:

                    partner_address = partner_data.get('Party', {}).get('Address', {})

                    name = partner_address.get('GivenName') + partner_address.get('LastName') or partner_email.split('@')[0]
                    street = partner_address.get('Address1')
                    zip = partner_address.get('ZIP')
                    city = partner_address.get('City')


                    partner = request.env['res.partner'].sudo().create({
                        'name': name,
                        'street': street,
                        'zip': zip,
                        'city': city,
                        'email': partner_email
                    })

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

        except Exception as e:

            _logger.error(f"Error during the eBill confirmation process for token '{token}' and activation code '{activation_code}'.", exc_info=True)
            return request.render('ebill_postfinance_recipient_subscription.subscribe_template',
                          {'error': 'Validierung fehlgeschlagen'})
