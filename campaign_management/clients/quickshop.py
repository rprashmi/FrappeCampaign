"""
QuickShop Website APIs - SERVER-SIDE COMPATIBLE VERSION WITH ENHANCED ERROR HANDLING
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


def get_request_data():
    """Safely extract data from various request formats"""
    data = {}
    
    try:
        # Method 1: form_dict
        if frappe.local.form_dict:
            data.update(frappe.local.form_dict)
            frappe.logger().info(f"📦 Data from form_dict: {json.dumps(data, indent=2)}")
    except Exception as e:
        frappe.logger().error(f"Error reading form_dict: {str(e)}")
    
    try:
        # Method 2: request.form
        if hasattr(frappe.local, 'request') and hasattr(frappe.local.request, 'form'):
            form_data = dict(frappe.local.request.form)
            data.update(form_data)
            frappe.logger().info(f"📦 Data from request.form: {json.dumps(form_data, indent=2)}")
    except Exception as e:
        frappe.logger().error(f"Error reading request.form: {str(e)}")
    
    try:
        # Method 3: JSON body
        if hasattr(frappe.local, 'request') and frappe.local.request.data:
            json_body = frappe.local.request.get_json(silent=True)
            if json_body:
                data.update(json_body)
                frappe.logger().info(f"📦 Data from JSON body: {json.dumps(json_body, indent=2)}")
    except Exception as e:
        frappe.logger().error(f"Error reading JSON body: {str(e)}")
    
    try:
        # Method 4: Raw data (for debugging)
        if hasattr(frappe.local, 'request') and frappe.local.request.data:
            raw_data = frappe.local.request.data
            if isinstance(raw_data, bytes):
                raw_data = raw_data.decode('utf-8')
            frappe.logger().info(f"📦 Raw request data: {raw_data}")
    except Exception as e:
        frappe.logger().error(f"Error reading raw data: {str(e)}")
    
    return data


@frappe.whitelist(allow_guest=True, methods=['POST'])
def submit_form(**kwargs):
    """Handle QuickShop form submission - Creates/Updates Lead"""
    frappe.set_user("Guest")
    frappe.flags.ignore_csrf = True

    try:
        frappe.logger().info("=" * 80)
        frappe.logger().info("📨 FORM SUBMISSION REQUEST RECEIVED")
        frappe.logger().info("=" * 80)

        # Get data from all possible sources
        data = get_request_data()
        data.update(kwargs)

        frappe.logger().info(f"📊 Combined data: {json.dumps(data, indent=2)}")

        # Extract fields - handle both direct values and stringified JSON
        full_name = str(data.get("full_name") or "").strip()
        email = str(data.get("email") or data.get("email_id") or "").strip()
        phone = str(data.get("phone") or data.get("mobile_no") or "").strip()

        # Handle client_id as both string and number
        client_id_raw = data.get("ga_client_id") or data.get("client_id")
        client_id = str(client_id_raw) if client_id_raw else None

        cart_items = str(data.get("cart_items") or "")
        cart_total = data.get("cart_total", 0)
        cta_source = str(data.get("cta_source") or "Direct Visit")

        frappe.logger().info(f"✅ Extracted: name={full_name}, email={email}, phone={phone}, client_id={client_id}")

        # Validation
        if not full_name:
            frappe.logger().error("❌ Validation failed: Name is required")
            return {"success": False, "message": "Name is required"}

        if not email and not phone:
            frappe.logger().error("❌ Validation failed: Email or Phone is required")
            return {"success": False, "message": "Email or Phone is required"}

        # Get tracking info - SERVER-SIDE
        user_agent = str(data.get("user_agent") or frappe.get_request_header("User-Agent", ""))
        ip_address = str(data.get("ip_address") or frappe.local.request_ip or "")
        page_url = str(data.get("page_url") or "")
        referrer = str(data.get("referrer") or "")

        frappe.logger().info(f"🌐 Tracking: UA={user_agent[:50]}..., IP={ip_address}")

        browser_details = extract_browser_details(user_agent)
        geo_info = get_geo_info_from_ip(ip_address)
        utm_params = get_utm_params_from_data(data)

        geo_location = ""
        if geo_info.get('city') and geo_info.get('country'):
            geo_location = f"{geo_info['city']}, {geo_info['country']}"
        elif geo_info.get('country'):
            geo_location = geo_info['country']

        # Build tracking data
        complete_tracking_data = {
            "browser": {
                "browser_name": browser_details['browser'],
                "os_name": browser_details['os'],
                "device_type": browser_details['device']
            },
            "geo": {
                "country": geo_info.get('country'),
                "city": geo_info.get('city'),
                "ip_address": ip_address
            },
            "submission_timestamp": now(),
            "cart_items": cart_items,
            "cart_total": cart_total,
            "cta_source": cta_source
        }

        # Check/Create Organization
        org_name = "QuickShop"
        if not frappe.db.exists("CRM Organization", org_name):
            org = frappe.get_doc({
                "doctype": "CRM Organization",
                "organization_name": org_name,
                "website": "quickshop-4f6f5.web.app"
            })
            org.insert(ignore_permissions=True)
            frappe.db.commit()
            frappe.logger().info(f"✅ Created organization: {org_name}")

        # Check for existing lead
        existing_lead = None

        if client_id:
            try:
                existing_lead = frappe.db.get_value(
                    "CRM Lead", {"ga_client_id": client_id},
                    ["name", "email", "mobile_no"], as_dict=True
                )
                if existing_lead:
                    frappe.logger().info(f"✅ Found existing lead by client_id: {existing_lead.name}")
            except Exception as e:
                frappe.logger().error(f"Error checking lead by client_id: {str(e)}")

        if not existing_lead and email:
            try:
                existing_lead = frappe.db.get_value(
                    "CRM Lead", {"email": email},
                    ["name", "email", "mobile_no"], as_dict=True
                )
                if existing_lead:
                    frappe.logger().info(f"✅ Found existing lead by email: {existing_lead.name}")
            except Exception as e:
                frappe.logger().error(f"Error checking lead by email: {str(e)}")

        if existing_lead:
            # UPDATE EXISTING LEAD - RECORD NEW ORDER
            frappe.logger().info(f"🔄 Recording new order for existing lead: {existing_lead.name}")

            lead = frappe.get_doc("CRM Lead", existing_lead.name)

            # Update contact info if missing
            if email and not lead.email:
                lead.email = email
            if phone and not lead.mobile_no:
                lead.mobile_no = phone
            if client_id and not lead.ga_client_id:
                lead.ga_client_id = client_id
            if not lead.organization:
                lead.organization = org_name

            # Add order comment
            lead.add_comment("Info", f"🛒 New Order Placed<br>Items: {cart_items}<br>Total: ₹{cart_total}<br>Via: {cta_source}")
            lead.save(ignore_permissions=True)

            # Add ORDER activity (not resubmission)
            add_activity_to_lead(lead.name, {
                "activity_type": f"🛒 Order Placed - ₹{cart_total}",
                "page_url": page_url,
                "product_name": cart_items,  # List of items
                "cta_name": "Order Completed",
                "timestamp": now(),
                "browser": f"{browser_details['browser']} on {browser_details['os']}",
                "device": browser_details['device'],
                "geo_location": geo_location,
                "referrer": referrer,
                "client_id": client_id,
                **utm_params
            })

            frappe.db.commit()
            frappe.logger().info(f"✅ Order recorded for lead: {lead.name}")

            return {
                "success": True,
                "message": "Your order has been placed!",
                "lead": lead.name
            }

        else:
            # CREATE NEW LEAD
            frappe.logger().info(f"➕ Creating new lead for: {full_name}")

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
                link_historical_activities_to_lead(client_id, lead_name)

            # Add FIRST ORDER activity
            add_activity_to_lead(lead.name, {
                "activity_type": f"🛒 First Order Placed - ₹{cart_total}",
                "page_url": page_url,
                "product_name": cart_items,
                "cta_name": "Order Completed",
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
                "message": "Thank you! Your order has been placed.",
                "lead": lead.name
            }

    except Exception as e:
        frappe.logger().error("=" * 80)
        frappe.logger().error(f"❌ FORM SUBMISSION ERROR: {str(e)}")
        frappe.logger().error(f"❌ Traceback: {frappe.get_traceback()}")
        frappe.logger().error("=" * 80)
        frappe.log_error(frappe.get_traceback(), "QuickShop Form Error")

        return {
            "success": False,
            "message": f"Error: {str(e)}",
            "error_details": frappe.get_traceback()
        }



@frappe.whitelist(allow_guest=True, methods=['POST'])
def track_activity(**kwargs):
    """Track user activity - page views, clicks, scrolls, etc."""
    frappe.set_user("Guest")
    frappe.flags.ignore_csrf = True
    
    try:
        frappe.logger().info("=" * 80)
        frappe.logger().info("📊 ACTIVITY TRACKING REQUEST RECEIVED")
        frappe.logger().info("=" * 80)
        
        # Get data from all possible sources
        data = get_request_data()
        data.update(kwargs)
        
        frappe.logger().info(f"📊 Combined data: {json.dumps(data, indent=2)}")

        # Extract required fields
        client_id = data.get("client_id")
        activity_type = str(data.get("activity_type") or "")
        page_url = str(data.get("page_url") or "")
        product_name = str(data.get("product_name") or "")
        cta_name = str(data.get("cta_name") or "")
        percent_scrolled = data.get("percent_scrolled", "")

        frappe.logger().info(f"✅ Extracted: client_id={client_id}, activity={activity_type}")

        if not client_id:
            frappe.logger().error("❌ Validation failed: client_id is required")
            return {"success": False, "message": "client_id is required"}
        
        if not activity_type:
            frappe.logger().error("❌ Validation failed: activity_type is required")
            return {"success": False, "message": "activity_type is required"}

        # Handle scroll events - extract percentage
        if "scroll" in activity_type.lower() and percent_scrolled:
            # percent_scrolled might be "scroll_50", "50", or 50
            if isinstance(percent_scrolled, str):
                if "scroll_" in percent_scrolled:
                    percent_scrolled = percent_scrolled.replace("scroll_", "")
                activity_type = f"📜 Scroll {percent_scrolled}%"
            else:
                activity_type = f"📜 Scroll {percent_scrolled}%"
            
            frappe.logger().info(f"📜 Processed scroll event: {activity_type}")

        # Get tracking info - SERVER-SIDE
        user_agent = str(data.get("user_agent") or frappe.get_request_header("User-Agent", ""))
        ip_address = str(data.get("ip_address") or frappe.local.request_ip or "")
        referrer = str(data.get("referrer") or "")
        
        browser_details = extract_browser_details(user_agent)
        geo_info = get_geo_info_from_ip(ip_address)
        utm_params = get_utm_params_from_data(data)
        
        geo_location = ""
        if geo_info.get('city') and geo_info.get('country'):
            geo_location = f"{geo_info['city']}, {geo_info['country']}"
        elif geo_info.get('country'):
            geo_location = geo_info['country']

        # Get or create visitor
        visitor = get_or_create_web_visitor(client_id, data)
        frappe.db.set_value("Web Visitor", visitor.name, "last_seen", now(), update_modified=False)
        frappe.logger().info(f"✅ Visitor: {visitor.name}")

        # Find linked lead
        lead_name = None
        
        if visitor.converted_lead:
            lead_name = visitor.converted_lead
            frappe.logger().info(f"✅ Found lead from visitor.converted_lead: {lead_name}")

        if not lead_name and client_id:
            try:
                lead_name = frappe.db.get_value("CRM Lead", {"ga_client_id": client_id}, "name")
                if lead_name:
                    frappe.logger().info(f"✅ Found existing lead by ga_client_id: {lead_name}")
                    link_web_visitor_to_lead(client_id, lead_name)
            except Exception as e:
                frappe.logger().error(f"Error finding lead: {str(e)}")

        # Add activity
        if lead_name:
            frappe.logger().info(f"📝 Adding activity to lead: {lead_name}")
            success = add_activity_to_lead(lead_name, {
                "activity_type": activity_type,
                "page_url": page_url,
                "product_name": product_name,
                "cta_name": cta_name,
                "timestamp": now(),
                "browser": f"{browser_details['browser']} on {browser_details['os']}",
                "device": browser_details['device'],
                "geo_location": geo_location,
                "referrer": referrer,
                "client_id": client_id,
                **utm_params
            })
            frappe.db.commit()
            
            frappe.logger().info(f"✅ Activity saved to lead: {success}")
            
            return {
                "success": True,
                "visitor": visitor.name,
                "linked_lead": lead_name,
                "activity_saved": success
            }
        else:
            # No lead yet - store activity linked to Web Visitor
            frappe.logger().info(f"📝 No lead yet, storing activity for visitor: {visitor.name}")
            
            success = add_activity_to_lead(None, {
                "activity_type": activity_type,
                "page_url": page_url,
                "product_name": product_name,
                "cta_name": cta_name,
                "timestamp": now(),
                "browser": f"{browser_details['browser']} on {browser_details['os']}",
                "device": browser_details['device'],
                "geo_location": geo_location,
                "referrer": referrer,
                "client_id": client_id,
                **utm_params
            })
            frappe.db.commit()
            
            frappe.logger().info(f"✅ Activity saved to visitor: {success}")
            
            return {
                "success": True,
                "visitor": visitor.name,
                "linked_lead": None,
                "message": "Activity logged, no lead yet",
                "activity_saved": success
            }

    except Exception as e:
        frappe.logger().error("=" * 80)
        frappe.logger().error(f"❌ ACTIVITY TRACKING ERROR: {str(e)}")
        frappe.logger().error(f"❌ Traceback: {frappe.get_traceback()}")
        frappe.logger().error("=" * 80)
        frappe.log_error(frappe.get_traceback(), "Activity Tracking Error")
        
        return {
            "success": False, 
            "message": str(e),
            "error_details": frappe.get_traceback()
        }
