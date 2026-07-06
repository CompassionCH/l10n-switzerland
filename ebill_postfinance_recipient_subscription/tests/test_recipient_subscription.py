# Copyright 2026 Compassion CH (Noé Berdoz)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import re
from datetime import date
from types import SimpleNamespace
from unittest import mock

from odoo.tests.common import HttpCase, TransactionCase, tagged
from odoo.tools import mute_logger

from odoo.addons.ebill_postfinance.models.ebill_postfinance_service import (
    EbillPostfinanceService as BaseService,
)

CSV_HEADER = "SUBSCRIPTIONTYPE;EMAIL;RECIPIENTID;GIVENNAME;FAMILYNAME;ADDRESS;ZIP;CITY"
CONTRACT_LOGGER = "odoo.addons.base_ebill_payment_contract.models.res_partner"
SERVICE_LOGGER = (
    "odoo.addons.ebill_postfinance_recipient_subscription.models"
    ".ebill_postfinance_service"
)


def protocol_file(name, rows):
    data = "\n".join([CSV_HEADER, *rows]).encode("utf-8")
    return SimpleNamespace(Filename=name, Data=data)


def bulk_response(recipients):
    return SimpleNamespace(BillRecipients=SimpleNamespace(BillRecipient=recipients))


class RecipientSubscriptionCommon(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.service = cls.env["ebill.postfinance.service"].create(
            {
                "name": "PF test service",
                "use_test_service": True,
                "biller_id": "41100000000000000",
                "username": "user",
                "password": "pwd",
            }
        )
        cls.env["ir.config_parameter"].sudo().set_param(
            "ebill_postfinance.biller_id", cls.service.biller_id
        )
        cls.transmit_method = cls.env["transmit.method"].search(
            [("code", "=", "postfinance")], limit=1
        )


class TestEnsurePartnerAndContract(RecipientSubscriptionCommon):
    @mute_logger(CONTRACT_LOGGER)
    def test_creates_partner_and_contract(self):
        partner, contract = self.service._ensure_partner_and_contract(
            {
                "email": "new.donor@example.com",
                "ebill_account_id": "EB-NEW",
                "name": "New Donor",
                "street": "Teststrasse 1",
                "zip": "1700",
                "city": "Fribourg",
            }
        )
        self.assertEqual(partner.name, "New Donor")
        self.assertEqual(partner.email, "new.donor@example.com")
        self.assertEqual(partner.city, "Fribourg")
        self.assertEqual(contract.state, "open")
        self.assertEqual(contract.postfinance_billerid, "EB-NEW")
        self.assertEqual(contract.postfinance_service_id, self.service)
        self.assertEqual(contract.transmit_method_id, self.transmit_method)

    @mute_logger(CONTRACT_LOGGER)
    def test_is_idempotent(self):
        info = {
            "email": "repeat@example.com",
            "ebill_account_id": "EB-REPEAT",
            "name": "Repeat Donor",
        }
        partner1, contract1 = self.service._ensure_partner_and_contract(info)
        partner2, contract2 = self.service._ensure_partner_and_contract(info)
        self.assertEqual(partner1, partner2)
        self.assertEqual(contract1, contract2)

    def test_requires_identifier_and_account(self):
        with self.assertRaises(ValueError):
            self.service._ensure_partner_and_contract({"email": "x@example.com"})
        with self.assertRaises(ValueError):
            self.service._ensure_partner_and_contract({"ebill_account_id": "EB-X"})

    @mute_logger(CONTRACT_LOGGER)
    def test_cancel_contract_by_recipient(self):
        _, contract = self.service._ensure_partner_and_contract(
            {
                "email": "leaver@example.com",
                "ebill_account_id": "EB-LEAVER",
                "name": "Leaver",
            }
        )
        today = date.today()
        self.service._cancel_contract_by_recipient("EB-LEAVER")
        self.assertEqual(contract.state, "cancel")
        self.assertEqual(contract.date_end, today)
        # unknown recipient: logs a warning, must not raise
        self.service._cancel_contract_by_recipient("EB-UNKNOWN")


class TestRegistrationProtocolCron(RecipientSubscriptionCommon):
    @mute_logger(CONTRACT_LOGGER)
    def test_processes_files_and_skips_empty_ones(self):
        _, contract = self.service._ensure_partner_and_contract(
            {
                "email": "leaver@example.com",
                "ebill_account_id": "EB-LEAVER",
                "name": "Leaver",
            }
        )
        registration = SimpleNamespace(CreateDate="2026-07-01", FileType="csv")
        good_file = protocol_file(
            "reg.csv",
            [
                "1;joiner@example.com;EB-JOINER;Jane;Doe;Mainstreet 5;1700;Fribourg",
                "1;noid@example.com;;X;Y;;;",
                "3;;EB-LEAVER;;;;;",
            ],
        )
        empty_file = SimpleNamespace(Filename="empty.csv", Data=None)
        fake = mock.Mock()
        fake.get_registration_protocol_list.return_value = [registration]
        fake.get_registration_protocol.return_value = [empty_file, good_file]
        with mock.patch.object(BaseService, "_get_service", return_value=fake):
            self.env["ebill.postfinance.service"]._cron_process_registration_protocols()
        joiner = self.env["res.partner"].search([("email", "=", "joiner@example.com")])
        self.assertEqual(len(joiner), 1)
        self.assertEqual(joiner.name, "Jane Doe")
        joiner_contract = self.env["ebill.payment.contract"].search(
            [("postfinance_billerid", "=", "EB-JOINER")]
        )
        self.assertEqual(joiner_contract.state, "open")
        # the type-3 line cancelled the pre-existing contract
        self.assertEqual(contract.state, "cancel")
        # the row without RECIPIENTID created nothing
        self.assertFalse(
            self.env["res.partner"].search([("email", "=", "noid@example.com")])
        )

    def test_returns_cleanly_without_service(self):
        self.env["ir.config_parameter"].sudo().set_param(
            "ebill_postfinance.biller_id", "NO-MATCH"
        )
        partners_before = self.env["res.partner"].search_count([])
        with mock.patch.object(BaseService, "_get_service") as get_service:
            with self.assertLogs(SERVICE_LOGGER, level="ERROR"):
                self.env[
                    "ebill.postfinance.service"
                ]._cron_process_registration_protocols()
        get_service.assert_not_called()
        self.assertEqual(self.env["res.partner"].search_count([]), partners_before)


class TestLookupEbillContract(RecipientSubscriptionCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create(
            {"name": "Known Donor", "email": "known@example.com"}
        )

    @mute_logger(CONTRACT_LOGGER)
    def test_allowed_recipient_yields_contract(self):
        fake = mock.Mock()
        fake.get_ebill_recipient_subscription_status_bulk.return_value = bulk_response(
            [
                SimpleNamespace(
                    SubmissionStatus="ALLOWED",
                    EmailAddress="KNOWN@example.com",
                    EbillAccountID="EB-KNOWN",
                )
            ]
        )
        with mock.patch.object(BaseService, "_get_service", return_value=fake):
            contract = self.partner._lookup_ebill_contract()
        self.assertTrue(contract)
        self.assertEqual(contract.state, "open")
        self.assertEqual(contract.partner_id, self.partner)
        self.assertEqual(contract.postfinance_billerid, "EB-KNOWN")

    @mute_logger(CONTRACT_LOGGER)
    def test_recipient_without_email_attribute_is_skipped(self):
        # the entry without EmailAddress comes FIRST: without the getattr
        # guard it raises inside the generator and no contract is ever found
        fake = mock.Mock()
        fake.get_ebill_recipient_subscription_status_bulk.return_value = bulk_response(
            [
                SimpleNamespace(SubmissionStatus="ALLOWED", EbillAccountID="EB-NOMAIL"),
                SimpleNamespace(
                    SubmissionStatus="ALLOWED",
                    EmailAddress="known@example.com",
                    EbillAccountID="EB-KNOWN2",
                ),
            ]
        )
        with mock.patch.object(BaseService, "_get_service", return_value=fake):
            contract = self.partner._lookup_ebill_contract()
        self.assertTrue(contract)
        self.assertEqual(contract.postfinance_billerid, "EB-KNOWN2")

    def test_no_service_returns_none(self):
        self.env["ir.config_parameter"].sudo().set_param(
            "ebill_postfinance.biller_id", "NO-MATCH"
        )
        with mock.patch.object(BaseService, "_get_service") as get_service:
            result = self.partner._lookup_ebill_contract()
        get_service.assert_not_called()
        self.assertIsNone(result)

    def test_no_email_returns_none(self):
        partner = self.env["res.partner"].create({"name": "No Mail"})
        self.assertIsNone(partner._lookup_ebill_contract())


@tagged("post_install", "-at_install")
class TestSubscriptionWorkflowHttp(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.service = cls.env["ebill.postfinance.service"].create(
            {
                "name": "PF test service",
                "use_test_service": True,
                "biller_id": "41100000000000000",
                "username": "user",
                "password": "pwd",
            }
        )
        cls.env["ir.config_parameter"].sudo().set_param(
            "ebill_postfinance.biller_id", cls.service.biller_id
        )

    def test_subscribe_renders_full_page_and_bare_fragment(self):
        page = self.url_open("/ebill/subscribe")
        self.assertEqual(page.status_code, 200)
        self.assertIn('id="email_input"', page.text)
        self.assertIn("</html>", page.text)
        fragment = self.url_open("/ebill/subscribe?is_integrated=1")
        self.assertEqual(fragment.status_code, 200)
        self.assertIn('id="email_input"', fragment.text)
        self.assertNotIn("</html>", fragment.text)

    @mute_logger(CONTRACT_LOGGER)
    def test_confirm_falls_back_to_email_local_part_for_blank_names(self):
        page = self.url_open("/ebill/subscribe")
        csrf = re.search(r'name="csrf_token" value="([^"]+)"', page.text).group(1)
        partner_data = SimpleNamespace(
            EbillAccountID="EB-FALLBACK",
            EmailAddress="fallback.user@example.com",
            Party=SimpleNamespace(
                Address=SimpleNamespace(
                    GivenName="  ",
                    FamilyName="",
                    Address1=None,
                    ZIP=None,
                    City=None,
                )
            ),
        )
        fake = mock.Mock()
        fake.confirm_ebill_recipient_subscription.return_value = partner_data
        with mock.patch.object(BaseService, "_get_service", return_value=fake):
            response = self.url_open(
                "/ebill/validate",
                data={
                    "csrf_token": csrf,
                    "token": "tok-123",
                    "validation_code": "123456",
                    "email": "fallback.user@example.com",
                    "is_integrated": "1",
                },
            )
        self.assertEqual(response.status_code, 200)
        self.assertIn("ebill-success-marker", response.text)
        partner = self.env["res.partner"].search(
            [("email", "=", "fallback.user@example.com")]
        )
        self.assertEqual(len(partner), 1)
        self.assertEqual(partner.name, "fallback.user")
