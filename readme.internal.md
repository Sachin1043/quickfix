1. Creating Your App
To get your app created and installed on your local site, run these commands in your terminal:

Bash
bench new-app quickfix
bench --site your-site.localhost install-app quickfix
Once that's done, you need to tell Frappe a little bit about your app.

hooks.py — Just fill in the basics here so Frappe knows who made it:

Python
app_name = "quickfix"
app_title = "Quickfix"
app_publisher = "Your Name"
app_version = "0.0.1"
app_email = "you@example.com"
app_license = "MIT"
modules.txt — Register your module name so it shows up in the system:

Plaintext
service_center
config/desktop.py — This adds the tile to the Frappe home screen:

Python
get_data = lambda: [{"module_name": "Service Center", "type": "module"}]
Check your folder structure:
If everything went right, your quickfix/ folder should now have these files and folders: hooks.py, modules.txt, patches.txt, config/, public/, and www/.

2. Multi-Site Setup
If you're managing both a dev and a production site, you'll set them up like this:

Bash
bench new-site quickfix-dev.localhost
bench new-site quickfix-prod.localhost
bench --site quickfix-dev.localhost install-app quickfix
bench --site quickfix-prod.localhost install-app quickfix
Developer Mode (Dev Site Only!)
In your sites/quickfix-dev.localhost/site_config.json, add this:

JSON
{ "developer_mode": 1 }
Crucial rule: Never turn this on in production. If you do, your users will see messy Python error tracebacks on their screens, and it disables asset minification (making your site slower).

Shared Database Host
If you have settings that apply to all sites (like your database host), put them in sites/common_site_config.json:

JSON
{ "db_host": "localhost" }
Just remember: site_config.json is for one specific site. common_site_config.json is shared across the whole bench. Never put a secret API key in the common config unless you want every site to have access to it.

The 4 Processes of bench start
When you run bench start, it fires up four things:

web: Handles all the HTTP requests (using Gunicorn).

worker: Churns through background jobs in the queue.

scheduler: Triggers your scheduled/recurring tasks.

socketio: Handles real-time events (like live notifications).

Note: If the worker process crashes, your background jobs just sit in the queue. They aren't lost, but they won't run until you restart the worker.

3. How Requests Work
Frappe routes traffic in three different ways:

/api/method/quickfix.api.get_job_summary: Frappe looks at this URL and treats it like a direct path to a Python function. It will run get_job_summary() straight from apps/quickfix/quickfix/api.py.

/api/resource/Job Card/JC-2024-0001: This is Frappe's built-in REST API. It bypasses your custom code entirely. Frappe checks permissions automatically and returns the document.

/track-job: This is a public website route. It goes through the website rendering system, which is a totally different pipeline than the /api/ routes.

Sessions & CSRF Security
When making state-changing requests (like POST, PUT, DELETE), Frappe expects a security token.

The frontend gets it from frappe.csrf_token.

The server expects it to match frappe.session.data.csrf_token.

If you don't send it, Frappe blocks the request.

(Side note: If you check frappe.session.data in the bench console, it will be empty {}. That's normal, it only populates during a real browser session).

Developer Mode vs Production

Dev Mode (1): You get full tracebacks in your browser. Easy debugging.

Prod Mode (0): Users just see generic error messages. Errors are safely logged to frappe.log_error and the error_log database table.

Permission Check Location
When you run frappe.get_doc("Job Card", name), Frappe automatically checks if the current user is allowed to see it. If not, it throws a frappe.PermissionError immediately. Only pass ignore_permissions=True if you are writing code that the system needs to execute in the background.

4. Database & ORM
Tables & Columns
Frappe puts a tab prefix on all database tables. So "Job Card" becomes tabJob Card in SQL. This stops Frappe from clashing with reserved SQL words. Every single table automatically gets these columns: name, creation, modified, docstatus, and owner.

Understanding docstatus

0 = Draft

1 = Submitted

2 = Cancelled
You cannot save() a submitted doc, and you cannot submit() a cancelled doc.

The "Document Modified" Error
If two people open a document at the same time, and Person A saves it, Person B will get a "Document Modified" error when they try to save. This is a built-in safety feature to prevent silent overwrites.

Transactions
When writing custom logic, use frappe.db.commit() when things succeed, and frappe.db.rollback() in your except block if something breaks. Always use frappe.log_error() to record the issue.

(Empty Query Builder Note): Your notes had an empty Python block for get_overdue_jobs(), so we are leaving that blank.

Python

Transfer Job Example:
Here is a solid example of safely interacting with the database:

Python
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
5. Controller Logic (api.py)
A Classic validate() Bug
You should never call self.save() inside the validate() method. Here is why:

Bad pattern — don't do this:

Python
def validate(self):
    self.total = sum(r.amount for r in self.items)
    self.save()  # causes recursive save loop
    other = frappe.get_doc("Spare part", self.part)
    other.stock_qty -= self.qty
    other.save()  # unsafe side effect inside validate
Correct pattern:

Python
def validate(self):
    self.total = sum(r.amount for r in self.items)  # only compute, don't save

def before_submit(self):
    other = frappe.get_doc("Spare part", self.part)
    other.stock_qty -= self.qty
    other.save()  # safe to persist here
The Golden Rule: validate() is for doing math and checking rules. Never save yourself or other documents inside it.

6. Child Tables, Renaming, & Permissions
Child Tables (Part Usage Entry)
When you add a row to Job Card.parts_used, Frappe auto-fills the parent, parentfield, parenttype, and idx (row number) fields. If you delete a row, Frappe smartly renumbers the idx to keep everything sequential. The DB table is called tabPart Usage Entry.

Renaming Documents
Use frappe.rename_doc("Technician", old_name, new_name, merge=False). Setting merge=False is safe and cleanly updates linked fields.
Danger: Never use merge=True unless you really mean it. It smashes two records together and permanently deletes data.

Track Changes & Uniqueness

Track Changes: Checking this box means Frappe logs every edit so you can see who changed what.

Unique constraint vs frappe.db.exists(): Checking uniqueness in Python (validate()) is risky because two users clicking save at the exact same millisecond can bypass it. If a field MUST be unique, set it as unique in the DocType settings so the actual database enforces it.

Permissions Deep Dive

List View: You use permission_query_conditions to filter what people see. For example, ensuring technicians only see their assigned jobs.

Document Access: You use has_permission to block access to specific records (e.g., blocking non-managers from viewing an unpaid invoice).

frappe.get_all vs frappe.get_list: get_all skips permissions completely! Never use it if guests or low-level users can trigger the code. Always use get_list instead.

Sharing Records & Checking Roles

Python
@frappe.whitelist()
def share_job_card(job_card_name,user_email):
    frappe.share.add("Job Card", job_card_name, user_email, read=1)
    return "Job Card shared with {}".format(user_email)
If you use frappe.only_for("QF Manager") at the top of a function, it instantly throws an error if the user doesn't have that role, stopping the code dead in its tracks.

7. Job Card Lifecycle Logic
Here is exactly what should happen during the lifecycle of a Job Card:

validate(): Check if the phone is 10 digits. Check if an "In Repair" job has a tech assigned. Calculate the total prices. Load the labor charge if it's missing.

before_submit(): Stop them from submitting unless the status is "Ready for Delivery". Check if there's enough stock.

on_submit(): This is the action phase. Deduct the stock. Create the Service Invoice (using ignore_permissions=True). Trigger the realtime job_ready event, and queue up the email.

on_cancel(): Change status to "Cancelled". Give the stock back. Cancel the invoice.

on_trash(): Stop people from deleting it unless it's a Draft or Cancelled.

on_update(): Use this to recalculate amounts, but never call self.save().

Why ignore_permissions=True on submit? Because the system is deducting stock in the background. The user clicking "Submit" might not have inventory access, but the system still needs to do its job.

Here is the complete code for that lifecycle:

Python
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
            "quickfix.quickfix.api.send_job_ready_email",
            job_card=self.name
        )
        
    def on_cancel(self):
        self.db_set("status", "Cancelled")

        for row in self.parts_usage:
            stock_qty = frappe.db.get_value(
                "Spare Part",
                {"name": row.part},
                "stock_qty"
            )
            new_stock = (stock_qty or 0) + (row.quantity or 0)
            frappe.db.set_value(
                "Spare Part",
                row.part,
                "stock_qty",
                new_stock,
                update_modified=False
            )
        invoice = frappe.db.get_value("Service Invoice", {"job_card": self.name}, "name")

        if invoice:
            inv_doc = frappe.get_doc("Service Invoice", invoice)
            if inv_doc.docstatus == 1:  
                inv_doc.cancel()

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
8. Autoname, Overrides, & Hooks
autoname() on Spare Part

Python
def autoname(self):
    self.part_code = self.part_code.upper()
    self.name = make_autoname("PART-.YYYY.-.####")
This runs before the doc is saved. Uppercasing things here keeps your data clean.

Override Strategies (MRO & super())
If you override a core Frappe class, you must call super().validate(). If you don't, you wipe out all of Frappe's built-in checks for that document.

doc_events: The safest way to add logic. Multiple apps can hook into it.

override_doctype_class: More invasive. Swaps the whole class.

frappe.db.get_value: Use this instead of frappe.get_doc if you only need to read one field. It's much faster.

Here is an example of a proper override using super():

Python
    def validate(self):
        super().validate() 
        self._check_urgent_unassigned()

    def _check_urgent_unassigned(self):
        if frappe.flags.in_validate:
            return

        if self.priority == "Urgent" and not self.assigned_technician:
            frappe.msgprint("Urgent Job Card must have an assigned technician.", alert=True)
            settings = frappe.get_single("QuickFix Settings")
            
            frappe.enqueue("quickfix.utils.send_urgent_alert",job_card=self.name, manager=settings.manager_email,enqueue_after_commit=True)
Doc Events & Wildcards
If you use "*" as the DocType in doc_events, your code will run for every single document in the system. Great for audit logs. If a controller throws an error during validate, your doc_events handler will never run.

Install & Boot Hooks

after_install: Great for creating default setup data.

before_uninstall: Great for stopping someone from accidentally deleting the app if there's active data.

extend_bootinfo: Sends global settings to the frontend JS right when the user logs in.

Here is how you write those hooks:

Python
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
9. Frontend Hooks & Whitelisting
Frontend Hooks

app_include_js: For backend Desk users.

web_include_js: For public-facing website pages.

doctype_js: Logic inside a form.

doctype_list_js: Logic on the list view.
(Always run bench build --app quickfix after changing JS to clear the cache).

Jinja Templates: Print formats get doc automatically. Web pages do not.

Website Routes Example (in hooks.py):

Python
# hooks.py
website_route_rules = [{"from_route": "/track-job", "to_route": "track-job"}]
portal_menu_items = [{"title": "Track My Job", "route": "/track-job", "role": "Guest"}]
override_whitelisted_methods
This is the clean way to replace a Frappe API endpoint. It's safe and reversible. If two apps override the same method, the last one installed wins silently. Just make sure your function arguments exactly match the original, or you'll get a TypeError.

Python
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
10. Fixtures, Patches, & Monkey Patching
Fixtures
Fixtures let you bundle custom fields and settings so they install automatically on other servers. Put this in your hooks.py:

Python
fixtures = [
    "Role",
    "Workspace",
    {"dt": "Custom Field", "filters": [["module", "=", "Quickfix"]]},
    {"dt": "Property Setter", "filters": [["module", "=", "Quickfix"]]},
    {"dt": "Device Type"},
    {"dt": "QuickFix Settings"},
]
Pro tip: Always prefix custom fields (e.g., qf_status). If Frappe updates and adds their own status field, it will crash your app.

Property Setters (after_install)
If you want to tweak a standard field (like making the remarks field bold) without modifying the core, use this in setup.py:

Python
def after_install():
    frappe.make_property_setter({
        "doctype": "Job Card",
        "fieldname": "remarks",
        "property": "bold",
        "value": "1",
        "property_type": "Check"
    })
    frappe.db.commit()
Patching Order
Never put field creation and field usage in the exact same patch file. The database column doesn't actually get created until between patches. If you bundle them, the script will crash trying to read a column that doesn't exist yet.

Safe Monkey Patching (The Last Resort)
Monkey patching changes code while it's running. It's dangerous. If you have to do it, isolate it in a monkey_patches.py file, and always use a flag (_qf_patched) so it doesn't get stuck in an infinite loop:

Python
import frappe

def apply_all():
    _patch_get_url()

def _patch_get_url():
    import frappe.utils as fu

    if hasattr(fu, "_qf_patched"):
        return

    _orig = fu.get_url

    def _custom_get_url(path=None, full_address=False):
        url = _orig(path, full_address)
        prefix = frappe.conf.get("custom_url_prefix", "")
        return prefix + url if prefix else url

    fu.get_url = _custom_get_url
    fu._qf_patched = True
11. Final Wrap-Up Notes
Async Client-Side: Never put frappe.call() inside a JS validate or before_save trigger. It's async, meaning the document will save before the server has time to reply. Use it in onload or refresh instead.

Tree DocType: Used for hierarchies (like chart of accounts). It needs a parent_field and an is_group checkbox.

Client Script vs Shipped JS: Client scripts (in the UI) are great for quick hacks. Shipped JS (in your codebase) is best for real development because it uses version control and is safer.

JS Hide is NOT Security: Hiding a field on the frontend doesn't secure the data. A smart user can still read it from the network API.

JavaScript
frm.set_df_property("customer_phone", "hidden", 1) 
// This only hides it visually!