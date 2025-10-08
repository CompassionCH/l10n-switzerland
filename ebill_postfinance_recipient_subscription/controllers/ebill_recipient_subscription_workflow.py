import logging
import json
from odoo import http
from odoo.http import request
from odoo.tools import email_normalize
from odoo.http import Response

_logger = logging.getLogger(__name__)


class EbillSubscriptionController(http.Controller):


    def _get_ebill_service(self):
        biller_id = request.env['ir.config_parameter'].sudo().get_param('ebill_postfinance.biller_id')
        return request.env['ebill.postfinance.service'].sudo().search([('biller_id', '=', biller_id)], limit=1)

    @http.route('/ebill/bulk/search', type='json', auth='public', methods=['POST'], sitemap=False)
    def bulk_search(self, **kw):
        try:
            data = json.loads(request.httprequest.data)
            recipient_ids = data.get('params', {}).get('recipient_ids')

            if not isinstance(recipient_ids, list):
                return {'info': 'The param recipient_ids has to be a list.'}

            ebill_service = self._get_ebill_service()
            results = ebill_service.get_ebill_recipient_subscription_status_bulk(recipient_ids)

            #TODO create contract with results

            return results

        except Exception as e:
            if 'Missing element SubmissionStatus' in str(e):
                _logger.warning("No ebill recipient found for the given IDs (service raised exception).")
                return {'info': 'No ebill recipient was found for the provided recipient_ids.'}
            else:
                _logger.error(f"Unexpected Exception during bulk search occurred: {e}", exc_info=True)
                return {'error': 'An internal server error occurred.'}

    @http.route('/ebill/subscribe', type='http', auth='public', website=True, sitemap=False)
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

    @http.route('/ebill/validate', type='http', auth='public', website=True, methods=['POST'], sitemap=False)
    def validate(self, **post):
        email = post.get('email')
        try:
            ebill_service = self._get_ebill_service()
            token_sub = ebill_service.initiate_ebill_recipient_subscription(email)

            return request.render('ebill_postfinance_recipient_subscription.validate_template', {
                'token': token_sub.SubscriptionInitiationToken,
                'email': email,
            })
        except Exception as e:
            _logger.error(f"Error during the eBill confirmation process for mail '{email}': {e}", exc_info=True)
            return request.render('ebill_postfinance_recipient_subscription.retry_template')

#index = flase
    @http.route('/ebill/confirm', type='http', auth='public', website=True, methods=['POST'], sitemap=False)
    def confirm(self, **post):
        token = post.get('token')
        activation_code = post.get('validation_code')
        email = post.get('email')
        ebill_service = self._get_ebill_service()

        try:
            partner_data = ebill_service.confirm_ebill_recipient_subscription(
                token, activation_code
            )

            if not (partner_data and partner_data.get('eBillAccountID')):
                _logger.warning(f"eBill validation failed for token '{token}' (e.g., incorrect code).")
                return request.render('ebill_postfinance_recipient_subscription.subscribe_template',
                                      {'error': 'Validation failed. Please check the code.'})

            partner_email = partner_data.get('eMailAddress')
            partner = request.env['res.partner'].sudo().search([('email', '=', partner_email)], limit=1)
            if not partner:

                partner_address = partner_data.get('Party', {}).get('Address', {})

                name = partner_address.get('GivenName') + ' ' + partner_address.get('LastName') or partner_email.split('@')[0]
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

            transmit_method_id = request.env['transmit.method'].sudo().search([('code', '=', 'postfinance')], limit=1)
            request.env['ebill.payment.contract'].sudo().create({
                'partner_id': partner.id,
                'transmit_method_id': transmit_method_id.id,
                'state': 'open',
                'postfinance_service_id': ebill_service.id,
                'postfinance_billerid': partner_data.get('eBillAccountID')
            })

            return request.render('ebill_postfinance_recipient_subscription.success_template', {})

        except Exception as e:
            _logger.warning(f"Exception during confirmation, likely a wrong activation code for token '{token}': {e}", exc_info=True)

            return request.render('ebill_postfinance_recipient_subscription.validate_template', {
                'error': 'The Validation Code was wrong. Please try again or request a new one.',
                'token': token,
                'email': email
            })
