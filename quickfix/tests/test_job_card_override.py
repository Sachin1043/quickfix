
import frappe

import unittest

class TestJobCardOverride(unittest.TestCase):

    def test_core_validation_runs(self):

        doc = frappe.get_doc({
            "doctype":"Job Card",
            "priority":"Normal"
        })

        with self.assertRaises(frappe.ValidationError):
            doc.insert()