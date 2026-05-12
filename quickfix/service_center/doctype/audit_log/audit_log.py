import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime

class AuditLog(Document):
	pass

def log_doctype(doc, method):

	if doc.doctype in ["Audit Log", "User", "Sessions", "Error Log", "Activity Log", "Access Log"]:
		return

	try:
		frappe.get_doc({
			"doctype": "Audit Log",
			"doctype_name": doc.doctype,
			"document_name": doc.name,
			"action": method,
			"user": frappe.session.user,
			"timestamp": now_datetime()
		}).insert(ignore_permissions=True)

	except Exception as e:
		frappe.log_error(
			title="Audit Log Failed",
			message=str(e)
		)

def user_on_creation(login_manager):

	user = login_manager.user

	if user == "Guest":
		return

	try:
		frappe.get_doc({
			"doctype": "Audit Log",
			"doctype_name": "User",
			"document_name": user,
			"action": "User Login",
			"user": user,
			"timestamp": now_datetime()
		}).insert(ignore_permissions=True)

		frappe.db.commit()

	except Exception as e:
		frappe.log_error(
			title="Audit Log Login Failed",
			message=str(e)
		)
		frappe.db.rollback()

def user_on_logout(login_manager):
	user = login_manager.user

	if user == "Guest":
		return

	try:
		frappe.get_doc({
			"doctype": "Audit Log",
			"doctype_name": "User",
			"document_name": user,
			"action": "User Logout",
			"user": user,
			"timestamp": now_datetime()
		}).insert(ignore_permissions=True)

		frappe.db.commit()
	except Exception as e:
		frappe.log_error(
			title="Audit Log logout failed",
			message=str(e)
		)
		frappe.db.rollback()

