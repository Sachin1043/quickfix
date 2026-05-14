
from frappe.model.document import Document

import frappe

class JobCard(Document):       

    def validate(self):

        if not self.customer_phone or not self.customer_phone.isdigit() or len(self.customer_phone) != 10:
            frappe.throw("Phone Number must be exactly 10 digit")


        if self.status in ["In Repair", "Ready For Delivery" ,"Delivered","Cancelled"]:
            if not self.assigned_technician:
                frappe.throw("Technician should assigned for in repair or beyond")

        total = 0

        for row in self.parts_usage:

            unit_cost = row.unit_cost or 0
            quantity = row.quantity or 0

            row.total_price = unit_cost * quantity

            total += row.total_price

        if not self.labour_charge:
            self.labour_charge = frappe.db.get_single_value("QuickFix Settings","default_labour_charge")


        self.parts_total = total
        self.final_amount = total + (self.labour_charge or 0)

    def before_submit(self):
        if self.status != "Ready for Delivery":
            frappe.throw("Only allowed for submit if the status is ready for delivery")
        
        for row in self.parts_usage:

            stck = frappe.db.get_value("Spare Part",{"part_name":row.part_name},"stock_qty")

            if stck is None:
                frappe.throw(f"Stock not found for part {row.part_name}")

            if stck < (row.quantity or 0):
                frappe.throw(
                f"Insufficient stock for part {row.part_name}. Available: {stck}, Required: {row.quantity}"
            )
    
    def on_submit(self):
  
        for row in self.parts_usage:

            stock_qty = frappe.db.get_value(
                "Spare Part",
                {"name": row.part},
                "stock_qty"
            )

            new_stock = (stock_qty or 0) - (row.quantity or 0)

            frappe.db.set_value(
                "Spare Part",
                row.part,
                "stock_qty",
                new_stock,
                update_modified=False
            )

        # Create Service Invoice
        invoice = frappe.get_doc({
            "doctype": "Service Invoice",
            "job_card": self.name,
            "payment_status": "Unpaid"
        })
        invoice.insert(ignore_permissions=True)


        # Realtime notification
        frappe.publish_realtime(
            "job_ready",
            {"job_card": self.name},
            user=self.owner
        )

        # Background email (async)
        frappe.enqueue(
            "quickfix.api.send_job_ready_email",
            job_card=self.name
        )
    def get_print_summary(self):

        brand = self.device_brand or ""

        model = self.device_model or ""

        return f"{self.customer_name} - {brand} {model}"
            
    # def on_cancel(self):

    #     for row in self.parts_usage:

    #         stock_qty = frappe.db.get_value(
    #             "Spare Part",
    #             {"name": row.part},
    #             "stock_qty"
    #         )

    #         new_stock = (stock_qty or 0) + (row.quantity or 0)

    #         frappe.db.set_value(
    #             "Spare Part",
    #             row.part,
    #             "stock_qty",
    #             new_stock,
    #             update_modified=False
    #         )

    #     invoice = frappe.db.get_value(
    #         "Service Invoice",
    #         {"job_card": self.name},
    #         "name"
    #     )

    #     if invoice:

    #         try:

    #             inv_doc = frappe.get_doc("Service Invoice", invoice)

    #             if inv_doc.docstatus == 1:
    #                 inv_doc.cancel()

    #         except Exception:

    #             frappe.log_error(
    #                 frappe.get_traceback(),
    #                 "Service Invoice Cancel Error"
    #             )

    #             raise

    def on_trash(self):

        if self.status not in ["Draft", "Cancelled"]:
            frappe.throw("Only Draft or Cancelled Job Cards can be deleted")

    def on_update(self):

        if not self.some_field:
            self.db_set("some_field", "default_value")

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
	



