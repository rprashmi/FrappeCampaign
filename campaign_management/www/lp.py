import frappe
from campaign_management.api import serve_landing_page

def get_context(context):
    context.no_cache = 1
    # Extract slug from path (e.g. /lp/my-campaign → slug = "my-campaign")
    path = frappe.request.path
    slug = path.split("/lp/")[-1] if "/lp/" in path else None
    if slug:
        context.html = serve_landing_page(slug=slug)
    else:
        frappe.respond_as_web_page("Not Found", "Page not found", http_status_code=404)
    return context
