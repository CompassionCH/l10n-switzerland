import json
import logging

from odoo import http
from odoo.http import request
from odoo.tools import email_normalize

_logger = logging.getLogger(__name__)


def _get_ebill_service():
    biller_id = (
        request.env["ir.config_parameter"]
        .sudo()
        .get_param("ebill_postfinance.biller_id")
    )
    return (
        request.env["ebill.postfinance.service"]
        .sudo()
        .search([("biller_id", "=", biller_id)], limit=1)
    )


def _render_view(is_integrated, template_xml_id, values=None):
    values = dict(values or {})
    if is_integrated:
        values["is_integrated"] = is_integrated
        return request.env["ir.ui.view"]._render_template(template_xml_id, values)
    else:
        return request.render(template_xml_id, values)


class EbillSubscriptionController(http.Controller):
    @http.route(
        "/ebill/bulk/search",
        type="json",
        auth="public",
        methods=["POST"],
        sitemap=False,
        csrf=False,
    )
    def bulk_search(self, **kw):
        try:
            data = json.loads(request.httprequest.data)
            recipient_ids = data.get("params", {}).get("recipient_ids")

            if not isinstance(recipient_ids, list):
                return {"error": "The param recipient_ids has to be a list."}

            ebill_service = _get_ebill_service()
            results = ebill_service.get_ebill_recipient_subscription_status_bulk(
                recipient_ids
            )

            bill_recipients_obj = (
                results.BillRecipients if hasattr(results, "BillRecipients") else None
            )
            received_recipients = (
                bill_recipients_obj.BillRecipient
                if (
                    bill_recipients_obj
                    and hasattr(bill_recipients_obj, "BillRecipient")
                )
                else []
            )

            allowed_recipients = [
                r
                for r in received_recipients
                if getattr(r, "SubmissionStatus", None) == "ALLOWED"
            ]

            created, errors = [], []

            for recipient in allowed_recipients:
                ebill_recipient_info = {
                    "email": recipient.EmailAddress,
                    "ebill_account_id": recipient.EbillAccountID,
                }

                try:
                    partner, contract = ebill_service._ensure_partner_and_contract(
                        ebill_recipient_info, ebill_service
                    )
                    created.append(
                        {
                            "partner_id": partner.id,
                            "email": partner.email,
                            "contract_id": contract.id,
                            "EbillAccountID": contract.postfinance_billerid,
                        }
                    )
                except Exception as e:
                    _logger.error(
                        "Create partner/contract failed for email %s: %s",
                        ebill_recipient_info.get("email"),
                        e,
                        exc_info=True,
                    )
                    errors.append(
                        {"email": ebill_recipient_info.get("email"), "error": str(e)}
                    )

            return {
                "summary": {
                    "total_requested": len(recipient_ids),
                    "created": len(created),
                    "errors": len(errors),
                },
                "created": created,
                "errors": errors,
            }

        except Exception as e:
            if "Missing element SubmissionStatus" in str(e):
                _logger.warning(
                    "No ebill recipient found for the given IDs (service raised exception)."
                )
                return {
                    "error": "No ebill recipient was found for the provided recipient_ids."
                }
            else:
                _logger.error(
                    f"Unexpected Exception during bulk search occurred: {e}",
                    exc_info=True,
                )
                return {"error": "An internal server error occurred."}

    @http.route(
        "/ebill/subscribe",
        type="http",
        auth="public",
        website=True,
        methods=["GET", "POST"],
        sitemap=False,
        csrf=False,
    )
    def subscribe(self, is_integrated=False, **kw):
        email = kw.get("email")

        if not email:
            return _render_view(
                is_integrated,
                "ebill_postfinance_recipient_subscription.subscribe_template",
            )

        normalized_email = email_normalize(email)
        if not normalized_email:
            return _render_view(
                is_integrated,
                "ebill_postfinance_recipient_subscription.subscribe_template",
                {"submitted_email": email},
            )

        try:
            ebill_service = _get_ebill_service()
            token_sub = ebill_service.initiate_ebill_recipient_subscription(email)

            return _render_view(
                is_integrated,
                "ebill_postfinance_recipient_subscription.validate_template",
                {
                    "token": token_sub.SubscriptionInitiationToken,
                    "email": email,
                },
            )

        except Exception:
            _logger.warning(
                f"Failed to initiate eBill subscription for email '{email}'.",
                exc_info=True,
            )
            return _render_view(
                is_integrated,
                "ebill_postfinance_recipient_subscription.subscribe_template",
                {"submitted_email": email},
            )

    @http.route(
        "/ebill/validate",
        type="http",
        auth="public",
        website=True,
        methods=["POST"],
        sitemap=False,
        csrf=False,
    )
    def validate(self, is_integrated=False, **post):
        email = post.get("email")

        normalized_email = email_normalize(email)
        if not normalized_email:
            return _render_view(
                is_integrated,
                "ebill_postfinance_recipient_subscription.subscribe_template",
                {"submitted_email": email},
            )

        try:
            ebill_service = _get_ebill_service()
            token_sub = ebill_service.initiate_ebill_recipient_subscription(email)

            return _render_view(
                is_integrated,
                "ebill_postfinance_recipient_subscription.validate_template",
                {
                    "token": token_sub.SubscriptionInitiationToken,
                    "email": email,
                },
            )

        except Exception as e:
            _logger.error(
                f"Error during the eBill confirmation process for mail '{email}': {e}",
                exc_info=True,
            )

            return _render_view(
                is_integrated,
                "ebill_postfinance_recipient_subscription.retry_template",
                {
                    "email": email,
                },
            )

    @http.route(
        "/ebill/confirm",
        type="http",
        auth="public",
        website=True,
        methods=["POST"],
        sitemap=False,
        csrf=False,
    )
    def confirm(self, is_integrated=False, **post):
        token = post.get("token")
        activation_code = post.get("validation_code")
        email = post.get("email")
        ebill_service = _get_ebill_service()

        try:
            partner_data = ebill_service.confirm_ebill_recipient_subscription(
                token, activation_code
            )

            if not (partner_data and partner_data.EbillAccountID):
                _logger.warning(
                    f"eBill validation failed for token '{token}' (e.g., incorrect code)."
                )

                return _render_view(
                    is_integrated,
                    "ebill_postfinance_recipient_subscription.validate_template",
                    {
                        "error": (
                            "Validation failed. Please verify the code or check "
                            "if an eBill connection is possible with this email."
                        ),
                        "token": token,
                        "email": email,
                    },
                )

            party = getattr(partner_data, "Party", None)
            partner_address = getattr(party, "Address", None)
            name = (partner_data.EmailAddress or "").split("@", 1)[0]  # Fallback-Name

            if partner_address:
                name = " ".join(
                    filter(
                        None,
                        [
                            (partner_address.GivenName or "").strip(),
                            (partner_address.FamilyName or "").strip(),
                        ],
                    )
                )

            ebill_recipient_info = {
                "email": partner_data.EmailAddress,
                "ebill_account_id": partner_data.EbillAccountID,
                "name": name,
                "street": partner_address.Address1 if partner_address else None,
                "zip": partner_address.ZIP if partner_address else None,
                "city": partner_address.City if partner_address else None,
            }

            ebill_service._ensure_partner_and_contract(
                ebill_recipient_info, ebill_service
            )

            return _render_view(
                is_integrated,
                "ebill_postfinance_recipient_subscription.success_template",
            )

        except Exception as e:
            _logger.warning(
                "Exception during confirmation, likely "
                "a wrong activation code for token '%s': %s",
                token,
                e,
                exc_info=True,
            )

            return _render_view(
                is_integrated,
                "ebill_postfinance_recipient_subscription.validate_template",
                {
                    "error": (
                        "Validation failed. Please verify the code or check "
                        "if an eBill connection is possible with this email."
                    ),
                    "token": token,
                    "email": email,
                },
            )

    @http.route(
        "/ebill/current-user/contract",
        type="json",
        auth="user",
        csrf=False,
        methods=["POST"],
        sitemap=False,
    )
    def ebill_me_contract(self, **kw):
        try:
            user = request.env.user
            partner = user.sudo().partner_id

            if not partner or partner == request.env.ref(
                "base.public_partner", raise_if_not_found=False
            ):
                return {"has_contract": False, "contract": None}

            ebill_service = _get_ebill_service()
            transmit_method = ebill_service._get_ebill_transmit_method()
            active_states = ["draft", "open", "cancel"]
            extra_domain = [("state", "in", active_states)]
            contract = partner.sudo().get_active_contract(
                transmit_method, domain=extra_domain
            )

            if not contract:
                return {
                    "has_contract": False,
                    "contract": None,
                    "partner": {
                        "id": partner.id,
                        "name": partner.name,
                        "email": partner.email,
                    },
                }

            return {
                "has_contract": True,
                "partner": {
                    "id": partner.id,
                    "name": partner.name,
                    "email": partner.email,
                },
                "contract": {
                    "id": contract.id,
                    "state": contract.state,
                    "transmit_method": transmit_method.name,
                    "postfinance_billerid": contract.postfinance_billerid or None,
                    "service_id": contract.postfinance_service_id.id
                    if contract.postfinance_service_id
                    else None,
                },
            }
        except Exception as e:
            _logger.error("Error in /ebill/current-user/contract: %s", e, exc_info=True)
            return {"error": "Could not check eBill contract for current user."}
