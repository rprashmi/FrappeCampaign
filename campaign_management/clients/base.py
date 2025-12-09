"""
Shared utilities for all client APIs - FINAL VERSION
"""
import frappe
from frappe.utils import now, format_datetime
import json


def extract_browser_details(user_agent):
    """Extract browser, OS, device from user agent"""
    browser = "Unknown"
    os = "Unknown"
    device = "Desktop"

    if "Chrome" in user_agent:
        browser = "Chrome"
    elif "Firefox" in user_agent:
        browser = "Firefox"
    elif "Safari" in user_agent and "Chrome" not in user_agent:
        browser = "Safari"
    elif "Edge" in user_agent:
        browser = "Edge"

    if "Windows" in user_agent:
        os = "Windows"
    elif "Mac" in user_agent:
        os = "macOS"
    elif "Linux" in user_agent:
        os = "Linux"
    elif "Android" in user_agent:
        os = "Android"
        device = "Mobile"
    elif "iPhone" in user_agent or "iPad" in user_agent:
        os = "iOS"
        device = "Mobile" if "iPhone" in user_agent else "Tablet"

    return {
        "browser": browser,
        "os": os,
        "device": device,
        "user_agent": user_agent
    }


def get_geo_info_from_ip(ip_address):
    """Get geographic info from IP"""
    geo_info = {
        'country': None, 'country_code': None, 'region': None,
        'city': None, 'latitude': None, 'longitude': None
    }

    try:
        if ip_address in ['127.0.0.1', 'localhost', '::1', None, '']:
            return geo_info

        if ip_address.startswith(('10.', '172.', '192.168.')):
            return geo_info

        import requests
        response = requests.get(
            f'http://ip-api.com/json/{ip_address}',
            timeout=3,
            params={'fields': 'status,country,countryCode,region,city,lat,lon'}
        )

        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 'success':
                geo_info.update({
                    'country': data.get('country'),
                    'country_code': data.get('countryCode'),
                    'region': data.get('region'),
                    'city': data.get('city'),
                    'latitude': data.get('lat'),
                    'longitude': data.get('lon')
                })
    except Exception as e:
        frappe.log_error(f"Geo IP failed: {str(e)}", "Geo IP Error")

    return geo_info


def get_or_create_web_visitor(client_id, data):
    """Get existing or create new Web Visitor"""
    visitor_name = frappe.db.get_value("Web Visitor", {"client_id": client_id}, "name")

    if visitor_name:
        visitor = frappe.get_doc("Web Visitor", visitor_name)
    else:
        visitor = frappe.get_doc({
            "doctype": "Web Visitor",
            "client_id": client_id,
            "website": data.get("page_url", "").split("?")[0],
            "first_seen": now(),
            "last_seen": now()
        })
        visitor.insert(ignore_permissions=True)
        frappe.db.commit()
        frappe.logger().info(f"✅ Created Web Visitor: {visitor.name}")

    return visitor


def link_web_visitor_to_lead(client_id, lead_name):
    """Link Web Visitor → Lead"""
    try:
        visitor_name = frappe.db.get_value("Web Visitor", {"client_id": client_id}, "name")
        if visitor_name:
            visitor = frappe.get_doc("Web Visitor", visitor_name)
            visitor.converted_lead = lead_name
            visitor.save(ignore_permissions=True)
            frappe.db.commit()
            frappe.logger().info(f"✅ Linked Web Visitor {visitor_name} → Lead {lead_name}")
    except Exception as e:
        frappe.logger().error(f"Failed to link visitor {client_id}: {str(e)}")

def add_activity_to_lead(lead_name, activity_data):
    """
    Add timeline activity to lead using Communication
    This shows in the Activity tab
    """
    try:
        # Check if lead exists
        if lead_name and frappe.db.exists("CRM Lead", lead_name):
            reference_doctype = "CRM Lead"
            reference_name = lead_name
            lead_email = frappe.db.get_value("CRM Lead", lead_name, "email") or ""
        else:
            # Lead doesn't exist yet - link to Web Visitor instead
            # We'll re-link these later when lead is created
            client_id = activity_data.get('client_id')
            if not client_id:
                frappe.logger().error(f"❌ No lead and no client_id provided")
                return False
            
            visitor_name = frappe.db.get_value("Web Visitor", {"client_id": client_id}, "name")
            if not visitor_name:
                # Create visitor if doesn't exist
                visitor = frappe.get_doc({
                    "doctype": "Web Visitor",
                    "client_id": client_id,
                    "website": activity_data.get("page_url", "").split("?")[0],
                    "first_seen": now(),
                    "last_seen": now()
                })
                visitor.insert(ignore_permissions=True)
                frappe.db.commit()
                visitor_name = visitor.name
                frappe.logger().info(f"✅ Created Web Visitor: {visitor_name}")
            
            reference_doctype = "Web Visitor"
            reference_name = visitor_name
            lead_email = ""
            frappe.logger().info(f"📝 Storing activity for future lead (visitor: {visitor_name})")

        activity_type = activity_data.get('activity_type', 'Web Activity')
        page_url = activity_data.get('page_url', '')
        product_name = activity_data.get('product_name', '').strip()
        browser = activity_data.get('browser', '')
        device = activity_data.get('device', '')
        geo_location = activity_data.get('geo_location', '')
        referrer = activity_data.get('referrer', '')
        utm_source = activity_data.get('utm_source')
        utm_medium = activity_data.get('utm_medium')
        utm_campaign = activity_data.get('utm_campaign')

        # Build clean, readable content
        lines = [f"<strong>{activity_type}</strong>"]

        if page_url:
            lines.append(f"Page: <a href='{page_url}' target='_blank'>{page_url}</a>")
        if product_name:
            lines.append(f"Product: <strong>{product_name}</strong>")
        if browser:
            lines.append(f"Browser: {browser}")
        if device:
            lines.append(f"Device: {device}")
        if geo_location:
            lines.append(f"Location: {geo_location}")
        if referrer and referrer != "direct":
            lines.append(f"Referrer: {referrer}")

        utm = []
        if utm_source: utm.append(f"Source: {utm_source}")
        if utm_medium: utm.append(f"Medium: {utm_medium}")
        if utm_campaign: utm.append(f"Campaign: {utm_campaign}")
        if utm:
            lines.append("UTM: " + " | ".join(utm))

        content = "<br>".join(lines)

        # Create Communication
        comm = frappe.get_doc({
            "doctype": "Communication",
            "communication_type": "Communication",
            "communication_medium": "Other",
            "subject": activity_type,
            "content": content,
            "reference_doctype": reference_doctype,
            "reference_name": reference_name,
            "status": "Linked",
            "sent_or_received": "Received",
            "recipients": lead_email
        })
        comm.insert(ignore_permissions=True)
        frappe.db.commit()

        frappe.logger().info(f"✅ Activity saved: {comm.name} for {reference_doctype} {reference_name}")
        return True

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Add Activity Failed")
        frappe.logger().error(f"❌ Failed to add activity: {str(e)}")
        return False

def link_historical_activities_to_lead(client_id, lead_name):
    """
    When a lead is created, find all Web Visitor activities 
    and link them to this lead retroactively
    """
    try:
        # Get the Web Visitor
        visitor_name = frappe.db.get_value("Web Visitor", {"client_id": client_id}, "name")
        
        if not visitor_name:
            frappe.logger().info(f"No Web Visitor found for client_id: {client_id}")
            return
        
        # Find all Communications linked to this Web Visitor but NOT yet linked to a Lead
        # These are the "orphan" activities from before lead creation
        communications = frappe.get_all(
            "Communication",
            filters={
                "reference_doctype": "Web Visitor",
                "reference_name": visitor_name
            },
            fields=["name", "subject", "content", "creation"]
        )
        
        if not communications:
            frappe.logger().info(f"No historical activities found for visitor: {visitor_name}")
            return
        
        frappe.logger().info(f"Found {len(communications)} historical activities to link")
        
        # Re-link each Communication to the Lead
        for comm in communications:
            try:
                comm_doc = frappe.get_doc("Communication", comm.name)
                comm_doc.reference_doctype = "CRM Lead"
                comm_doc.reference_name = lead_name
                
                # Update recipient to lead's email
                lead_email = frappe.db.get_value("CRM Lead", lead_name, "email") or ""
                if lead_email:
                    comm_doc.recipients = lead_email
                
                comm_doc.save(ignore_permissions=True)
                frappe.logger().info(f"✅ Linked activity {comm.name} to lead {lead_name}")
            except Exception as e:
                frappe.logger().error(f"Failed to link activity {comm.name}: {str(e)}")
                continue
        
        frappe.db.commit()
        frappe.logger().info(f"✅ Successfully linked {len(communications)} historical activities to lead {lead_name}")
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Link Historical Activities Failed")
        frappe.logger().error(f"❌ Failed to link historical activities: {str(e)}")


def get_utm_params_from_data(data):
    """Extract UTM parameters from request data"""
    return {
        'utm_source': data.get('utm_source'),
        'utm_medium': data.get('utm_medium'),
        'utm_campaign': data.get('utm_campaign'),
        'utm_term': data.get('utm_term'),
        'utm_content': data.get('utm_content')
    }
