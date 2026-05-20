import re

import frappe
from datetime import date


@frappe.whitelist()
def get_job_summary():

    job_card_name = frappe.form_dict.get("job_card_name")

    if not frappe.db.exists("Job Card", job_card_name):

        frappe.local.response["http_status_code"] = 404

        return {
            "error": "Not found"
        }

    doc = frappe.get_doc("Job Card", job_card_name)

    return {

        "job_card": doc.name,

        "customer_name": doc.customer_name,

        "status": doc.status,

        "final_amount": doc.final_amount,

        "created_date": date.today()
    }

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


import frappe


@frappe.whitelist(allow_guest=True)
def get_job_by_phone():

    ip = frappe.local.request_ip

    key = f"limit:{ip}"

    count = frappe.cache().get_value(key) or 0

    if int(count) >= 5:

        frappe.throw("Too many requests")

    frappe.cache().set_value(
        key,
        int(count) + 1,
        expires_in_sec=60
    )

    phone = frappe.form_dict.get("phone")

    if not phone:
        frappe.throw("Phone number is required")

    if not re.match(r'^\d{10}$', phone):
        frappe.throw("Invalid phone number. Must be 10 digits only.")

    return frappe.get_all(
    "Job Card",
    filters={
        "customer_phone": phone
    },
    fields=["name", "status"]
    )

import frappe
import hmac
import hashlib
import json


@frappe.whitelist(allow_guest=True)
def payment_webhook():

    payload = frappe.request.data

    secret = frappe.conf.get(
        "payment_webhook_secret",
        ""
    )

    signature = frappe.get_request_header(
        "X-Signature"
    )

    expected = hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(
        expected,
        signature or ""
    ):

        frappe.throw(
            "Invalid signature",
            frappe.AuthenticationError
        )

    data = json.loads(payload)

    if frappe.db.exists(
        "Audit Log",
        {
            "action": "payment_received",
            "document_name": data["ref"]
        }
    ):

        return {
            "status": "duplicate",
            "message": "Already processed"
        }

    doc = frappe.get_doc(
        "Job Card",
        data["ref"]
    )

    doc.payment_status = "Paid"

    doc.save()

    frappe.get_doc({

        "doctype": "Audit Log",

        "action": "payment_received",

        "document_name": data["ref"]

    }).insert(ignore_permissions=True)


    return {
        "status": "ok"
    }

@frappe.whitelist()
def get_status_chart_data():

    cache_key = "status_chart"

    cached = frappe.cache().get_value(
        cache_key
    )

    if cached:
        return cached

    data = frappe.db.sql("""

        SELECT
            status,
            COUNT(*) as count

        FROM `tabJob Card`

        GROUP BY status

    """, as_dict=True)

    frappe.cache().set_value(
        cache_key,
        data,
        expires_in_sec=300
    )

    return data
logger = frappe.logger("quickfix", with_more_info=True)

@frappe.whitelist(allow_guest=True)
def handle_webhook():


    try:
        logger.info("Webhook received")

        data = frappe.request.get_json()

        logger.info(f"Payload received: {data}")

        doc = frappe.get_doc({
            "doctype": "Note",
            "title": data.get("order_id"),
            "content": f"Order received with amount {data.get('amount')}"
        })
        doc.insert(ignore_permissions=True)
        frappe.db.commit() 

        logger.info(f"Note created successfully for order {data.get('order_id')}")


    except Exception:
        logger.error("Webhook processing failed")

        frappe.log_error(
            title="Webhook Handler Failed",
            message=frappe.get_traceback()
        )

@frappe.whitelist()
def test_logger():

    logger = frappe.logger(
        "quickfix",
        allow_site=True
    )

    logger.info("TEST LOGGER WORKING")

    return "done"

@frappe.whitelist(allow_guest=True)
def get_job_status(job_id):

    job = frappe.db.get_value(

        "Job Card",

        job_id,

        [
            "status",
            "device_type",
            "final_amount"
        ],

        as_dict=True
    )

    return job