# Copyright (c) 2024, Your Company and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import cstr

class LandingPage(Document):
    def validate(self):
        """Validate before save"""
        # Auto-generate slug from title if not provided
        if self.title and not self.slug:
            self.slug = self.generate_slug(self.title)
        
        # Validate slug uniqueness
        if self.slug:
            self.validate_slug_unique()
        
        # Generate published URL when status is Published
        if self.status == 'Published':
            if not self.slug:
                frappe.throw("Slug is required to publish the landing page")
            self.published_url = self.generate_published_url()
        else:
            # Clear published URL if not published
            self.published_url = None
    
    def generate_slug(self, text):
        """Generate URL-friendly slug from text"""
        import re
        # Convert to lowercase
        slug = text.lower()
        # Remove special characters
        slug = re.sub(r'[^\w\s-]', '', slug)
        # Replace spaces and multiple hyphens with single hyphen
        slug = re.sub(r'[-\s]+', '-', slug)
        # Remove leading/trailing hyphens
        slug = slug.strip('-')
        return slug
    
    def validate_slug_unique(self):
        """Check if slug is unique"""
        exists = frappe.db.exists({
            'doctype': 'Landing Page',
            'slug': self.slug,
            'name': ('!=', self.name)
        })
        if exists:
            frappe.throw(f"A landing page with slug '{self.slug}' already exists. Please use a different slug.")
    
    def generate_published_url(self):
        """Generate the full published URL"""
        site_url = frappe.utils.get_url()
        return f"{site_url}/lp/{self.slug}"
    
    def on_update(self):
        """After save hook"""
        # If status changed to Published, log it
        if self.has_value_changed('status') and self.status == 'Published':
            frappe.msgprint(f"Landing page published successfully! Live URL: {self.published_url}", 
                          indicator='green', alert=True)


@frappe.whitelist()
def get_landing_page_url(name):
    """Get the published URL for a landing page"""
    doc = frappe.get_doc('Landing Page', name)
    if doc.status == 'Published' and doc.slug:
        return doc.generate_published_url()
    return None
