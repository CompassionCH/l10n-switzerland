from odoo import models, api
import logging

_logger = logging.getLogger(__name__)


class Partner(models.Model):
    _inherit = "res.partner"

    def _lookup_ebill_contract(self):
        self.ensure_one()

        ebill_service = self.env["ebill.postfinance.service"]._get_ebill_service_instance()

        if not self.email:
            _logger.info("Partner %s has no email for eBill lookup.", self.id)
            return None

        try:
            recipient_ids = [self.email]
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

            allowed_recipient = next(
                (
                    r for r in received_recipients
                    if getattr(r, "SubmissionStatus", None) == "ALLOWED"
                       and r.EmailAddress.lower() == self.email.lower()
                ),
                None,
            )

            if not allowed_recipient:
                _logger.info(
                    "No 'ALLOWED' eBill subscription found for partner %s (email: %s).",
                    self.id, self.email
                )
                return None

            ebill_recipient_info = {
                "partner_id": self.id,
               "ebill_account_id": allowed_recipient.EbillAccountID,
            }

            partner, contract  = ebill_service._ensure_partner_and_contract(ebill_recipient_info, ebill_service)

            _logger.info(
                "eBill-Subscription für Partner %s gefunden. "
                "Gebe Infos an Controller zurück...", self.id
            )
            return contract

        except Exception as e:
            if "Missing element SubmissionStatus" in str(e):
                _logger.warning(
                    "No ebill recipient found for the given IDs (service raised exception)."
                )
                return None
            else:
                _logger.error(
                    f"Unexpected Exception during bulk search occurred: {e}",
                    exc_info=True,
                )
            return None
