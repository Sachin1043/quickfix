from frappe.utils import today

import frappe
import requests

def check_low_stock():

    # Idempotency guard

    last_run = frappe.db.get_value(
        "Audit Log",
        {
            "action": "low_stock_check",
            "date": today()
        },
        "name"
    )

    if last_run:
        return

    low_stock_parts = frappe.get_all(
        "Spare Part",
        filters={
            "stock_qty": ["<", 5]
        },
        fields=["name", "part_name", "stock_qty"]
    )

    for part in low_stock_parts:

        frappe.log_error(
            f"Low stock for {part.part_name}",
            "Low Stock Alert"
        )

    # Create audit log

    frappe.get_doc({
        "doctype": "Audit Log",
        "action": "low_stock_check",
        "date": today()
    }).insert(ignore_permissions=True)


import frappe


def generate_monthly_revenue_report(year):

    months = range(1, 13)

    yearly_total = 0

    for i, month in enumerate(months, 1):

        revenue = frappe.db.sql("""
            SELECT SUM(final_amount)
            FROM `tabJob Card`
            WHERE YEAR(creation) = %s
            AND MONTH(creation) = %s
            AND docstatus = 1
        """, (year, month))[0][0] or 0

        yearly_total += revenue

        frappe.publish_progress(
            percent=round(i / 12 * 100),
            title="Generating Revenue Report",
            description=f"Processing month {month}..."
        )

    frappe.msgprint(
        f"Yearly Revenue: {yearly_total}"
    )


def failing_background_job():

    raise Exception(
        "Intentional background job failure"
    )


def send_webhook(job_card_name):
    doc = frappe.get_doc("Job Card", job_card_name)
    
    webhook_url = frappe.db.get_single_value("QuickFix Settings", "webhook_url")
    
    if not webhook_url:
        return

    payload = {
        "job_card": doc.name,
        "customer_name": doc.customer_name,
        "status": doc.status,
        "final_amount": doc.final_amount
    }

    try:
        requests.post(webhook_url, json=payload)
    except requests.exceptions.ConnectionError:
        frappe.log_error(
            frappe.get_traceback(),
            "Webhook Connection Error"
        )

def failing_job():

    x = 10 / 0