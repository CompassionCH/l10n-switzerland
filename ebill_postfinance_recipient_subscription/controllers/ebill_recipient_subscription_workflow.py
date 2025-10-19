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

    def _render_view(self, is_ajax, template_xml_id, values={}):
        if is_ajax:
            html = request.env['ir.ui.view']._render_template(template_xml_id, values)
            return {'html': html}
        else:
            return request.render(template_xml_id, values)



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

    @http.route('/ebill/subscribe', type='json', auth='public', website=True, sitemap=False)
    def subscribe(self, is_ajax=False, **kw):
        email = kw.get('email')

        if not email:
            return self._render_view(is_ajax, 'ebill_postfinance_recipient_subscription.subscribe_template')

        normalized_email = email_normalize(email)
        if not normalized_email:
            return self._render_view(is_ajax, 'ebill_postfinance_recipient_subscription.subscribe_template',{'submitted_email': email})

        try:
            ebill_service = self._get_ebill_service()
            token_sub = ebill_service.initiate_ebill_recipient_subscription(email)

            return self._render_view(is_ajax, 'ebill_postfinance_recipient_subscription.validate_template',{
                'token': token_sub.SubscriptionInitiationToken,
                'email': email,
            })

        except Exception as e:
            _logger.warning(f"Failed to initiate eBill subscription for email '{email}'.", exc_info=True)
            return self._render_view(is_ajax, 'ebill_postfinance_recipient_subscription.subscribe_template',
                              {'submitted_email': email})

    @http.route('/ebill/validate', type='json', auth='public', website=True, methods=['POST'], sitemap=False)
    def validate(self, is_ajax=False, **post):
        email = post.get('email')

        try:
            ebill_service = self._get_ebill_service()
            token_sub = ebill_service.initiate_ebill_recipient_subscription(email)

            return self._render_view(is_ajax, 'ebill_postfinance_recipient_subscription.validate_template',{
                'token': token_sub.SubscriptionInitiationToken,
                'email': email,
            })

        except Exception as e:
            _logger.error(f"Error during the eBill confirmation process for mail '{email}': {e}", exc_info=True)

            return self._render_view(is_ajax, 'ebill_postfinance_recipient_subscription.retry_template', {
                'email': email,
            })


    @http.route('/ebill/confirm', type='json', auth='public', website=True, methods=['POST'], sitemap=False)
    def confirm(self, is_ajax=False, **post):
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

                return self._render_view(is_ajax, 'ebill_postfinance_recipient_subscription.validate_template', {
                    'error': 'Validation failed. Please check the code.',
                    'token': token,
                    'email': email,
                })

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

            return self._render_view(is_ajax, 'ebill_postfinance_recipient_subscription.success_template')

        except Exception as e:
            _logger.warning(f"Exception during confirmation, likely a wrong activation code for token '{token}': {e}", exc_info=True)

            return self._render_view(is_ajax, 'ebill_postfinance_recipient_subscription.validate_template', {
                'error': 'Validation failed. Please verify the code or check if an eBill connection exists for this email.',
                'token': token,
                'email': email,
            })
