from quickfix.service_center.doctype.job_card.job_card import JobCard
import frappe

# MRO (Method Resolution Order):
# Python checks methods in this order → Child class → Parent class → Base classes.
#
# Here, CustomJobCard extends JobCard.
# So Python first runs CustomJobCard, then JobCard.
#
# Why super() is important:
# super().validate() calls the original JobCard validation.
#
# If we don't call super():
# - Core validation will be skipped
# - Invalid data may be saved
# - System behavior may break
#
# So calling super() is mandatory.

class CustomJobCard(JobCard):

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