import frappe
from campaign_management.api import serve_dynamic_form

def get_context(context):
    context.no_cache = 1
    path = frappe.request.path
    slug = path.split("/forms/")[-1] if "/forms/" in path else None
    if slug:
        context.html = serve_dynamic_form(slug=slug)
    else:
        frappe.respond_as_web_page("Not Found", "Form not found", http_status_code=404)
    return context
