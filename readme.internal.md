
## A1 — Creating the App

Run this to create the app and install it on your site:

```bash
bench new-app quickfix
bench --site your-site.localhost install-app quickfix
```

### `hooks.py` — fill in the basics

```python
app_name = "quickfix"
app_title = "Quickfix"
app_publisher = "Your Name"
app_version = "0.0.1"
app_email = "you@example.com"
app_license = "MIT"
```

### `modules.txt` — register your module

```
service_center
```

### `config/desktop.py` — add the home page tile

```python
get_data = lambda: [{"module_name": "Service Center", "type": "module"}]
```

### Check your folder structure

After setup, your `quickfix/` directory should have:
`hooks.py`, `modules.txt`, `patches.txt`, `config/`, `public/`, `www/`

---

## A2 — Multi-Site Setup

### Create two sites

```bash
bench new-site quickfix-dev.localhost
bench new-site quickfix-prod.localhost
bench --site quickfix-dev.localhost install-app quickfix
bench --site quickfix-prod.localhost install-app quickfix
```

### Developer mode — dev site only

In `sites/quickfix-dev.localhost/site_config.json`:
```json
{ "developer_mode": 1 }
```

Never set this on prod. It exposes full Python tracebacks in HTTP responses and disables asset minification.

### Shared DB host — common config

In `sites/common_site_config.json`:
```json
{ "db_host": "localhost" }
```

### What each config file does

`site_config.json` is per-site — only that site reads it. `common_site_config.json` applies to every site on the bench. If you accidentally put a secret (like an API key or password) in `common_site_config.json`, every site on that bench can read it — including ones that shouldn't have access to it.

### The 4 processes `bench start` launches

| Process | What it does |
|---|---|
| `web` | Handles HTTP requests via Gunicorn |
| `worker` | Runs background jobs from the queue |
| `scheduler` | Triggers scheduled/recurring tasks |
| `socketio` | Handles realtime events (like `publish_realtime`) |

If the worker process crashes, background jobs stop processing. Jobs stay in the queue but nothing picks them up until the worker restarts. No jobs are lost, but they pile up silently.

---

## B1 — How Requests Work

### `/api/method/quickfix.api.get_job_summary`
Frappe reads the URL after `/api/method/` as a Python dotted path and calls that function directly. So this hits `get_job_summary()` inside `apps/quickfix/quickfix/api.py`. Think of it as a direct line to a Python function.

### `/api/resource/Job Card/JC-2024-0001`
This goes through Frappe's generic REST handler — not your custom code. Frappe reads the DocType metadata, checks permissions, and returns the document. No custom server method is involved here.

### `/track-job`
This is a website route, not an API call. Frappe resolves it through its website/page rendering system — the same way public pages work. Totally different pipeline from `/api/`.

---

## Sessions & CSRF

- The `X-Frappe-CSRF-Token` header value comes from `frappe.csrf_token` on the client side.
- Frappe stores it in `frappe.session.data.csrf_token` on the server.
- If you send a state-changing request (POST, PUT, DELETE) without a valid CSRF token, Frappe rejects it immediately.
- In `bench console`, `frappe.session.data` returns `{}` — that's normal. It only has real values during an actual browser session.

---

## Developer Mode vs Production

| | Developer Mode (`1`) | Production (`0`) |
|---|---|---|
| Errors | Full traceback in browser | Generic error message only |
| Debugging | Easy | Errors go to `frappe.log_error` and the `error_log` table |

Always keep `developer_mode: 0` in production. Users should never see Python tracebacks.

---

## Permission Check Location

When you call `frappe.get_doc("Job Card", name)`, Frappe checks permissions automatically. If the user doesn't have access (e.g., a technician not assigned to that job), it raises `frappe.PermissionError` before your code even runs. Add `ignore_permissions=True` only when you genuinely mean it — like system-initiated writes.

---

## B2 — Database & ORM

### Table Names
Frappe adds a `tab` prefix to all DocType tables. So "Job Card" lives in `tabJob Card`. This avoids clashing with reserved SQL names like `user`.

### Standard Columns
Every DocType table has: `name`, `creation`, `modified`, `docstatus`, `owner`. These are always there.

### `docstatus` Values
- `0` = Draft
- `1` = Submitted
- `2` = Cancelled

You can't call `save()` on a submitted doc (unless amending). You can't call `submit()` on a cancelled doc.

### The "Document Modified" Error
Frappe compares timestamps before saving. If two people (or processes) open the same doc and one saves first, the second gets this error. It's a safeguard against silent overwrites.

### Transactions
Use `frappe.db.commit()` on success and `frappe.db.rollback()` in the `except` block. Log errors with `frappe.log_error()` before re-raising.

### Query Builder — `get_overdue_jobs()`

### Transfer Job — `transfer_job()`


```python
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
```

# api.py

---

## A Classic `validate()` Bug

**Bad pattern — don't do this:**
```python
def validate(self):
    self.total = sum(r.amount for r in self.items)
    self.save()  # causes recursive save loop
    other = frappe.get_doc("Spare part", self.part)
    other.stock_qty -= self.qty
    other.save()  # unsafe side effect inside validate
```

**Correct pattern:**
```python
def validate(self):
    self.total = sum(r.amount for r in self.items)  # only compute, don't save

def before_submit(self):
    other = frappe.get_doc("Spare part", self.part)
    other.stock_qty -= self.qty
    other.save()  # safe to persist here
```

The rule: `validate()` is for checking and computing. Never save yourself or other documents inside it.

---

## C1 — Child Tables (Part Usage Entry)

- When you append a row to `Job Card.parts_used` and save, Frappe automatically fills in `parent`, `parentfield`, `parenttype`, and `idx`.
- The DB table name is `tabPart Usage Entry`.
- If you delete a row and resave, Frappe renumbers the remaining rows to keep `idx` sequential.

---

## C3 — Renaming Documents

`frappe.rename_doc("Technician", old_name, new_name, merge=False)` automatically updates all linked fields (like `assigned_technician` on Job Cards). Use `merge=False` — it's safe and updates links cleanly.

**Never use `merge=True`** unless you're absolutely certain. It merges two distinct records and can destroy data.

**Track Changes** means Frappe records a revision every time a field is edited, so you can see who changed what and when.

**Unique constraint vs `frappe.db.exists()` check:**
Setting a field as `unique` in the DocType creates a database-level constraint — the DB itself rejects duplicates, no matter what. A `frappe.db.exists()` check in `validate()` is application-level only. Two requests can pass the check at the same time and both slip through. If uniqueness truly matters, enforce it at the DB level.

---

## D1 — Permissions Deep Dive

### List View (`permission_query_conditions`)
For QF Technicians, this should limit the Job Card list to only jobs where they are the assigned technician. Otherwise they'd see everyone's jobs.

### Document Access (`has_permission`)
For Service Invoice, non-managers should be blocked from viewing if the linked Job Card's `payment_status` isn't "Paid".

### Safe vs Unsafe Whitelisted Methods
- `frappe.get_all` — **bypasses permissions**. Never use it in a method accessible to low-privilege or guest users.
- `frappe.get_list` — **permission-aware**. Use this instead.
- Also strip sensitive fields like `customer_phone` and `customer_email` for non-manager users before returning data.

### `frappe.share` and `frappe.only_for`


```python
@frappe.whitelist()
def share_job_card(job_card_name,user_email):
    frappe.share.add("Job Card", job_card_name, user_email, read=1)
    return "Job Card shared with {}".format(user_email)
```

`frappe.only_for("QF Manager")` immediately throws a `frappe.PermissionError` if the calling user doesn't have that role. Nothing below that line runs.

### `frappe.get_doc_permissions()` output

## E1 — Job Card Lifecycle Logic

Here's what should happen at each stage:

| Hook | What it does |
|---|---|
| `validate()` | Check phone is 10 digits. If status is "In Repair" or later, technician must be assigned. Compute `total_price` per part row. Sum to `parts_total`. Load `labour_charge` from settings if empty. Set `final_amount = parts_total + labour_charge`. |
| `before_submit()` | Only allow submission if status is "Ready for Delivery". Check stock availability per part. |
| `on_submit()` | Deduct stock. Create Service Invoice with `ignore_permissions=True`. Publish realtime event `job_ready`. Enqueue the email (don't block submit on it). |
| `on_cancel()` | Set status to "Cancelled". Restore part stock. Cancel linked Service Invoice if one exists. |
| `on_trash()` | Block deletion unless doc is Draft or Cancelled. |
| `on_update()` | **Never call `self.save()` here.** Use helper methods like `recalculate_amounts()`. |

### Why `ignore_permissions=True` on submit

Stock deduction and Service Invoice creation during `on_submit` are system-initiated actions — the app is doing this automatically, not the user clicking a button. The user may not have write permission on Spare Part or Service Invoice, but the system still needs to act. `ignore_permissions=True` is acceptable here because the action is controlled and intentional, not user-driven.

### The `on_update()` Recursion Pitfall

Calling `self.save()` inside `on_update()` triggers another save, which fires `on_update()` again, which calls `self.save()` again — infinite loop until a crash. Instead, use helper methods that only update `self` fields in memory:

```python
def on_update(self):
    self.recalculate_amounts()  # updates self.final_amount etc. — no save()

def recalculate_amounts(self):
    self.parts_total = sum(r.total_price for r in self.parts_used)
    self.final_amount = self.parts_total + (self.labour_charge or 0)
```

```python

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
```

---

## E2 — autoname & Renaming

### `autoname()` on Spare Part

```python
def autoname(self):
    self.part_code = self.part_code.upper()
    self.name = make_autoname("PART-.YYYY.-.####")
```

This runs before the document is saved for the first time. Uppercasing first means the naming series always works off a clean, consistent code.

### `merge=True` danger

`merge=True` in `rename_doc` combines two separate records into one. Any data unique to the old record is silently lost. Only use it if you are 100% certain the two records are truly duplicates and you are okay with merging their histories.

---

## E3 — Override Strategies

### Method Resolution Order (MRO)

When Python looks up a method on a class, it follows the MRO — it checks the subclass first, then the parent, then the grandparent. Always call `super().validate()` inside your override so the parent class's checks still run. If you skip it, you silently break all the logic the parent class had.

### `override_doctype_class` vs `doc_events`

Use `doc_events` for most things — it hooks into lifecycle events without replacing the class, multiple apps can attach to the same event safely, and it's fully reversible on uninstall.

Use `override_doctype_class` only when you need to change how an existing method actually works — not just react to it. It's more invasive because it swaps the whole controller class.

### Upgrade friction

If Frappe updates `Job Card`'s `validate()` to add a new internal check and you've overridden the class, your `super()` call pulls in that new check automatically — which is good. But if you forget `super()` entirely, that new check never runs and you won't even know. Always call `super()` first.

### `frappe.db.get_value` vs `frappe.get_doc` for single fields

```python
# Expensive — loads the entire document
doc = frappe.get_doc("QuickFix Settings", "QuickFix Settings")
threshold = doc.low_stock_threshold

# Cheap — fetches only the field you need
threshold = frappe.db.get_value("QuickFix Settings", None, "low_stock_threshold")
```

Use `frappe.db.get_value` when you only need one or two fields. Loading the full doc just to read one value is wasteful.


```python

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
```

---

## F1 — doc_events: Wildcards & Multiple Handlers

### Wildcard handler

Adding `"*"` as the DocType key in `doc_events` hooks into every DocType's events. Useful for audit logging — every save, submit, or cancel across the whole app goes through one handler.

### Handler order

When both a controller method and a `doc_events` handler are registered for the same event (e.g., `validate` on Job Card), the controller method runs first, then the `doc_events` handler. If the controller raises a `frappe.ValidationError`, the `doc_events` handler never runs.

If both raise an error, only the first error reaches the user — the second never fires.

### `"*"` plus a specific DocType handler

Both run. The wildcard handler and the specific DocType handler are independent. Registering both for the same event means both execute — wildcard first, then the specific one.

---

## F2 — Install, Boot & Session Hooks

### `after_install`

Runs once when the app is installed. Use it to create default data and settings. Don't make it do anything that could break if run twice — always check if the record already exists before creating it.

### `before_uninstall`

Runs before the app is removed. Use it as a safety guard — if submitted Job Cards exist, block the uninstall with a clear error. You don't want someone accidentally wiping a live system.

### `extend_bootinfo`

Adds data to the global boot object sent to the browser on login. Anything you put in `bootinfo` is accessible in JS as `frappe.boot.your_key`. Use it for app-wide settings the frontend needs at startup.

### `on_session_creation` and `on_logout`

These fire when a user logs in or logs out. Good place to write audit log entries for session tracking.


```python

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

```

---

## F3 — Frontend Hooks

| Hook | Where it loads |
|---|---|
| `app_include_js` | Desk only (logged-in users) |
| `web_include_js` | Website/Portal (public-facing) |
| `doctype_js` | Form view — field logic, actions, validation |
| `doctype_list_js` | List view — indicators, filters, list actions |

`app_include_js` is for backend UI customization — things like custom buttons or form logic on the Desk. 
`web_include_js` is for public-facing features, Web Forms, and the customer portal.

**Tree view** (`doctype_tree_js`) applies to DocTypes with parent-child hierarchical relationships — like Account, Warehouse, or Item Group. Not applicable to Job Card or Technician.

After any JS/CSS changes, run `bench build --app quickfix`. This rebundles assets and generates hashed filenames so browsers load the new version instead of the old cached one.

### Jinja Templates

**Print Formats** automatically get `doc`, `meta`, and `frappe` in context. Tied to a specific document — good for PDFs.

**Web Pages** do NOT automatically get `doc`. You have to pass data from the backend or fetch it explicitly. They are not the same context.

### Website Routes

```python
# hooks.py
website_route_rules = [{"from_route": "/track-job", "to_route": "track-job"}]
portal_menu_items = [{"title": "Track My Job", "route": "/track-job", "role": "Guest"}]
```

---

## F4 — `override_whitelisted_methods`

### Hook-based override vs Monkey Patching

| | `override_whitelisted_methods` | Monkey Patching |
|---|---|---|
| Where declared | `hooks.py` — visible to everyone | Somewhere at import time — invisible |
| Reversible | Yes — uninstall the app | No — affects the whole process |
| Scope | API endpoint only | Entire Python process |
| Safe for multi-app bench | Yes | Dangerous |
| Debuggable | Easy | Very hard |

Use `override_whitelisted_methods` when you need to replace a Frappe API endpoint cleanly. Use monkey patching only as a last resort in isolated, emergency situations.

### What happens when two apps override the same method

The last app installed wins — silently. The earlier app's override stops working with no error or warning. If you're App B, chain to App A's override instead of replacing it entirely.

### Signature mismatch — `TypeError`

Your override must have the exact same parameters as the original function. If you're missing a parameter, have the wrong name, or added a required parameter without a default, Python will throw a `TypeError` when the original caller passes arguments your function doesn't expect.

Always check the original signature first:
```python
import inspect
from frappe.client import get_count
print(inspect.signature(get_count))
```

Then match it exactly in your override.


```python

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
```

---

## F5 — Fixtures & Property Setters

### What are Fixtures?

Fixtures are just configuration data that travels with your app. Instead of manually creating Custom Fields, Roles, or Workspaces on every new site, you export them once as JSON files and Frappe applies them automatically on install.

### Setting up `hooks.py`

```python
fixtures = [
    "Role",
    "Workspace",
    {"dt": "Custom Field", "filters": [["module", "=", "Quickfix"]]},
    {"dt": "Property Setter", "filters": [["module", "=", "Quickfix"]]},
    {"dt": "Device Type"},
    {"dt": "QuickFix Settings"},
]
```

Then export:
```bash
bench --site your-site export-fixtures --app quickfix
```

Always use `--app quickfix` so you only export your app's data, not everything on the site. Commit the generated `fixtures/` folder to Git.

### Making the `remarks` Field Bold via `after_install`

`after_install` runs once when your app is installed. It's the right place for one-time setup like this.

In `hooks.py`:
```python
after_install = "quickfix.setup.after_install"
```

In `quickfix/setup.py`:
```python
def after_install():
    frappe.make_property_setter({
        "doctype": "Job Card",
        "fieldname": "remarks",
        "property": "bold",
        "value": "1",
        "property_type": "Check"
    })
    frappe.db.commit()
```

`make_property_setter` overrides a field's metadata without touching the core DocType. The original is untouched — your change just layers on top.

### Fieldname Collision Risk

If your Custom Field uses the same name as a field Frappe adds in a future update, things break quietly — migrations crash, data gets overwritten, or two pieces of logic share one column with no warning.

Fix: always prefix with your app name. `status` becomes `qf_status`, `remarks` becomes `qf_remarks`. You can't predict what Frappe will add later, so the prefix keeps you safe.

### Patching Order

If Patch 1 creates a Custom Field and Patch 2 reads from it, they must be separate entries in `patches.txt`. Here's why:

```
Patch 1 runs  →  creates the Custom Field record in the DB
bench migrate →  sees the new field → adds the actual DB column
Patch 2 runs  →  column exists → reads it safely 
```

If you merge them into one patch, Patch 2 runs before `bench migrate` ever gets a chance. The column doesn't exist yet and it crashes. The migration only happens between separate patch entries, not inside a single one.

One patch, one concern. Never combine field creation and field usage in the same patch.

---

## G1 — Safe Monkey Patching

Monkey patching is a last resort. Document it like a warning label on something dangerous.

### The `_qf_patched` guard

Without this flag, every worker restart re-patches an already-patched function. The "original" variable now points to the patched version — so calling it calls itself, causing infinite recursion and a crash. The guard checks if the patch was already applied and skips it if so.

```python
if hasattr(fu, "_qf_patched"):
    return  # already patched, don't do it again
```

### Why `monkey_patches.py` and not `__init__.py`

`__init__.py` runs every time Python imports your module — including during tests, during bench commands, and before Frappe is fully ready. Patches applied there are invisible, untraceable, and affect everything.

`monkey_patches.py` is a single dedicated file. It's called explicitly from a controlled hook, easy to find, easy to disable, and each patch can be independently guarded. New developers know exactly where to look.

### The escalation path

Always try the least invasive option first:

1. **`doc_events`** — hook into lifecycle events. Zero risk, fully reversible.
2. **`override_doctype_class`** — subclass the controller. Clean, uses `super()`.
3. **`override_whitelisted_methods`** — replace an API endpoint via `hooks.py`. Explicit and visible.
4. **Monkey patch** — last resort only. Document WHY, use the guard, isolate in one file.

Each step up adds more risk and less reversibility. Don't skip levels.

```python
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
```

---

## Common Pitfalls

**Fieldname collisions** — don't use generic names like `status` or `priority`. Prefix with `qf_` (e.g., `qf_status`) to avoid future conflicts with Frappe core fields.

**Patch ordering** — never merge a patch that creates a custom field with one that reads from it. They must be separate patches. The migration runs between them to actually add the DB column.

**`frappe.db.exists()` race condition** — an exists check in `validate()` is application-level only. Two requests can pass the check simultaneously. If uniqueness truly matters, add a `unique` constraint at the DocType field level so the database enforces it.

**`frappe.get_all` in guest-accessible methods** — this skips all permission checks. Don't do it. Use `frappe.get_list`.

**`self.save()` inside `on_update()`** — causes infinite recursion. Never do it. Use helper methods that update `self` fields in memory only.

**`merge=True` in `rename_doc`** — merges two records and destroys data from one of them. Use `merge=False` unless you are absolutely certain.

---

## Async Client-Side Patterns

**`frappe.call()` inside `validate` or `before_save`** — avoid this pattern. `frappe.call()` is asynchronous, so the save flow does not wait for the server response before continuing. This can lead to documents getting saved before the validation result returns. Validation logic that must block saving should always be done in the Python `validate()` method on the server side.

**Using `onload` or `refresh` for async fetches** — this is the correct place for asynchronous calls. These events are part of the UI lifecycle and are safe for fetching extra data, updating indicators, filtering dropdowns, or showing alerts. Since they are not part of the critical save transaction, the form can continue loading while the server response arrives in the background.

## Tree DocType

A Tree DocType is used to store hierarchical parent-child records.

Examples:
- Account hierarchy
- Employee hierarchy

`doctype_tree_js` is used to customize the frontend behavior of the tree view.

Tree DocTypes require:
- `parent_field` → stores parent record reference
- `is_group` → identifies whether the record can contain child records


## Client Script DocType vs Shipped JS

Client Script DocType stores JavaScript directly in the database. It is useful for quick customizations because changes apply immediately without deploy, migrate, or bench build.

Shipped JS files are stored inside the app codebase and loaded using hooks.py. These are version controlled and safer for long-term production maintenance.

Consultants often prefer Client Script DocType because:
- fast customization
- no server access needed
- no deployment required

App developers usually prefer shipped JS because:
- version control support
- easier debugging
- proper code review
- deployment consistency
- safer production management

Risks of Client Script DocType in production:
- code stored only in DB
- difficult to track changes
- easy to overwrite accidentally
- no proper git history
- difficult multi-site maintenance

## JS Hide is NOT Security

Hiding a field using JavaScript only affects the frontend UI.

Example:

```javascript
frm.set_df_property("customer_phone", "hidden", 1)