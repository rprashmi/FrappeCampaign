import frappe
from frappe.model.document import Document

class TrackingOrganization(Document):
    def autoname(self):
        if not self.organization_name or not self.organization_name.strip():
            frappe.throw("Organization Name is required to generate the document name.")

        name = self.organization_name.strip()
        if frappe.db.exists("Tracking Organization", name):
            frappe.throw(
                f"A Tracking Organization named '{name}' already exists. "
                f"Organization names must be unique."
            )
        self.name = name