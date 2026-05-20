# Copyright (c) 2026, sachin and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase


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
        "part_name": "Test Part " + frappe.generate_hash(length=4),
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

	def test_valid_job_card(self):

		doc = create_job_card()
		self.assertTrue(frappe.db.exists("Job Card", doc.name))

	def test_phone_validation(self):

		with self.assertRaises(frappe.ValidationError):
			create_job_card(customer_phone="123")
		with self.assertRaises(frappe.ValidationError):
			create_job_card(customer_phone="12345678901")
		with self.assertRaises(frappe.ValidationError):
			create_job_card(customer_phone="123456789a")

		doc = create_job_card(customer_phone="9876543210")
		self.assertTrue(frappe.db.exists("Job Card", doc.name))

	def test_spare_part_selling_price_constraint(self):

		with self.assertRaises(frappe.ValidationError):
			create_spare_part(unit_cost=100, selling_price=99)
		with self.assertRaises(frappe.ValidationError):
			create_spare_part(unit_cost=100, selling_price=100)

		doc = create_spare_part(unit_cost=100, selling_price=101)
		self.assertTrue(frappe.db.exists("Spare Part", doc.name))
	