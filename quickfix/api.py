import frappe

@frappe.whitelist()
def get_job_summary():
    return "Hello from api"

@frappe.whitelist()
def share_job_card(job_card_name,user_email):
    frappe.share.add("Job Card", job_card_name, user_email, read=1)
    return "Job Card shared with {}".format(user_email)

@frappe.whitelist()
def manager_only():
    frappe.only_for("QF Manager")
    return "Hello Manager"

# http://127.0.0.1:8001/api/method/quickfix.api.get_job_cards_unsafe  -  Unsafe as it exposes all data
# http://http://127.0.0.1:8001/api/method/quickfix.api.get_job_cards_safe  - Safe as it checks user permissions


@frappe.whitelist()
def get_job_cards_unsafe():
    return frappe.get_all("Job Card",
                fields=["name","customer_name","customer_phone","customer_email"])

@frappe.whitelist()
def get_job_cards_safe():
    user = frappe.session.user

    data = frappe.get_list("Job Card",
                           fields=["name","customer_name","customer_phone","customer_email"])
    
    if "QF Manager" not in frappe.get_roles(user):
        for row in data:
            row.pop("customer_phone",None)
            row.pop("customer_email",None)
    return data

def send_job_ready_email(job_card):

    doc = frappe.get_doc("Job Card", job_card)

    frappe.sendmail(
        recipients=[doc.owner],
        subject="Your Job Card is Ready",
        message=f"""
        Job Card {doc.name} is ready for delivery.
        Final Amount: {doc.final_amount}
        """
    )

@frappe.whitelist()
def custom_get_count(doctype, filters=None, debug=False, cache=False):
    frappe.get_doc(
        {
            "doctype":"Audit Log",
            "doctype_name":doctype,
            "action":"count_queried",
            "user":frappe.session.user
        }
    ).insert(ignore_permissions=True)

    from frappe.client import get_count
    
    return get_count(doctype, filters, debug, cache)

    # api.py

import frappe


@frappe.whitelist()
def transfer_job(job, technician):

    try:

        doc = frappe.get_doc("Job Card", job)

        doc.db_set("assigned_technician", technician)

        return {
            "status": "success",
            "message": "Technician transferred successfully"
        }

    except Exception as e:

        frappe.log_error(
            frappe.get_traceback(),
            "Transfer Job Error"
        )

        raise e
    
@frappe.whitelist()
def complete_job(job):
    
    doc = frappe.get_doc("Job Card",job)

    doc.db_set("status","Completed")

    return "Job Completed!"