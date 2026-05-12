
import frappe

def after_install():
    frappe.make_property_setter(
        "Job Card",
        "remarks",
        "bold",
        "1",
        "Check"
    )
    frappe.db.commit()