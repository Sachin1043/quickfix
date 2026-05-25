import json
import os
import frappe


def load_test_fixtures():
    fixtures_path = os.path.join(
        os.path.dirname(__file__),
        "quickfix",
        "fixtures",
        "test"
    )

    fixture_files = [
        "test_roles.json",
        "device_type.json",
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