# Copyright 2022 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging.config
import csv
import io
import datetime

from odoo import models

_logger = logging.getLogger(__name__)


class EbillPostfinanceService(models.Model):
    _inherit = "ebill.postfinance.service"

    def get_ebill_recipient_subscription_status_bulk(self, bill_recipient_id):
        service = self._get_service()
        res = service.get_ebill_recipient_subscription_status_bulk(bill_recipient_id)
        return res

    def initiate_ebill_recipient_subscription(self, recipient_email):
        service = self._get_service()
        res = service.initiate_ebill_recipient_subscription(recipient_email)
        return res

    def confirm_ebill_recipient_subscription(self, initiation_token, activation_code):
        service = self._get_service()
        res = service.confirm_ebill_recipient_subscription(
            initiation_token, activation_code
        )
        return res

    def _get_ebill_service_instance(self):
        biller_id = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("ebill_postfinance.biller_id")
        )
        return (
            self.env["ebill.postfinance.service"]
            .sudo()
            .search([("biller_id", "=", biller_id)], limit=1)
        )

    def _get_ebill_transmit_method(self):
        return (
            self.env["transmit.method"]
            .sudo()
            .search([("code", "=", "postfinance")], limit=1)
        )

    def _ensure_partner_and_contract(self, ebill_recipient_info, ebill_service):
        email = (ebill_recipient_info.get("email") or "").strip() or None
        ebill_account_id = (
                            ebill_recipient_info.get("ebill_account_id") or ""
                           ).strip() or None
        name = ebill_recipient_info.get("name")
        street = (ebill_recipient_info.get("street") or "").strip() or None
        zip_code = (ebill_recipient_info.get("zip") or "").strip() or None
        city = (ebill_recipient_info.get("city") or "").strip() or None

        if not email or not ebill_account_id:
            raise ValueError("email and ebill_account_id is required")

        Partner = self.env["res.partner"].sudo()
        Contract = self.env["ebill.payment.contract"].sudo()

        partner = Partner.search([("email", "=", email)], limit=1)
        if not partner:
            vals = {"name": name, "email": email}
            if street:
                vals["street"] = street
            if zip_code:
                vals["zip"] = zip_code
            if city:
                vals["city"] = city
            partner = Partner.create(vals)

        transmit_method = self._get_ebill_transmit_method()

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

    def _cron_process_registration_protocols(self):
        _logger.info("Starting eBill registration protocol cron job...")

        ebill_service = self._get_ebill_service_instance()

        if not ebill_service:
            _logger.error("eBill registration cron: No eBill service found. Cron job aborted.")
            return

        try:
            registration_lists = ebill_service.get_registration_protocol_list()
        except Exception as e:
            _logger.error("eBill registration cron: Failed to get registration protocol list: %s", e, exc_info=True)
            return

        if not registration_lists:
            registration_lists = []

        _logger.info("Found %s registration protocol list(s) to process.", len(registration_lists))

        for registration_list in registration_lists:
            _logger.info("Processing registration list from %s", registration_list.CreateDate)
            try:
                files = ebill_service.get_registration_protocol_list(registration_list.CreateDate)
            except Exception as e:
                _logger.error(
                    "eBill registration cron: Failed to get protocol file for date %s: %s",
                    registration_list.CreateDate, e, exc_info=True
                )
                continue

            for file in files:
                _logger.info("Processing file: %s", file.Filename)
                try:
                    data_bytes = file.Data
                    # Decode using utf-8, as examples show special characters
                    decoded_data = data_bytes.decode('utf-8')
                    data_file = io.StringIO(decoded_data)
                    csv_reader = csv.DictReader(data_file, delimiter=';')

                    for line in csv_reader:
                        try:
                            subscription_type = line.get("SUBSCRIPTIONTYPE", "").strip()
                            email = line.get("EMAIL", "").strip()
                            recipient_id = line.get("RECIPIENTID", "").strip()

                            if not recipient_id:
                                _logger.warning(
                                    "Skipping line in %s: No RECIPIENTID found. Line: %s",
                                    file.Filename, line
                                )
                                continue

                            if subscription_type == "1":

                                ebill_recipient_info = {
                                    "email": email,
                                    "ebill_account_id": recipient_id,
                                    "name": " ".join(filter(None, [
                                        line.get("GIVENNAME", "").strip(),
                                        line.get("FAMILYNAME", "").strip(),
                                        line.get("COMPANYNAME", "").strip(),
                                    ])),
                                    "street": line.get("ADDRESS", "").strip(),
                                    "zip": line.get("ZIP", "").strip(),
                                    "city": line.get("CITY", "").strip(),
                                }

                                try:
                                    partner, contract = self._ensure_partner_and_contract(ebill_recipient_info, ebill_service)

                                    _logger.info(
                                        "Cron: Ensured contract (ID: %s) for partner %s (ID: %s) with EbillAccountID %s.",
                                        contract.id, partner.email, partner.id, contract.postfinance_billerid
                                    )
                                except Exception as e_ensure:
                                    _logger.warning(
                                        "Cron: Failed to ensure partner/contract for email %s (RecipientID: %s). Error: %s",
                                        email, recipient_id, e_ensure
                                    )

                            else:
                                # --- End of contract ---
                                _logger.info(
                                    "Processing end of contract for RecipientID %s (Type: %s)",
                                    recipient_id, subscription_type
                                )

                        except Exception as e_line:
                            _logger.error(
                                "eBill registration cron: Failed to process line in %s: %s. Error: %s",
                                file.Filename, line, e_line, exc_info=True
                            )

                except Exception as e_file:
                    _logger.error(
                        "eBill registration cron: Failed to read or decode file %s: %s",
                        file.Filename, e_file, exc_info=True
                    )
        _logger.info("Finished eBill registration protocol cron job.")
