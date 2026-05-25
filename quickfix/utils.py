import frappe

try:
    import qrcode
except ImportError:
    qrcode = None
import base64

from io import BytesIO

def send_urgent_alert(job_card, manager):

    try:
        frappe.sendmail(
        recipients=[manager],
        subject="Urgent Job Card Alert",
        message=f"""
        Job Card {job_card} is marked as Urgent and has no assigned technician.
        Please assign a technician as soon as possible.
        """
    )
        
    except Exception as e:
        print("Mail failed:", e)
    
    print(f"Alert sent to {manager} for Job Card {job_card}")

def get_shop_name():

    shop_name = frappe.db.get_single_value("QuickFix Settings","shop_name")
    return shop_name

def format_job_id(job_id):

    return f"JOB#{job_id}"




def generate_qr_code(docname):

    url = frappe.utils.get_url(
        f"/app/job-card/{docname}"
    )

    qr = qrcode.make(url)

    buffer = BytesIO()

    qr.save(buffer, format="PNG")

    encoded = base64.b64encode(
        buffer.getvalue()
    ).decode()

    return encoded