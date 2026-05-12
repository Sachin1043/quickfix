import frappe

@frappe.whitelist()
def rename_technician(old_name, new_name):
    frappe.rename_doc(
        "Technician",
        old_name,
        new_name,
        merge=False
    )
    frappe.db.commit()
    return "Renamed successfully!"