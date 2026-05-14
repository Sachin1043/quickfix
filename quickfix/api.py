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

@frappe.whitelist()
def send_job_ready_email(job_card):

    doc = frappe.get_doc("Job Card", job_card)

    frappe.sendmail(
        recipients=[doc.customer_email],
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


@frappe.whitelist()
def prepare_technician_report(filters=None):

    frappe.enqueue(

        method=generate_report,

        queue="long",

        timeout=300,

        filters=filters
    )

    return "Report queued successfully"


def generate_report(filters=None):

    report = frappe.get_doc(
        "Report",
        "Technician Performance Report"
    )

    result = report.get_data(
        filters=filters,
        as_dict=True
    )

    frappe.get_doc({

        "doctype": "Prepared Report",

        "report_name": "Technician Performance Report",

        "filters": frappe.as_json(filters),

        "status": "Completed",

        "report_end_time": frappe.utils.now(),

        "output": frappe.as_json(result)

    }).insert(ignore_permissions=True)


import frappe


@frappe.whitelist()
def get_status_chart_data():

    data = frappe.db.sql("""

        SELECT
            status,
            COUNT(*) as count

        FROM `tabJob Card`

        GROUP BY status

    """, as_dict=True)

    return {

        "labels": [d.status for d in data],

        "datasets": [

            {
                "name": "Job Count",
                "values": [d.count for d in data]
            }
        ]
    }

import frappe
from frappe.utils import today


@frappe.whitelist()
def get_today_revenue():

    revenue = frappe.db.sql("""

        SELECT
            SUM(final_amount)

        FROM `tabJob Card`

        WHERE
            status = 'Delivered'
            AND DATE(modified) = %s

    """, today())

    return revenue[0][0] or 0

@frappe.whitelist()
def start_revenue_report(year):

    frappe.enqueue(
        "quickfix.tasks.generate_monthly_revenue_report",
        year=year,
        queue="long",
        timeout=600
    )

    return "Report generation started"