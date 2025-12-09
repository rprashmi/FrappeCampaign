"""
QuickShop Website APIs - FINAL VERSION
"""
import frappe
from frappe.utils import now, format_datetime
import json
from campaign_management.clients.base import (
    extract_browser_details,
    get_geo_info_from_ip,
    get_or_create_web_visitor,
    link_web_visitor_to_lead,
    add_activity_to_lead,
    get_utm_params_from_data,
    link_historical_activities_to_lead
)


@frappe.whitelist(allow_guest=True, methods=['POST'])
def submit_form(**kwargs):
    """Handle QuickShop form submission - Creates/Updates Lead"""
    frappe.set_user("Guest")
    frappe.flags.ignore_csrf = True

    try:
        # Collect form data
        data = {}
        if frappe.local.form_dict:
            data.update(frappe.local.form_dict)
        if hasattr(frappe.local, 'request') and hasattr(frappe.local.request, 'form'):
            data.update(dict(frappe.local.request.form))
        data.update(kwargs)
        if frappe.local.request.data:
            try:
                json_body = frappe.local.request.get_json(silent=True) or {}
                data.update(json_body)
            except:
                pass

        frappe.logger().info(f"📨 Form submission received")

        # Extract fields
        full_name = (data.get("full_name") or "").strip()
        email = (data.get("email") or data.get("email_id") or "").strip()
        phone = (data.get("phone") or data.get("mobile_no") or "").strip()
        client_id = data.get("ga_client_id") or data.get("client_id")
        cart_items = data.get("cart_items", "")

        # Validation
        if not full_name:
            return {"success": False, "message": "Name is required"}
        if not email and not phone:
            return {"success": False, "message": "Email or Phone is required"}

        # Get tracking info
        user_agent = frappe.get_request_header("User-Agent", "")
        ip_address = frappe.local.request_ip or ""
        page_url = data.get("page_url", "")
        referrer = data.get("referrer", "")

        browser_details = extract_browser_details(user_agent)
        geo_info = get_geo_info_from_ip(ip_address)
        utm_params = get_utm_params_from_data(data)

        geo_location = ""
        if geo_info.get('city') and geo_info.get('country'):
            geo_location = f"{geo_info['city']}, {geo_info['country']}"
        elif geo_info.get('country'):
            geo_location = geo_info['country']

        # Build tracking data
        full_client_data_str = data.get("full_client_data")
        if full_client_data_str:
            try:
                client_data_obj = json.loads(full_client_data_str)
            except:
                client_data_obj = {}
        else:
            client_data_obj = {}

        complete_tracking_data = {
            "browser": client_data_obj.get("browser", {
                "browser_name": browser_details['browser'],
                "os_name": browser_details['os'],
                "device_type": browser_details['device']
            }),
            "geo": {
                "country": geo_info.get('country'),
                "city": geo_info.get('city'),
                "ip_address": ip_address
            },
            "client_data": client_data_obj.get("client_data", {}),
            "submission_timestamp": now(),
            "cart_items": cart_items
        }

        # ✨ Check/Create Organization
        org_name = "QuickShop"
        if not frappe.db.exists("CRM Organization", org_name):
            org = frappe.get_doc({
                "doctype": "CRM Organization",
                "organization_name": org_name,
                "website": "http://localhost:8001"
            })
            org.insert(ignore_permissions=True)
            frappe.db.commit()
            frappe.logger().info(f"✅ Created organization: {org_name}")

        # Check for existing lead
        existing_lead = None
        if client_id:
            existing_lead = frappe.db.get_value(
                "CRM Lead", {"ga_client_id": client_id},
                ["name", "email", "mobile_no"], as_dict=True
            )
        if not existing_lead and email:
            existing_lead = frappe.db.get_value(
                "CRM Lead", {"email": email},
                ["name", "email", "mobile_no"], as_dict=True
            )

        if existing_lead:
            # UPDATE EXISTING LEAD
            lead = frappe.get_doc("CRM Lead", existing_lead.name)

            if email and not lead.email:
                lead.email = email
            if phone and not lead.mobile_no:
                lead.mobile_no = phone
            if client_id and not lead.ga_client_id:
                lead.ga_client_id = client_id
            if not lead.organization:
                lead.organization = org_name

            lead.add_comment("Info", f"🔄 Form Resubmission<br>Cart: {cart_items or 'Empty'}")
            lead.save(ignore_permissions=True)

            # Add activity
            add_activity_to_lead(lead.name, {
                "activity_type": "📝 Form Resubmission",
                "page_url": page_url,
                "product_name": cart_items,
                "timestamp": now(),
                "browser": f"{browser_details['browser']} on {browser_details['os']}",
                "device": browser_details['device'],
                "geo_location": geo_location,
                "referrer": referrer,
                "client_id": client_id,
                **utm_params
            })

            frappe.db.commit()

            return {
                "success": True,
                "message": "Your information has been updated!",
                "lead": lead.name
            }

        else:
            # CREATE NEW LEAD
            name_parts = full_name.strip().split(maxsplit=1)
            first_name = name_parts[0] if name_parts else full_name
            last_name = name_parts[1] if len(name_parts) > 1 else ""

            lead = frappe.get_doc({
                "doctype": "CRM Lead",
                "first_name": first_name,
                "last_name": last_name,
                "email": email if email else None,
                "mobile_no": phone,
                "status": "New",
                "source": "QuickShop Website",
                "website": page_url,
                "organization": org_name,
                "ga_client_id": client_id,
                "utm_source": utm_params.get('utm_source'),
                "utm_medium": utm_params.get('utm_medium'),
                "utm_campaign": utm_params.get('utm_campaign'),
                "full_tracking_details": json.dumps(complete_tracking_data, indent=2)
            })

            lead.insert(ignore_permissions=True)
            frappe.db.commit()

            frappe.logger().info(f"✅ Lead created: {lead.name} with org: {org_name}")

            # Link Web Visitor
            if client_id:
                link_web_visitor_to_lead(client_id, lead.name)
                
                # ✨ NEW: Link all historical activities to this lead
                link_historical_activities_to_lead(client_id, lead.name)

            # Add form submission activity
            add_activity_to_lead(lead.name, {
                "activity_type": "✅ Form Submitted",
                "page_url": page_url,
                "product_name": cart_items,
                "timestamp": now(),
                "browser": f"{browser_details['browser']} on {browser_details['os']}",
                "device": browser_details['device'],
                "geo_location": geo_location,
                "referrer": referrer,
                "client_id": client_id,
                **utm_params
            })

            frappe.db.commit()

            return {
                "success": True,
                "message": "Thank you! Your information has been submitted.",
                "lead": lead.name
            }

    except Exception as e:
        frappe.logger().error(f"❌ Form submission error: {str(e)}")
        frappe.log_error(frappe.get_traceback(), "QuickShop Form Error")
        return {"success": False, "message": f"Error: {str(e)}"}


@frappe.whitelist(allow_guest=True, methods=['POST'])
def track_activity(**kwargs):
    frappe.set_user("Guest")
    frappe.flags.ignore_csrf = True
    try:
        data = {}
        if frappe.local.form_dict:
            data.update(frappe.local.form_dict)
        data.update(kwargs)
        if frappe.local.request.data:
            try:
                json_body = frappe.local.request.get_json(silent=True) or {}
                data.update(json_body)
            except:
                pass

        client_id = data.get("client_id")
        activity_type = data.get("activity_type")
        page_url = data.get("page_url", "")
        product_name = data.get("product_name", "")

        if not client_id or not activity_type:
            return {"success": False, "message": "client_id and activity_type required"}

        frappe.logger().info(f"Tracking: {activity_type} for client: {client_id}")

        user_agent = frappe.get_request_header("User-Agent", "")
        ip_address = frappe.local.request_ip or ""
        referrer = data.get("referrer", "")
        browser_details = extract_browser_details(user_agent)
        geo_info = get_geo_info_from_ip(ip_address)
        utm_params = get_utm_params_from_data(data)
        geo_location = ""
        if geo_info.get('city') and geo_info.get('country'):
            geo_location = f"{geo_info['city']}, {geo_info['country']}"
        elif geo_info.get('country'):
            geo_location = geo_info['country']

        visitor = get_or_create_web_visitor(client_id, data)
        frappe.db.set_value("Web Visitor", visitor.name, "last_seen", now(), update_modified=False)

        lead_name = None
        if visitor.converted_lead:
            lead_name = visitor.converted_lead
            frappe.logger().info(f"Found lead from visitor.converted_lead: {lead_name}")

        if not lead_name and client_id:
            lead_name = frappe.db.get_value("CRM Lead", {"ga_client_id": client_id}, "name")
            if lead_name:
                frappe.logger().info(f"Found existing lead by ga_client_id: {lead_name}")
                link_web_visitor_to_lead(client_id, lead_name)

        if lead_name:
            success = add_activity_to_lead(lead_name, {
                "activity_type": activity_type,
                "page_url": page_url,
                "product_name": product_name,
                "timestamp": now(),
                "browser": f"{browser_details['browser']} on {browser_details['os']}",
                "device": browser_details['device'],
                "geo_location": geo_location,
                "referrer": referrer,
                "client_id": client_id,
                **utm_params
            })
            frappe.db.commit()
            return {
                "success": True,
                "visitor": visitor.name,
                "linked_lead": lead_name,
                "activity_saved": success
            }
        else:
            # No lead yet - store activity linked to Web Visitor
            success = add_activity_to_lead(None, {
                "activity_type": activity_type,
                "page_url": page_url,
                "product_name": product_name,
                "timestamp": now(),
                "browser": f"{browser_details['browser']} on {browser_details['os']}",
                "device": browser_details['device'],
                "geo_location": geo_location,
                "referrer": referrer,
                "client_id": client_id,
                **utm_params
            })
            frappe.db.commit()
            return {
                "success": True,
                "visitor": visitor.name,
                "linked_lead": None,
                "message": "Activity logged, no lead yet",
                "activity_saved": success
            }

    except Exception as e:
        frappe.logger().error(f"Activity tracking error: {str(e)}")
        frappe.log_error(frappe.get_traceback(), "Activity Tracking Error")
        return {"success": False, "message": str(e)}
