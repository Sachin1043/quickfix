import frappe

def validate_handler(doc,method):

    if doc.priority == "Low":
        frappe.throw("Blocked by doc events")

def after_install_doctype():

    device = ["Fridge","Fan","Mobile"]

    for dev in device:
         
        if not frappe.db.exists("Device Type",dev):
             
             doc = frappe.new_doc("Device Type")
             doc.device_type = dev
             doc.insert(ignore_permissions=True)

             print(f"New Device type {dev} is created successfully")
        else:
            print(f"{dev} is already exist")
    settings = frappe.get_single("QuickFix Settings")

    if not settings.shop_name:
         settings.shop_name = "Repair shop"
         settings.manager_email = "admin007@gmail.com"
         settings.default_labour_charge = 300
         settings.save(ignore_permissions=True)

         print(f"{settings.shop_name} is created successfulyy!")
    else:
        print(f"{settings.shop_name} is already exits")

        
def before_uninstall_doctype():

    submitted_jobs = frappe.get_all("Job Card",filter={"docstatus":1})

    if submitted_jobs:
        raise frappe.ValidationError("There's submitted job cards unsafe to uninstall")
    print("No Submitted jobs safe to uninstall")

def extend_bootinfo_settings(bootinfo):

    settings = frappe.get_single("QuickFix Settings")
    bootinfo.quickfix_shop_name = settings.shop_name
    bootinfo.quickfix_manager_email = settings.manager_email
