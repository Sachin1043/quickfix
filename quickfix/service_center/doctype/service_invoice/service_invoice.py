# Copyright (c) 2026, sachin and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class ServiceInvoice(Document):
	pass

def has_permission(doc,user=None):
	
	roles = frappe.get_roles(user)

	if "QF Manager" in roles:
		return True

	if doc.payment_status == "Paid":
		return True
		
	return False
