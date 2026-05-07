"""
Simple Form Storage API
Just stores form data - nothing else
"""
import frappe
from frappe.utils import now


@frappe.whitelist(allow_guest=True, methods=['POST'])
def save_form(**kwargs):
    """
    Save form data to database
    Simple storage - no tracking, no complications
    """
    frappe.set_user("Guest")
    frappe.flags.ignore_csrf = True
    
    try:
        # Get data from request
        data = {}
        if frappe.local.form_dict:
            data.update(frappe.local.form_dict)
        
        if hasattr(frappe.local, 'request') and frappe.local.request.data:
            json_body = frappe.local.request.get_json(silent=True)
            if json_body:
                data.update(json_body)
        
        data.update(kwargs)
        
        # Extract form fields
        first_name = str(data.get("firstName") or data.get("first_name") or "").strip()
        last_name = str(data.get("lastName") or data.get("last_name") or "").strip()
        email = str(data.get("email") or "").strip().lower()
        company = str(data.get("company") or "").strip()
        message = str(data.get("message") or "").strip()
        form_type = str(data.get("formType") or data.get("form_type") or "").strip()
        
        # Validation
        if not first_name or not email:
            return {
                "success": False,
                "message": "First name and email are required"
            }
        
        # Create Form Submission record
        form_submission = frappe.get_doc({
            "doctype": "Form Submission",
            "first_name": first_name,
            "last_name": last_name if last_name else None,
            "email": email,
            "company": company if company else None,
            "message": message if message else None,
            "form_type": form_type if form_type else None,
            "created_at": now()
        })
        
        form_submission.insert(ignore_permissions=True)
        frappe.db.commit()
        
        frappe.logger().info(f"✅ Form saved: {form_submission.name} - {email}")
        
        return {
            "success": True,
            "message": "Form submitted successfully",
            "id": form_submission.name
        }
        
    except Exception as e:
        frappe.logger().error(f"Form storage error: {str(e)}")
        frappe.log_error(frappe.get_traceback(), "Form Storage Error")
        return {
            "success": False,
            "message": str(e)
        }
