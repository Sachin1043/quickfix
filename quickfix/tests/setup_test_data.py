import json
import os
import frappe


def load_test_fixtures():
    app_path = os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    )
    fixtures_path = os.path.join(app_path, "fixtures", "test")

    fixture_files = [
        "test_roles.json",
        "device_types.json",
        "quickfix_settings.json"
    ]

    for filename in fixture_files:
        filepath = os.path.join(fixtures_path, filename)

        with open(filepath, "r") as f:
            records = json.load(f)

        for record in records:
            doc = frappe.get_doc(record)
            doc.insert(ignore_if_duplicate=True)

        frappe.db.commit()
        print(f"Loaded fixtures from {filename}")