from frappe.model.document import Document

import frappe
from frappe.utils.pdf import get_pdf

class JobCard(Document):       

    def validate(self):

        if not self.customer_phone or not self.customer_phone.isdigit() or len(self.customer_phone) != 10:
            frappe.throw(frappe._("Phone Number must be exactly 10 digit"))

        if self.status == "In Repair" and not self.assigned_technician:
            frappe.throw(
                frappe._("Assigned Technician is required when status is In Repair"),
                frappe.ValidationError
            )

        if self.status in ["In Repair", "Ready for Delivery", "Delivered"] and self.estimated_cost == 0:
            frappe.throw(
                frappe._("Estimated Cost is required for advanced statuses."),
                frappe.ValidationError
            )

        parts_total = 0
        for row in self.parts_usage:
            if (row.quantity or 0) <= 0:
                frappe.throw(
                    frappe._(f"Row {row.idx}: Quantity must be greater than zero for part {row.part}"),
                    frappe.ValidationError
                )
            row.total_price = (row.quantity or 0) * (row.unit_cost or 0)
            parts_total += row.total_price

        self.parts_total = parts_total

        labour_charge = frappe.db.get_single_value("QuickFix Settings", "default_labour_charge") or 0
        self.final_amount = self.parts_total + labour_charge

    def before_submit(self):
        if self.status != "Ready for Delivery":
            frappe.throw(frappe._("Only allowed to submit if the status is Ready for Delivery"))

        for row in self.parts_usage:
            stck = frappe.db.get_value("Spare Part", {"part_name": row.part}, "stock_qty")

            if stck is None:
                frappe.throw(frappe._(f"Stock not found for part {row.part}"))

            if stck < (row.quantity or 0):
                frappe.throw(
                    frappe._(f"Insufficient stock for part {row.part}. Available: {stck}, Required: {row.quantity}"),
                    frappe.ValidationError
                )

    def on_update(self):
        frappe.cache().delete_value("status_chart")

    def on_submit(self):

        frappe.enqueue(
            "quickfix.task.send_webhook",
            job_card_name=self.name
        )

        for row in self.parts_usage:
            part_name = frappe.db.get_value("Spare Part", {"part_name": row.part}, "name")
            current_stock = frappe.db.get_value("Spare Part", part_name, "stock_qty")
            frappe.db.set_value("Spare Part", part_name, "stock_qty", current_stock - row.quantity)

        existing_invoice = frappe.db.get_value(
            "Service Invoice",
            {"job_card": self.name},
            "name"
        )

        if not existing_invoice:
            invoice = frappe.get_doc({
                "doctype": "Service Invoice",
                "job_card": self.name,
                "total_amount": self.final_amount,
                "payment_status": "Unpaid"
            })
            invoice.insert(ignore_permissions=True)
            invoice.submit()

        frappe.publish_realtime(
            event="job_ready",
            message={"job_card": self.name}
        )

        frappe.enqueue(
            "quickfix.api.send_job_ready_email",
            job_card=self.name
        )

        frappe.sendmail(
            recipients=self.customer_email,
            subject=frappe._(f"Job Card {self.name} - Ready for Delivery"),
            message=frappe._(f"Dear {self.customer_name}, your device is ready for delivery. Final amount: {self.final_amount}")
        )

        self.send_invoice_email()

    def send_invoice_email(self):
        try:
            pdf_content = get_pdf(
                frappe.get_print(
                    "Job Card",
                    self.name
                )
            )
            frappe.sendmail(
                recipients=[self.customer_email],
                subject=frappe._(f"Invoice for Job {self.name}"),
                message=frappe._(f"Dear {self.customer_name}, please find your invoice attached for job {self.name}. Amount: {self.final_amount}. Thank you for choosing QuickFix!"),
                attachments=[{
                    "fname": f"Invoice-{self.name}.pdf",
                    "fcontent": pdf_content
                }]
            )

            frappe.log_error(
                title=frappe._("Invoice Email Sent"),
                message=f"Email sent to {self.customer_email} for {self.name}"
            )

        except Exception:
            frappe.log_error(
                title=frappe._("Invoice Email Failed"),
                message=frappe.get_traceback()
            )

    def get_print_summary(self):
        brand = self.device_brand or ""
        model = self.device_model or ""
        return f"{self.customer_name} - {brand} {model}"

    def on_cancel(self):

        for row in self.parts_usage:
            part_name = frappe.db.get_value("Spare Part", {"part_name": row.part}, "name")
            current_stock = frappe.db.get_value("Spare Part", part_name, "stock_qty")
            frappe.db.set_value("Spare Part", part_name, "stock_qty", current_stock + row.quantity)

        # removed duplicate get_value — was fetched twice before
        invoice = frappe.db.get_value(
            "Service Invoice",
            {"job_card": self.name},
            "name"
        )

        if invoice:
            try:
                inv_doc = frappe.get_doc("Service Invoice", invoice)

                if inv_doc.docstatus == 1:
                    inv_doc.flags.ignore_permissions = True
                    inv_doc.cancel()

            except Exception:
                frappe.log_error(
                    frappe.get_traceback(),
                    frappe._("Service Invoice Cancel Error")
                )
                raise

    def on_trash(self):
        if self.docstatus == 1:
            frappe.throw(
                frappe._("Cannot delete a submitted Job Card. Cancel it first."),
                frappe.ValidationError
            )


def job_card_query(user):

    roles = frappe.get_roles(user)

    if user == "Administrator" or "QF Manager" in roles:
        return ""

    if "QF Technician" in frappe.get_roles(user):
        technician = frappe.db.get_value("Technician", {"user": user}, "name")

        if technician:
            return f"`tabJob Card`.assigned_technician = '{technician}'"
        else:
            return "1=0"

    return ""