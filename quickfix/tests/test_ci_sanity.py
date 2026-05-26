import frappe
from frappe.tests.utils import FrappeTestCase


class TestCISanity(FrappeTestCase):
    """
    This test exists specifically to catch CI fixture loading failures
    before the real application tests run. If this test fails it means
    the test environment setup broke — not the application code. Check
    that load_test_fixtures ran successfully and all fixture files exist
    in quickfix/fixtures/test/ before investigating application code.
    """

    def test_environment_sanity(self):
        """
        Verifies that all required fixture data was loaded correctly
        into the test database before application tests run.
        If any assertion here fails, the problem is in CI setup
        not in application code.
        """

        # Check all three Device Types exist
        device_types = ["Mobile", "Laptop", "Tablet"]
        for device_type in device_types:
            self.assertTrue(
                frappe.db.exists("Device Type", device_type),
                f"Device Type '{device_type}' missing — fixture loading failed"
            )

        # Check QuickFix Settings exists and has manager_email
        settings = frappe.get_single("QuickFix Settings")
        self.assertTrue(
            settings.manager_email,
            "QuickFix Settings has empty manager_email — fixture loading failed"
        )

        # Check all three custom Roles exist
        roles = ["QF Service Staff", "QF Technician", "QF Manager"]
        for role in roles:
            self.assertTrue(
                frappe.db.exists("Role", role),
                f"Role '{role}' missing — fixture loading failed"
            )

        # Check Job Card DocType exists and has minimum expected fields
        meta = frappe.get_meta("Job Card")
        field_count = len(meta.fields)
        minimum_fields = 10
        self.assertGreater(
            field_count,
            minimum_fields,
            f"Job Card has only {field_count} fields — expected more than {minimum_fields}"
        )