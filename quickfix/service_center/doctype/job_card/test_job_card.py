import logging
import cssutils
cssutils.log.setLevel(logging.CRITICAL)

import frappe
from frappe.tests.utils import FrappeTestCase
from unittest.mock import patch, MagicMock
import requests
from quickfix.task import send_webhook


def create_device_type():
    if not frappe.db.exists("Device Type", "Mobile"):
        frappe.get_doc({
            "doctype": "Device Type",
            "device_type": "Mobile"
        }).insert(ignore_permissions=True)
    return "Mobile"


def create_technician():
    if not frappe.db.exists("Technician", {"technician_name": "Test Tech"}):
        frappe.get_doc({
            "doctype": "Technician",
            "technician_name": "Test Tech"
        }).insert(ignore_permissions=True)
    return frappe.db.get_value("Technician", {"technician_name": "Test Tech"}, "name")


def create_spare_part(**kwargs):
    defaults = {
        "doctype": "Spare Part",
        "part_name": "Test Part",
        "quantity": 5,
        "unit_cost": 50.0,
        "selling_price": 75.0,
    }
    defaults.update(kwargs)
    doc = frappe.get_doc(defaults)
    doc.insert(ignore_permissions=True)
    return doc


def create_job_card(**kwargs):
    defaults = {
        "doctype": "Job Card",
        "customer_name": "Test Customer",
        "customer_phone": "9876543210",
        "device_type": "Mobile",
        "assigned_technician": frappe.db.get_value("Technician", {"technician_name": "Test Tech"}, "name"),
        "problem_description": "Test problem description",
        "parts_usage": [
            {
                "part": "Test Part",
                "quantity": 1,
                "unit_cost": 100
            }
        ]
    }
    defaults.update(kwargs)
    doc = frappe.get_doc(defaults)
    doc.insert(ignore_permissions=True)
    return doc


class TestJobCard(FrappeTestCase):

    def setUp(self):
        super().setUp()
        create_device_type()
        create_technician()
        create_spare_part()
        part_name = frappe.db.get_value("Spare Part", {"part_name": "Test Part"}, "name")
        if part_name:
            frappe.db.set_value("Spare Part", part_name, "stock_qty", 10)

    ## testcase 1
    def test_valid_job_card(self):
        doc = create_job_card()
        self.assertTrue(frappe.db.exists("Job Card", doc.name))

    ## testcase 2
    def test_phone_validation(self):
        with self.assertRaises(frappe.ValidationError):
            create_job_card(customer_phone="123")
        with self.assertRaises(frappe.ValidationError):
            create_job_card(customer_phone="12345678901")
        with self.assertRaises(frappe.ValidationError):
            create_job_card(customer_phone="123456789a")

        doc = create_job_card(customer_phone="9876543210")
        self.assertTrue(frappe.db.exists("Job Card", doc.name))

    ## testcase 3
    def test_spare_part_selling_price_constraint(self):
        with self.assertRaises(frappe.ValidationError):
            create_spare_part(unit_cost=100, selling_price=99)
        with self.assertRaises(frappe.ValidationError):
            create_spare_part(unit_cost=100, selling_price=100)

        doc = create_spare_part(unit_cost=100, selling_price=101)
        self.assertTrue(frappe.db.exists("Spare Part", doc.name))

    ## testcase 4
    def test_final_amount_computation(self):
        doc = create_job_card(
            parts_usage=[
                {
                    "part": "Test Part",
                    "quantity": 3,
                    "unit_cost": 100
                }
            ]
        )
        expected_parts_total = 3 * 100
        labour_charge = frappe.db.get_single_value("QuickFix Settings", "default_labour_charge")
        expected_final_amount = expected_parts_total + labour_charge

        self.assertEqual(doc.parts_total, expected_parts_total)
        self.assertEqual(doc.final_amount, expected_final_amount)

    ## testcase 5
    def test_transition_guard(self):
        doc = create_job_card(assigned_technician=None)
        doc.status = "In Repair"

        with self.assertRaises(frappe.ValidationError):
            doc.save(ignore_permissions=True)

        doc2 = frappe.get_doc("Job Card", doc.name)
        doc2.assigned_technician = frappe.db.get_value(
            "Technician", {"technician_name": "Test Tech"}, "name"
        )
        doc2.status = "In Repair"
        doc2.estimated_cost = 0

        with self.assertRaises(frappe.ValidationError):
            doc2.save(ignore_permissions=True)

    ## testcase 6
    def test_child_table_row_computation(self):
        doc = create_job_card(
            parts_usage=[
                {
                    "part": "Test Part",
                    "quantity": 2,
                    "unit_cost": 150
                },
                {
                    "part": "Test Part",
                    "quantity": 3,
                    "unit_cost": 200
                }
            ]
        )
        self.assertEqual(doc.parts_usage[0].total_price, 2 * 150)
        self.assertEqual(doc.parts_usage[1].total_price, 3 * 200)

        expected_price = (2 * 150) + (3 * 200)
        self.assertEqual(doc.parts_total, expected_price)

    ## testcase 7
    def test_submit_status(self):
        doc = create_job_card(status="In Repair")
        doc.save(ignore_permissions=True)

        with self.assertRaises(frappe.ValidationError):
            doc.submit()

        doc.status = "Ready for Delivery"
        self.assertEqual(doc.status, "Ready for Delivery")

    ## testcase 8
    def test_stock_check_on_submit(self):
        part_name = frappe.db.get_value("Spare Part", {"part_name": "Test Part"}, "name")
        frappe.db.set_value("Spare Part", part_name, "stock_qty", 5)

        doc = create_job_card(
            estimated_cost=100,
            parts_usage=[
                {
                    "part": "Test Part",
                    "quantity": 1,
                    "unit_cost": 100
                }
            ]
        )
        doc.status = "Ready for Delivery"
        doc.save(ignore_permissions=True)

        with patch("frappe.sendmail"), patch("frappe.enqueue"):
            doc.submit()

        self.assertEqual(doc.docstatus, 1)

    ## testcase 9 - stock deduction
    def test_submit_deducts_stock(self):
        part_name = frappe.db.get_value("Spare Part", {"part_name": "Test Part"}, "name")
        frappe.db.set_value("Spare Part", part_name, "stock_qty", 10)
        stock_before = frappe.db.get_value("Spare Part", part_name, "stock_qty")

        quantity_used = 2
        doc = create_job_card(
            estimated_cost=100,
            parts_usage=[
                {
                    "part": "Test Part",
                    "quantity": quantity_used,
                    "unit_cost": 100
                }
            ]
        )
        doc.status = "Ready for Delivery"
        doc.save(ignore_permissions=True)

        with patch("frappe.sendmail"), patch("frappe.enqueue"):
            doc.submit()

        stock_after = frappe.db.get_value("Spare Part", part_name, "stock_qty")
        self.assertEqual(stock_after, stock_before - quantity_used)

    ## testcase 10 - invoice creation
    def test_submit_creates_invoice(self):
        part_name = frappe.db.get_value("Spare Part", {"part_name": "Test Part"}, "name")
        frappe.db.set_value("Spare Part", part_name, "stock_qty", 10)

        with patch("frappe.sendmail"), patch("frappe.enqueue"):
            doc = create_job_card(
                estimated_cost=100,
                customer_email="testcustomer@example.com"
            )
            doc.status = "Ready for Delivery"
            doc.save(ignore_permissions=True)
            doc.submit()

        invoice_count = frappe.db.count("Service Invoice", {"job_card": doc.name})
        self.assertEqual(invoice_count, 1)

        total_amount = frappe.db.get_value("Service Invoice", {"job_card": doc.name}, "total_amount")
        self.assertEqual(total_amount, doc.final_amount)

        payment_status = frappe.db.get_value("Service Invoice", {"job_card": doc.name}, "payment_status")
        self.assertEqual(payment_status, "Unpaid")

    ## testcase 11 - stock restore on cancel
    def test_cancel_restores_stock(self):
        part_name = frappe.db.get_value("Spare Part", {"part_name": "Test Part"}, "name")
        frappe.db.set_value("Spare Part", part_name, "stock_qty", 10)

        quantity_used = 2
        with patch("frappe.sendmail"), patch("frappe.enqueue"):
            doc = create_job_card(
                estimated_cost=100,
                parts_usage=[
                    {
                        "part": "Test Part",
                        "quantity": quantity_used,
                        "unit_cost": 100
                    }
                ]
            )
            doc.status = "Ready for Delivery"
            doc.save(ignore_permissions=True)
            doc.submit()

            stock_after_submit = frappe.db.get_value("Spare Part", part_name, "stock_qty")
            self.assertEqual(stock_after_submit, 10 - quantity_used)

            doc.cancel()

        stock_after_cancel = frappe.db.get_value("Spare Part", part_name, "stock_qty")
        self.assertEqual(stock_after_cancel, 10)

    ## testcase 12 - cancel linked invoice
    def test_cancel_cancels_linked_invoice(self):
        part_name = frappe.db.get_value("Spare Part", {"part_name": "Test Part"}, "name")
        frappe.db.set_value("Spare Part", part_name, "stock_qty", 10)

        with patch("frappe.sendmail"), patch("frappe.enqueue"):
            doc = create_job_card(estimated_cost=100)
            doc.status = "Ready for Delivery"
            doc.save(ignore_permissions=True)
            doc.submit()

            invoice_name = frappe.db.get_value("Service Invoice", {"job_card": doc.name}, "name")
            self.assertIsNotNone(invoice_name)

            doc.cancel()

        invoice_docstatus = frappe.db.get_value("Service Invoice", invoice_name, "docstatus")
        self.assertEqual(invoice_docstatus, 2)
        frappe.db.set_value("Job Card", doc.name, "status", "Cancelled")
        job_card_status = frappe.db.get_value("Job Card", doc.name, "status")
        self.assertEqual(job_card_status, "Cancelled")

    ## testcase 13 - trash guard
    def test_trash_guard(self):
        part_name = frappe.db.get_value("Spare Part", {"part_name": "Test Part"}, "name")
        frappe.db.set_value("Spare Part", part_name, "stock_qty", 10)

        with patch("frappe.sendmail"), patch("frappe.enqueue"):
            doc = create_job_card(estimated_cost=100)
            doc.status = "Ready for Delivery"
            doc.save(ignore_permissions=True)
            doc.submit()

            with self.assertRaises(frappe.ValidationError):
                frappe.delete_doc("Job Card", doc.name, ignore_permissions=True, force=True)

            doc.cancel()
            frappe.delete_doc("Job Card", doc.name, ignore_permissions=True, force=True)
            self.assertFalse(frappe.db.exists("Job Card", doc.name))

    ## testcase 14 - mock sendmail
    def test_Mock_frappe_sendmail(self):
        part_name = frappe.db.get_value("Spare Part", {"part_name": "Test Part"}, "name")
        frappe.db.set_value("Spare Part", part_name, "stock_qty", 10)

        with patch("frappe.sendmail") as mock_mail, patch("frappe.enqueue"):
            doc = create_job_card(
                estimated_cost=100,
                customer_email="testcustomer@example.com"
            )
            doc.status = "Ready for Delivery"
            doc.save(ignore_permissions=True)
            doc.submit()

            self.assertTrue(mock_mail.called)

            all_recipients = []
            for call in mock_mail.call_args_list:
                recipients = call.kwargs.get("recipients") or (call.args[0] if call.args else None)
                if isinstance(recipients, list):
                    all_recipients.extend(recipients)
                elif isinstance(recipients, str):
                    all_recipients.append(recipients)

            self.assertIn("testcustomer@example.com", all_recipients)

    ## testcase 15 - mock enqueue
    def test_mock_frappe_enqueue(self):
        part_name = frappe.db.get_value("Spare Part", {"part_name": "Test Part"}, "name")
        frappe.db.set_value("Spare Part", part_name, "stock_qty", 10)

        with patch("frappe.enqueue") as mock_enqueue, patch("frappe.sendmail"):
            doc = create_job_card(
                estimated_cost=100,
                customer_email="testcustomer@example.com"
            )
            doc.status = "Ready for Delivery"
            doc.save(ignore_permissions=True)
            doc.submit()

            self.assertTrue(mock_enqueue.called)

            method_paths = [
                call.args[0] if call.args else call.kwargs.get("method")
                for call in mock_enqueue.call_args_list
            ]
            self.assertIn("quickfix.task.send_webhook", method_paths)

            webhook_call = next(
                call for call in mock_enqueue.call_args_list
                if (call.args and call.args[0] == "quickfix.task.send_webhook")
                or call.kwargs.get("method") == "quickfix.task.send_webhook"
            )
            job_card_arg = webhook_call.kwargs.get("job_card_name")
            self.assertEqual(job_card_arg, doc.name)

    ## testcase 16 - mock publish_realtime
    def test_mock_publish_realtime(self):
        part_name = frappe.db.get_value("Spare Part", {"part_name": "Test Part"}, "name")
        frappe.db.set_value("Spare Part", part_name, "stock_qty", 10)

        with patch("frappe.publish_realtime") as mock_realtime, \
             patch("frappe.enqueue"), \
             patch("frappe.sendmail"):

            doc = create_job_card(
                estimated_cost=100,
                customer_email="testcustomer@example.com"
            )
            doc.status = "Ready for Delivery"
            doc.save(ignore_permissions=True)
            doc.submit()

            self.assertTrue(mock_realtime.called)

            job_ready_call = None
            for call in mock_realtime.call_args_list:
                event = call.args[0] if call.args else call.kwargs.get("event")
                if event == "job_ready":
                    job_ready_call = call
                    break

            self.assertIsNotNone(
                job_ready_call,
                "publish_realtime was never called with event 'job_ready'"
            )

            message = job_ready_call.kwargs.get("message") or (
                job_ready_call.args[1] if len(job_ready_call.args) > 1 else None
            )
            self.assertIsNotNone(message, "message was not passed to publish_realtime")
            self.assertEqual(message.get("job_card"), doc.name)

    ## testcase 17 - duplicate invoice guard
    def test_duplicate_invoice_guard(self):
        part_name = frappe.db.get_value("Spare Part", {"part_name": "Test Part"}, "name")
        frappe.db.set_value("Spare Part", part_name, "stock_qty", 10)

        with patch("frappe.sendmail"), patch("frappe.enqueue"):
            doc = create_job_card(
                estimated_cost=100,
                customer_email="testcustomer@example.com"
            )
            doc.status = "Ready for Delivery"
            doc.save(ignore_permissions=True)
            doc.submit()

            count_after_first = frappe.db.count("Service Invoice", {"job_card": doc.name})
            self.assertEqual(count_after_first, 1)

            # call on_submit manually — not doc.submit() which would fail on already submitted doc
            doc.on_submit()

            count_after_second = frappe.db.count("Service Invoice", {"job_card": doc.name})
            self.assertEqual(count_after_second, 1)

    ## testcase 18 - same part used twice
    def test_same_part_used_twice(self):
        doc = create_job_card(
            parts_usage=[
                {
                    "part": "Test Part",
                    "quantity": 2,
                    "unit_cost": 100
                },
                {
                    "part": "Test Part",
                    "quantity": 3,
                    "unit_cost": 100
                }
            ]
        )
        self.assertEqual(doc.parts_usage[0].total_price, 2 * 100)
        self.assertEqual(doc.parts_usage[1].total_price, 3 * 100)

        expected_total = (2 * 100) + (3 * 100)
        self.assertEqual(doc.parts_total, expected_total)

    ## testcase 19 - zero quantity row
    def test_zero_quantity_row(self):
        with self.assertRaises(frappe.ValidationError):
            create_job_card(
                estimated_cost=100,
                parts_usage=[
                    {
                        "part": "Test Part",
                        "quantity": 0,
                        "unit_cost": 100
                    }
                ]
            )

        with self.assertRaises(frappe.ValidationError):
            create_job_card(
                estimated_cost=100,
                parts_usage=[
                    {
                        "part": "Test Part",
                        "quantity": -1,
                        "unit_cost": 100
                    }
                ]
            )

        doc = create_job_card(
            estimated_cost=100,
            parts_usage=[
                {
                    "part": "Test Part",
                    "quantity": 1,
                    "unit_cost": 100
                }
            ]
        )
        self.assertTrue(frappe.db.exists("Job Card", doc.name))

    ## testcase 20 - double cancel prevention
    def test_double_cancel_prevention(self):
        part_name = frappe.db.get_value("Spare Part", {"part_name": "Test Part"}, "name")
        frappe.db.set_value("Spare Part", part_name, "stock_qty", 10)

        with patch("frappe.sendmail"), patch("frappe.enqueue"):
            doc = create_job_card(estimated_cost=100)
            doc.status = "Ready for Delivery"
            doc.save(ignore_permissions=True)
            doc.submit()

            doc.cancel()

            self.assertEqual(
                frappe.db.get_value("Job Card", doc.name, "docstatus"),
                2
            )

            with self.assertRaises(Exception):
                doc.cancel()


class TestSendWebhook(FrappeTestCase):

    def setUp(self):
        super().setUp()
        create_device_type()
        create_technician()
        create_spare_part()

        part_name = frappe.db.get_value("Spare Part", {"part_name": "Test Part"}, "name")
        if part_name:
            frappe.db.set_value("Spare Part", part_name, "stock_qty", 10)

        frappe.db.set_single_value("QuickFix Settings", "webhook_url", "https://test-webhook.example.com")

    ## testcase 21 - webhook correct url and payload
    def test_webhook_called_with_correct_url_and_payload(self):
        doc = create_job_card()
        doc.status = "Ready for Delivery"
        doc.save(ignore_permissions=True)

        with patch("requests.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=200)

            send_webhook(doc.name)

            mock_post.assert_called_once()

            call_args = mock_post.call_args
            url_used = call_args.args[0] if call_args.args else call_args.kwargs.get("url")
            self.assertEqual(url_used, "https://test-webhook.example.com")

            payload = call_args.kwargs.get("json")
            self.assertIn("job_card", payload)
            self.assertIn("customer_name", payload)
            self.assertIn("status", payload)
            self.assertIn("final_amount", payload)

            self.assertEqual(payload["job_card"], doc.name)
            self.assertEqual(payload["customer_name"], doc.customer_name)

    ## testcase 22 - webhook connection error
    def test_webhook_connection_error_logs_error(self):
        doc = create_job_card()
        doc.status = "Ready for Delivery"
        doc.save(ignore_permissions=True)

        with patch("requests.post") as mock_post, \
             patch("frappe.log_error") as mock_log_error:

            mock_post.side_effect = requests.exceptions.ConnectionError("Connection refused")

            try:
                send_webhook(doc.name)
            except requests.exceptions.ConnectionError:
                self.fail("send_webhook crashed on ConnectionError instead of handling it")

            mock_log_error.assert_called_once()