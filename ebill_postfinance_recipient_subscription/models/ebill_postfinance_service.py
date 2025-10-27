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



    def _cron_process_registration_protocols(self):
        """
        Cron job method to fetch and process eBill registration protocol files
        from PostFinance.

        This method:
        1. Fetches the list of available registration protocol files.
        2. Downloads each file.
        3. Parses the file as a CSV.
        4. For each line:
            - If SUBSCRIPTIONTYPE is '1' (New):
                - Finds a partner by email.
                - If exactly one partner is found, creates a new ebill.payment.contract.
                - Logs warnings for manual processing if zero or multiple partners are found.
            - If SUBSCRIPTIONTYPE is not '1' (Deregistration):
                - Finds the corresponding contract by RECIPIENTID.
                - Sets the contract state to 'cancel' and adds an end date.
        """
        _logger.info("Starting eBill registration protocol cron job...")

        # Find the eBill service based on system parameters
        biller_id = self.env["ir.config_parameter"].sudo().get_param("ebill_postfinance.biller_id")
        ebill_service = self.env["ebill.postfinance.service"].sudo().search(
            [("biller_id", "=", biller_id)], limit=1
        )

        if not ebill_service:
            _logger.error("eBill registration cron: No eBill service found for biller_id %s. Cron job aborted.",
                          biller_id)
            return

        partner_obj = self.env["res.partner"].sudo()
        contract_obj = self.env["ebill.payment.contract"].sudo()
        transmit_method = self.env["transmit.method"].sudo().search(
            [("code", "=", "postfinance")], limit=1
        )

        if not transmit_method:
            _logger.error("eBill registration cron: Transmit method 'postfinance' not found. Cron job aborted.")
            return

        # Get list of protocol files
        try:
            registration_lists = ebill_service.get_registration_protocol_list()
        except Exception as e:
            _logger.error("eBill registration cron: Failed to get registration protocol list: %s", e, exc_info=True)
            return

        _logger.info("Found %s registration protocol list(s) to process.", len(registration_lists))

        for registration_list in registration_lists:
            _logger.info("Processing registration list from %s", registration_list.CreateDate)
            try:
                files = ebill_service.get_registration_protocol(registration_list.CreateDate)
            except Exception as e:
                _logger.error(
                    "eBill registration cron: Failed to get protocol file for date %s: %s",
                    registration_list.CreateDate, e, exc_info=True
                )
                continue  # Skip to the next list

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
                                # --- Create new contract ---
                                if not email:
                                    _logger.warning(
                                        "Skipping subscription in %s: No EMAIL found for RECIPIENTID %s. Line: %s",
                                        file.Filename, recipient_id, line
                                    )
                                    continue

                                partners = partner_obj.search([("email", "=", email)])

                                if len(partners) == 1:
                                    partner = partners
                                    # Check for existing active contract to avoid duplicates
                                    existing_contract = contract_obj.search([
                                        ("partner_id", "=", partner.id),
                                        ("postfinance_billerid", "=", recipient_id),
                                        ("postfinance_service_id", "=", ebill_service.id),
                                        ("state", "=", "open"),
                                    ], limit=1)

                                    if existing_contract:
                                        _logger.info(
                                            "eBill contract already exists and is open for partner %s (ID: %s) and recipient ID %s. Skipping creation.",
                                            partner.email, partner.id, recipient_id
                                        )
                                        continue

                                    contract_vals = {
                                        "partner_id": partner.id,
                                        "state": "open",
                                        "date_start": datetime.date.today(),
                                        "transmit_method_id": transmit_method.id,
                                        "postfinance_billerid": recipient_id,
                                        "payment_type": "qr",  # As per your pseudo-code
                                        "postfinance_service_id": ebill_service.id
                                    }
                                    contract_obj.create(contract_vals)
                                    _logger.info(
                                        "Created eBill contract for partner %s (ID: %s) with recipient ID %s.",
                                        partner.email, partner.id, recipient_id
                                    )

                                elif len(partners) == 0:
                                    _logger.warning(
                                        "eBill registration cron: No partner found for email %s (RecipientID: %s). Manual processing required.",
                                        email, recipient_id
                                    )

                                else:  # len(partners) > 1
                                    _logger.warning(
                                        "eBill registration cron: Multiple partners (%s) found for email %s (RecipientID: %s). Manual processing required.",
                                        len(partners), email, recipient_id
                                    )

                            else:
                                # --- End of contract ---
                                _logger.info(
                                    "Processing end of contract for RecipientID %s (Type: %s)",
                                    recipient_id, subscription_type
                                )
                                # Find all open contracts matching the unique eBill RecipientID
                                contracts_to_close = contract_obj.search([
                                    ("postfinance_billerid", "=", recipient_id),
                                    ("postfinance_service_id", "=", ebill_service.id),
                                    ("state", "=", "open"),
                                ])

                                if not contracts_to_close:
                                    _logger.warning(
                                        "eBill deregistration: No active contract found for RecipientID %s. No action taken.",
                                        recipient_id
                                    )
                                    continue

                                for contract in contracts_to_close:
                                    contract.write({
                                        "state": "cancel",  # Or 'closed' if that state exists
                                        "date_end": datetime.date.today()
                                    })
                                    _logger.info(
                                        "Closed eBill contract ID %s for partner %s (RecipientID: %s).",
                                        contract.id, contract.partner_id.name, recipient_id
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
