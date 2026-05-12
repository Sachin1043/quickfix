# Copyright (c) 2026, sachin and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document

import frappe
class SparePart(Document):

	def before_save(self):
		if self.selling_price <= self.unit_cost:
			frappe.throw("Selling price cannot be less than unit cost")

	def autoname(self):

		if self.part_code:
			self.part_code = self.part_code.upper()

		#  method-1 default naming series

		# series = self.naming_series or "SP-.####"    
		# self.name = frappe.model.naming.make_autoname(series) 

		# method -2 part_code with naming series

			self.name = f"{self.part_code}-{frappe.model.naming.make_autoname('.####')}"

	def on_update(self):

		# this method downloads full file and search for specific doctype unitl it found -- too heavy 

		# doc = frappe.get_doc("QuickFix Settings", "QuickFix Settings")
		# threshold = doc.low_stock_threshold

		# here the operations are done by single get value, it only reads the specific doctype. -- fast
		threshold = frappe.db.get_value("QuickFix Settings", None,"low_stock_threshold")


# Performance Explanation:


# frappe.db.get_value() is preferred because it directly fetches
# the required field from the database without loading the entire document.
#
# frappe.get_doc() loads the full document along with all fields,
# metadata, and triggers additional processing, which is slower.
#
# Therefore, for simple read operations (like fetching a single value),
# frappe.db.get_value() is more efficient and improves performance.
	
		
