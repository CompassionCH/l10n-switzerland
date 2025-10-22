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


def _get_ebill_transmit_method():
    return (
        request.env["transmit.method"]
        .sudo()
        .search([("code", "=", "postfinance")], limit=1)
    )


def _render_view(is_integrated, template_xml_id, values={}):
    if is_integrated:
        values["is_integrated"] = is_integrated
        return request.env["ir.ui.view"]._render_template(template_xml_id, values)
    else:
        return request.render(template_xml_id, values)


def _ensure_partner_and_contract(ebill_recipient_info, ebill_service):
    email = (ebill_recipient_info.get("email") or "").strip() or None
    ebill_account_id = (
        ebill_recipient_info.get("ebill_account_id") or ""
    ).strip() or None
    name = ebill_recipient_info.get("name")
    street = (ebill_recipient_info.get("street") or "").strip() or None
    zip = (ebill_recipient_info.get("zip") or "").strip() or None
    city = (ebill_recipient_info.get("city") or "").strip() or None

    if not email or not ebill_account_id:
        raise ValueError("email and ebill_account_id is required")

    Partner = request.env["res.partner"].sudo()
    Contract = request.env["ebill.payment.contract"].sudo()

    partner = Partner.search([("email", "=", email)], limit=1)
    if not partner:
        vals = {"name": name, "email": email}
        if street:
            vals["street"] = street
        if zip:
            vals["zip"] = zip
        if city:
            vals["city"] = city
        partner = Partner.create(vals)

    transmit_method = _get_ebill_transmit_method()

    contract = Contract.search(
        [
            ("partner_id", "=", partner.id),
            ("postfinance_billerid", "=", ebill_account_id),
            ("postfinance_service_id", "=", ebill_service.id),
            ("state", "=", "open"),
        ],
        limit=1,
    )

    if not contract:
        contract = Contract.create(
            {
                "partner_id": partner.id,
                "transmit_method_id": transmit_method.id,
                "state": "open",
                "postfinance_service_id": ebill_service.id,
                "postfinance_billerid": ebill_account_id,
            }
        )

    return partner, contract


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

            received_recipients = (
                getattr(getattr(results, "BillRecipients", None), "BillRecipient", [])
                or []
            )
            allowed_recipients = [
                r
                for r in received_recipients
                if getattr(r, "SubmissionStatus", None) == "ALLOWED"
            ]

            created, errors = [], []

            for recipient in allowed_recipients:
                ebill_recipient_info = {
                    "email": getattr(recipient, "EmailAddress"),
                    "ebill_account_id": getattr(recipient, "EbillAccountID"),
                }

                try:
                    partner, contract = _ensure_partner_and_contract(
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
                        f"Create partner/contract failed for email {ebill_recipient_info.get('email')}: {e}",
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

            if not (partner_data and partner_data.get("eBillAccountID")):
                _logger.warning(
                    f"eBill validation failed for token '{token}' (e.g., incorrect code)."
                )

                return _render_view(
                    is_integrated,
                    "ebill_postfinance_recipient_subscription.validate_template",
                    {
                        "error": "Validation failed. Please verify the code or check if an eBill connection is possible with this email.",
                        "token": token,
                        "email": email,
                    },
                )

            partner_address = partner_data.get("Party", {}).get("Address", {})
            name = (
                " ".join(
                    filter(
                        None,
                        [
                            (partner_address.get("GivenName") or "").strip(),
                            (partner_address.get("LastName") or "").strip(),
                        ],
                    )
                )
                or (partner_data.get("eMailAddress") or "").split("@", 1)[0]
            )

            ebill_recipient_info = {
                "email": partner_data.get("eMailAddress"),
                "ebill_account_id": partner_data.get("eBillAccountID"),
                "name": name,
                "street": partner_address.get("Address1"),
                "zip": partner_address.get("ZIP"),
                "city": partner_address.get("City"),
            }

            _ensure_partner_and_contract(ebill_recipient_info, ebill_service)

            return _render_view(
                is_integrated,
                "ebill_postfinance_recipient_subscription.success_template",
            )

        except Exception as e:
            _logger.warning(
                f"Exception during confirmation, likely a wrong activation code for token '{token}': {e}",
                exc_info=True,
            )

            return _render_view(
                is_integrated,
                "ebill_postfinance_recipient_subscription.validate_template",
                {
                    "error": "Validation failed. Please verify the code or check if an eBill connection is possible with this email.",
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

            transmit_method = _get_ebill_transmit_method()
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
