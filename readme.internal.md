
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
```

## SQL QUERY - F-STRING VS PARAMETERIZED QUERIES

Using f-strings directly inside SQL queries is unsafe because user input becomes part of the SQL query itself.
Example:

```python

pythonquery = f"""
SELECT *
FROM `tabJob Card`
WHERE device_type = '{device_type}'
"""
```

If a malicious value is passed by the user, the query can be manipulated and may expose unintended records. This is called SQL Injection.
The safer approach is to use parameterized queries.
Example:

```python

pythonquery = """
SELECT
    name,
    customer_name,
    device_type,
    status,
    assigned_technician,
    estimated_cost,
    creation
FROM `tabJob Card`
WHERE status NOT IN ('Delivered', 'Cancelled')
AND (
    %(device_type)s = ''
    OR device_type = %(device_type)s
)
"""

frappe.db.sql(query, {
    "device_type": device_type
})

```
In the parameterized pattern, the SQL query and the user input are handled separately. The database treats the value only as data instead of executable SQL, which prevents SQL Injection and escaping problems.

## Prepared Report vs Real-time Script Report

Real-time Script Reports run the query every time the user opens the report. This gives the latest live data but can become slow for very large datasets.

Prepared Reports generate the report in the background and store the result. Users later see the already generated report, so loading becomes much faster.

Real-time Script Reports are useful for:
- live data
- current status monitoring
- small or medium datasets

Prepared Reports are useful for:
- large datasets
- heavy calculations
- analytics and summary reports

## Staleness Tradeoff

Prepared Reports may show old data because the result is cached.

Example:
- report prepared at 10 AM
- new records added at 11 AM
- user still sees old report data until the report is prepared again

This improves performance but may not always show the latest database changes.

## Caching Risk

If underlying data changes after the report is prepared, users continue seeing the old cached result.

Examples:
- new Job Cards may not appear
- updated stock values may not appear
- changed revenue totals may still show old values

## Report Builder vs Script Report

Report Builder is useful for simple reports where users only need basic filtering, sorting, grouping, and selecting columns without writing code. It is suitable for quick business reports and small datasets.

Examples:
- Customer History report
- simple Job Card listings
- basic filtering reports

Script Reports should be used when the report requires custom Python logic, calculations, charts, summaries, dynamic columns, conditional formatting, or complex business rules.

Examples:
- Technician Performance Report
- inventory analytics
- revenue calculations
- dynamic device type columns

Using Report Builder in production can become a mistake when the report requires heavy calculations or advanced logic. For example, creating a large technician analytics report using only Report Builder would be difficult to maintain, slow for large datasets, and unable to support charts, summaries, or custom calculations properly.

In such cases, Script Reports are the correct solution because they provide full backend control and better scalability.

## Multi-language Printing

Frappe determines the print language based on the current user's selected language.  
All strings wrapped using:

{{ _("text") }}

are passed through Frappe’s translation engine.

If a translation exists, the translated text is shown. Otherwise, the original English text is used.

---

## Using frappe.get_all() Directly Inside Jinja

Example:

{% set data = frappe.get_all("Spare Part") %}

This is not recommended because:
- database queries inside templates slow down rendering
- business logic gets mixed with UI code
- templates become harder to maintain

---

## Better Pattern - Precompute Data

Better approach:

Prepare data in Python before rendering.

Example:

def before_print(self):
    self.precomputed_field = "value"

Then use in template:

{{ doc.precomputed_field }}

Advantages:
- faster rendering
- cleaner templates
- easier debugging
- better separation of logic and UI


## Raw Printing vs HTML PDF Rendering

Raw printing sends ESC/POS commands directly to thermal printers. It is fast and mainly used for receipt printers.

Frappe HTML-PDF rendering uses HTML/CSS templates rendered through WeasyPrint to generate PDFs. This supports rich layouts, tables, images, and styling.

---

## CSS Limitations in WeasyPrint

Some CSS properties supported in browsers may fail in WeasyPrint, including:

- position: sticky
- backdrop-filter
- flex gap

WeasyPrint does not fully support all modern browser CSS features.

---

## Thermal Print Format

A second minimal print format was created for 80mm thermal printers.

It contains:
- Job Number
- Customer Name
- Final Amount

This layout is optimized for narrow receipt printers.

---

## Numeric Formatting

Numeric and currency values are formatted using:

frappe.utils.fmt_money()

Without formatting:
1105

With formatting:
₹ 1,105.00

This improves readability and ensures proper currency formatting.

## Background Job Queues

Frappe uses background workers and Redis queues to execute long-running tasks asynchronously using frappe.enqueue().

### Queue Types

1. short
Used for quick tasks like emails, notifications, and small updates.

2. default
Used for normal background jobs with medium execution time.

3. long
Used for heavy tasks like report generation, exports, backups, and batch processing.

Using separate queues prevents small jobs from waiting behind heavy jobs.

---

## Why Background Jobs Are Used

Background jobs improve user experience by moving slow operations outside the request-response cycle.

Instead of making the user wait, tasks are processed asynchronously by workers.

---

## Email Sending Internals

When frappe.enqueue() is used for sending emails:

1. Job is added to Redis queue.
2. Background worker picks the task.
3. frappe.sendmail() connects to SMTP server.
4. Email is sent asynchronously.

This prevents UI delays during user actions.


## Idempotency in Background Jobs

Background jobs may accidentally run multiple times due to scheduler retries, crashes, or duplicate worker execution.

To prevent duplicate processing, an idempotency guard is used.

Before executing the low stock check job, the system checks whether the job has already run today using an Audit Log entry.

If a log already exists, the function returns immediately without executing again.

This ensures:
- duplicate emails are avoided
- duplicate stock processing is prevented
- scheduler retries remain safe

Idempotency ensures the same operation produces the same final result even if executed multiple times.

## Long-running Jobs with Progress Updates

Heavy background jobs such as report generation may take several minutes to complete.

To improve user experience, realtime progress updates are sent using:

frappe.publish_progress()

During report generation, each processed month updates the progress percentage and status message.

Internally:

Background Job
→ publish_progress()
→ Realtime WebSocket event
→ Browser UI updates progress bar

## Frappe retry a failed background job by default

This prevents users from thinking the system is stuck during long-running operations.

By default, Frappe does not automatically retry failed background jobs.

If a job fails, it is immediately moved to RQ Failed Job and the traceback is stored in Error Log.

This prevents dangerous duplicate operations such as repeated emails, payments, or stock updates.

Retries must be explicitly configured when needed.

## Scheduler Events

Frappe uses scheduler_events in hooks.py to run automatic background jobs.

### Daily Scheduler

The low stock check job is registered under:

"daily"

This runs automatically once per day.

### Cron Scheduler

Monthly revenue report generation uses cron format:

"0 2 1 * *"

Meaning:
- minute = 0
- hour = 2
- day = 1

This runs at 2:00 AM on the 1st day of every month.

---

## Disabling Scheduler Per Site

Scheduler can be disabled for a specific site using:

bench --site sitename set-config pause_scheduler 1

This is useful in development environments to prevent:
- accidental emails
- repeated test jobs
- unfinished background tasks

---

## Worker Downtime Behavior

If workers are down, scheduled jobs remain queued in Redis.

When workers come back online, they continue processing pending jobs from the queue.

This allows temporary worker downtime without immediately losing scheduled jobs.



# N+1 PROBLEM - fix this

job_cards = frappe.get_all("Job Card", fields=["name","assigned_technician"])
    for jc in job_cards:
        tech = frappe.get_doc("Technician", jc.assigned_technician)
        print(tech.technician_name, tech.phone)

Correcter version- 

```python
    jobcards = frappe.get_all(
    "Job Card",
    fields=["name", "assigned_technician"]
    )

    technician_list = []

    for jc in jobcards:

        technician_list.append(
            jc.assigned_technician
        )

    technicians = frappe.get_all(
        "Technician",

        filters={
            "name": ["in", technician_list]
        },

        fields=["name", "phone_number"]
    )

```

##  Task B - Bulk operations:


Bulk update of 1000 draft records

```python
import frappe

def bulk_cancel_old_drafts():

    frappe.db.sql("""

        UPDATE `tabJob Card`

        SET status = 'Cancelled'

        WHERE status = 'Draft'

    """)
```

## PART 2 — Bulk INSERT

Requirement:

Insert 500 Audit Logs using bulk_insert()


```python
import frappe

def bulk_insert_audit_logs():

    logs = []

    for i in range(500):

        logs.append(
            (
                f"LOG-{i}",
                "low_stock_check"
            )
        )

    frappe.db.bulk_insert(

        "Audit Log",

        fields=[
            "name",
            "action"
        ],

        values=logs

    )

```

While comparing both slow and fast verison the final result will be

bulk_insert() and single SQL UPDATE are significantly faster
because they reduce multiple database round trips.
---

## Indexing

Indexes improve query performance by allowing the database to quickly locate matching rows without scanning the full table.

However, indexes should only be added to fields frequently used in:
- filters
- searches
- joins
- reports

Over-indexing is harmful because every INSERT, UPDATE, and DELETE operation must also update all indexes.

Too many indexes increase:
- write overhead
- storage usage
- memory consumption
- migration time

Therefore, indexes should be added carefully only where query optimization is needed.
---
## Report Performance Profiling

SQL logging was enabled in site/quickfix-dev.localhost/site_config.json to inspect queries generated during report execution.

After running the Technician Performance Report, the executed SQL queries were inspected from the logs.

The slowest query involved filtering Job Cards using assigned_technician.

To optimize performance, an index was added to the assigned_technician field using the field's Index option and bench migrate.

This reduced full table scans and improved query lookup performance.

cmd - `tail -f logs/frappe.log`

---
## REST Resource API & Custom API

GET /api/resource/Job Card - list Job Cards (use session cookie from browser)

request - http://localhost:8001/api/resource/Job%20Card/

reponse -

```python
{
    "data": [
        {
            "name": "JC-2026-00002"
        },
        {
            "name": "JC-2026-00004"
        },
        {
            "name": "JC-2026-00005"
        },
        {
            "name": "JC-2026-00006"
        },
        {
            "name": "JC-2026-00003"
        },
        {
            "name": "JC-2026-00007"
        },
        {
            "name": "JC-2026-00001"
        },
        {
            "name": "JC-2026-00008"
        },
        {
            "name": "JC-2026-00011"
        },
        {
            "name": "JC-2026-00010"
        },
        {
            "name": "JC-2026-00009"
        },
        {
            "name": "JC-2026-00012"
        },
        {
            "name": "JC-2026-00013"
        },
        {
            "name": "JC-2026-00014"
        },
        {
            "name": "JC-2026-00015"
        }
    ]
}
```
---
GET /api/resource/Job Card/JC-0001 - single doc

request - http://localhost:8001/api/resource/Job%20Card/JC-2026-00002

```python
resposne -

{
    "data": {
        "name": "JC-2026-00002",
        "owner": "Administrator",
        "creation": "2026-04-30 12:57:46.286143",
        "modified": "2026-04-30 12:57:49.206188",
        "modified_by": "Administrator",
        "docstatus": 1,
        "idx": 0,
        "customer_name": "Ram",
        "customer_phone": "9876543210",
        "device_type": "Smartphone",
        "problem_description": "<div class=\"ql-editor read-mode\"><p>test</p></div>",
        "assigned_technician": "TECH-NEW",
        "estimated_cost": 0.0,
        "priority": "Normal",
        "parts_total": 0.0,
        "labour_charge": 500.0,
        "final_amount": 0.0,
        "payment_status": "Unpaid",
        "status": "Draft",
        "doctype": "Job Card",
        "parts_usage": []
    }
}

```
---
POST /api/resource/Spare Part - create a part

request - http://localhost:8001/api/resource/Spare%20Part

response - 

```python

{
    "data": {
        "name": "si2q16uvik",
        "owner": "Administrator",
        "creation": "2026-05-18 13:48:53.088884",
        "modified": "2026-05-18 13:48:53.088884",
        "modified_by": "Administrator",
        "docstatus": 0,
        "idx": 0,
        "part_name": "Cable",
        "unit_cost": 100.0,
        "selling_price": 150.0,
        "stock_qty": 10.0,
        "reorder_level": 5.0,
        "is_active": 1,
        "doctype": "Spare Part"
    }
}

```
---
PUT /api/resource/Spare Part/PART-0001 - update a field

request - http://localhost:8001/api/resource/Spare%20Part/si2q16uvik

response -

```python

{
    "data": {
        "name": "si2q16uvik",
        "owner": "Administrator",
        "creation": "2026-05-18 13:48:53.088884",
        "modified": "2026-05-18 15:20:40.374804",
        "modified_by": "Administrator",
        "docstatus": 0,
        "idx": 0,
        "part_name": "Cable wire",
        "unit_cost": 100.0,
        "selling_price": 140.0,
        "stock_qty": 11.0,
        "reorder_level": 5.0,
        "is_active": 1,
        "doctype": "Spare Part"
    }
}

```
---
DELETE /api/resource/Spare Part/PART-0001 - delete it

request - http://localhost:8001/api/resource/Spare%20Part/si2q16uvik

response - 

```python
{
    "data": "ok"
}
```

---

## Difference between session cookie auth and token auth

Session cookie authentication uses the browser login session and stores a session cookie (sid) to identify the user. It is mainly used for browser-based applications and requires CSRF protection.

Token authentication uses an API key and API secret sent in the Authorization header. It does not depend on browser sessions or CSRF tokens and is mainly used for server-to-server communication and external API integrations.

---

## Rate limiting & abuse protection

allow_guest=True endpoints are publicly accessible without login, so they can be abused if not protected properly.

Common risks:

Brute force attacks - attackers repeatedly try different inputs to fetch data.
API spam / DDoS - too many requests can slow down or crash the server.
Data leakage - sensitive customer information may become publicly accessible.

A simple rate limiter was implemented using frappe.cache() to track request count per IP address per minute and block requests exceeding the limit.

---
## Incoming webhook Endpoint

Why use hmac.compare_digest() instead of == ?

hmac.compare_digest() prevents timing attacks. Normal == comparison may reveal partial matching information based on execution time, allowing attackers to guess the signature gradually.

Deduplication Strategy

Payment gateways may resend the same webhook event multiple times due to retries or network issues. Before processing payment, the system checks Audit Log for an existing payment record using the same reference number. If the event was already processed, the webhook returns a duplicate response and skips updating payment again


## Server Script Sandbox Analysis

### What Python functions/modules are blocked in Server Scripts?

Server Scripts run inside a restricted sandbox for security reasons. Dangerous modules and functions such as `os`, `sys`, `subprocess`, file operations, shell execution, and unrestricted imports are blocked.

---

### 3 Things You Cannot Do in Server Scripts

1. Access the server file system directly.
2. Execute shell/terminal commands.
3. Install or import arbitrary external Python packages.

---

### When Server Scripts Are Acceptable

1. Small business rule automations like field updates or validations.
2. Simple scheduled tasks or lightweight internal APIs.

---

### When App Code Should Be Preferred

1. Complex business logic and large workflows.
2. Integrations, background jobs, or performance-critical features.

---

### Governance / Maintainability Risk

Server Scripts are stored in the database instead of version-controlled app files. This makes tracking changes, code reviews, debugging, testing, and deployment management more difficult. Large usage of Server Scripts can lead to poor maintainability and hidden business logic.

## Frappe uses Redis caching to improve performance and reduce repeated database queries.

Common cached items include:
1. Bootinfo
2. DocType metadata
3. Website context
4. Translations
5. User permissions

Running frappe.clear_cache() clears cached data and forces the browser and backend to reload fresh information.

## Debugging Stale UI

### Old JS still showing after frontend changes

After modifying JavaScript files, the browser may continue using old bundled assets from cache.

To rebuild frontend assets:

```bash
bench build --app quickfix

```
This command rebuilds the app's JS/CSS bundles and updates static assets.

### To clear cached assets completely:

After changing a DocType, metadata cache can be cleared using:
```bash
bench clear-cache

    or

frappe.clear_cache()
```


## Production Debugging Without developer_mode

If a bug occurs only in production, debugging can be done using Error Logs, Audit Logs, and structured logger output.

1. First check Error Log records to identify:
   - exception type
   - traceback
   - failing method
   - affected document or API

2. Use Audit Log records to trace user actions and system events before the failure. This helps identify what operation triggered the issue.

3. Use `frappe.logger()` output from application logs to track execution flow, request data, retries, warnings, and background job behavior.

4. Correlate timestamps between:
   - Error Log
   - Audit Log
   - logger output

   to reconstruct the sequence of events leading to the bug.

5. Add additional temporary structured logging in suspicious areas to gather more production-specific information without enabling developer_mode.

This approach allows safe production debugging without exposing sensitive debugging features to end users.


## Ignore_permissions analysis

Problem 1 — Anyone Can Access All Data

* allow_guest=True means no login needed.
* ignore_permissions=True means no permission check. 

Together — literally anyone in the world can call this URL and get all your customer data.

# Always ask these 3 questions before using ignore_permissions

 1. Is there a logged in user here?
 2. Is this a guest accessible endpoint?
 3. Is this really a system action?

# Only use ignore_permissions when:

- It is a background job
- It is a webhook from external system
- No user input is involved
- It is purely system generated data

## Private vs public files

Upload a test file as a private attachment on a Job Card

```python

# bench --site quickfix-dev.localhost console

with open("/home/frappe/test.pdf", "rb") as f:
    content = f.read()

file_doc = frappe.get_doc({
    "doctype": "File",
    "file_name": "test.pdf",
    "attached_to_doctype": "Job Card",
    "attached_to_name": "JC-2026-00001",
    "is_private": 1,        # This makes it private
    "content": content
})
file_doc.insert()
frappe.db.commit()
print(file_doc.file_url)

```

this enables the private method

if we access using this `/files/filename.pdf directly`  it show the result as `404 Not Found`

if we use `/private/files/filename.pdf` 
if
    user have no permission - `403 Forbidden — No permission`

if user have permission 
    result - `File downloads successfully`

## Secrets management

The issues with API key hardcoded in Python source code

problem - if we push the code to github or host some where means anyone can see our api Key and use it, this is very bad practise of hard coding the api Key

Public = Anyone can open the link(`Shop logo , sales price`)
Private = Only authorized person can open the link (`Customer ID , Customer invoice , repair photo`)

```python
def payment_webhook():
    api_key = frappe.conf.get("payment_api_key")
    
    if not api_key:
        frappe.throw("Payment API key not configured")
    
    requests.post("https://payment.com", headers={
        "Authorization": api_key
    })
```

here key is not in github , key is in yous json so the api key is safe to use.

1. why should secrets NEVER be in common_site_config.json
ans - because this also a public acess file anyone can seen our api Key that's what we should never use secrets in common_site_config.json


2. what is the risk of committing site_config.json to git?

Risk 1 — Database password is exposed
Risk 2 — Payment API key is exposed
Risk 3 — Git history never forgets
Risk 4 — Encryption key is exposed

to avoid these risk use-

```bash
nano .gitignore
```


## Debugging Email Failures

When an email fails to send, the following should be checked:

1. Email Queue
   - Check the email status:
     Not Sent,
     Sent,
     Error
   - Inspect:
     recipients,
     subject,
     error field
   - Verify whether the email was queued correctly.

2. SMTP Logs / frappe.log
   - Check logs/frappe.log for:
     SMTP authentication failures,
     invalid credentials,
     connection refused,
     timeout errors
   - These logs help identify mail server issues.

3. Error Log
   - Open Setup → Error Log
   - Check traceback and exception details related to sendmail or email queue processing.
   - Useful for debugging unexpected backend failures.

Typical email failure causes include:
- invalid recipient email
- missing SMTP configuration
- wrong email password
- blocked SMTP access
- internet/network issues