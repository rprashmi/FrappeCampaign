"""
Shared utilities for all client APIs - ENHANCED VERSION
Fixed: Browser detection, Device detection, UTM tracking
"""
import frappe
from frappe.utils import now, format_datetime
import json
import re


def extract_browser_details(user_agent):
    """
    Enhanced browser, OS, device detection with better accuracy
    """
    if not user_agent:
        return {
            "browser": "Unknown",
            "os": "Unknown",
            "device": "Desktop",
            "user_agent": ""
        }
    
    user_agent = str(user_agent)
    browser = "Unknown"
    os = "Unknown"
    device = "Desktop"
    
    # ============================================
    # BROWSER DETECTION (Order matters!)
    # ============================================
    if "Edg/" in user_agent or "Edge/" in user_agent:
        browser = "Edge"
    elif "OPR/" in user_agent or "Opera" in user_agent:
        browser = "Opera"
    elif "Chrome/" in user_agent and "Safari/" in user_agent:
        # Chrome-based browsers
        if "Brave" in user_agent:
            browser = "Brave"
        else:
            browser = "Chrome"
    elif "Safari/" in user_agent and "Chrome" not in user_agent:
        browser = "Safari"
    elif "Firefox/" in user_agent:
        browser = "Firefox"
    elif "MSIE" in user_agent or "Trident/" in user_agent:
        browser = "Internet Explorer"
    
    # ============================================
    # OPERATING SYSTEM DETECTION
    # ============================================
    if "Windows NT 10" in user_agent:
        os = "Windows 10"
    elif "Windows NT 6.3" in user_agent:
        os = "Windows 8.1"
    elif "Windows NT 6.2" in user_agent:
        os = "Windows 8"
    elif "Windows NT 6.1" in user_agent:
        os = "Windows 7"
    elif "Windows" in user_agent:
        os = "Windows"
    elif "Mac OS X" in user_agent:
        # Extract macOS version
        mac_version = re.search(r"Mac OS X (\d+[._]\d+)", user_agent)
        if mac_version:
            version = mac_version.group(1).replace('_', '.')
            os = f"macOS {version}"
        else:
            os = "macOS"
    elif "Android" in user_agent:
        # Extract Android version
        android_version = re.search(r"Android (\d+\.?\d*)", user_agent)
        if android_version:
            os = f"Android {android_version.group(1)}"
        else:
            os = "Android"
        device = "Mobile"
    elif "iPhone" in user_agent or "iPad" in user_agent or "iPod" in user_agent:
        # Extract iOS version
        ios_version = re.search(r"OS (\d+_\d+)", user_agent)
        if ios_version:
            version = ios_version.group(1).replace('_', '.')
            os = f"iOS {version}"
        else:
            os = "iOS"
        device = "Tablet" if "iPad" in user_agent else "Mobile"
    elif "Linux" in user_agent:
        os = "Linux"
    elif "Ubuntu" in user_agent:
        os = "Ubuntu"
    elif "CrOS" in user_agent:
        os = "Chrome OS"
    
    # ============================================
    # DEVICE TYPE DETECTION
    # ============================================
    # Mobile indicators
    mobile_indicators = [
        "Mobile", "Android", "iPhone", "iPod", "BlackBerry",
        "Windows Phone", "Opera Mini", "IEMobile"
    ]
    
    # Tablet indicators
    tablet_indicators = ["iPad", "Tablet", "PlayBook", "Kindle"]
    
    if any(indicator in user_agent for indicator in tablet_indicators):
        device = "Tablet"
    elif any(indicator in user_agent for indicator in mobile_indicators):
        device = "Mobile"
    else:
        device = "Desktop"
    
    # Additional mobile detection for Android
    if "Android" in user_agent and "Mobile" not in user_agent:
        # Android tablets don't have "Mobile" in UA
        device = "Tablet"
    
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
    """
    Get existing or create new Web Visitor
    FIXED: Now updates device on each visit
    """
    visitor_name = frappe.db.get_value("Web Visitor", {"client_id": client_id}, "name")

    if visitor_name:
        visitor = frappe.get_doc("Web Visitor", visitor_name)
        
        # UPDATE DEVICE TYPE on each visit (Fix for cross-device)
        user_agent = data.get("user_agent") or ""
        if user_agent:
            browser_details = extract_browser_details(user_agent)
            current_device = browser_details['device']
            
            # Update if device changed
            if visitor.device != current_device:
                frappe.logger().info(f"🔄 Device update: {visitor.device} → {current_device}")
                frappe.db.set_value("Web Visitor", visitor_name, "device", current_device, update_modified=False)
                
    else:
        # Extract browser details for new visitor
        user_agent = data.get("user_agent") or ""
        browser_details = extract_browser_details(user_agent)
        
        visitor = frappe.get_doc({
            "doctype": "Web Visitor",
            "client_id": client_id,
            "website": data.get("page_url", "").split("?")[0],
            "device": browser_details['device'],  # Set initial device
            "first_seen": now(),
            "last_seen": now()
        })
        visitor.insert(ignore_permissions=True)
        frappe.db.commit()
        frappe.logger().info(f"✅ Created Web Visitor: {visitor.name} (Device: {browser_details['device']})")

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
    Enhanced with CTA tracking details
    FIXED: Now properly records device type
    """
    try:
        # Check if lead exists
        if lead_name and frappe.db.exists("CRM Lead", lead_name):
            reference_doctype = "CRM Lead"
            reference_name = lead_name
            lead_email = frappe.db.get_value("CRM Lead", lead_name, "email") or ""
        else:
            # Lead doesn't exist yet - link to Web Visitor instead
            client_id = activity_data.get('client_id')
            if not client_id:
                frappe.logger().error(f"❌ No lead and no client_id provided")
                return False

            visitor_name = frappe.db.get_value("Web Visitor", {"client_id": client_id}, "name")
            if not visitor_name:
                # Create visitor if doesn't exist
                user_agent = activity_data.get('user_agent', '')
                browser_details = extract_browser_details(user_agent)
                
                visitor = frappe.get_doc({
                    "doctype": "Web Visitor",
                    "client_id": client_id,
                    "website": activity_data.get("page_url", "").split("?")[0],
                    "device": browser_details['device'],
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

        # Enhanced CTA tracking
        cta_name = activity_data.get('cta_name', '')
        cta_location = activity_data.get('cta_location', '')
        cta_type = activity_data.get('cta_type', '')

        browser = activity_data.get('browser', '')
        device = activity_data.get('device', '')
        geo_location = activity_data.get('geo_location', '')
        referrer = activity_data.get('referrer', '')
        utm_source = activity_data.get('utm_source')
        utm_medium = activity_data.get('utm_medium')
        utm_campaign = activity_data.get('utm_campaign')

        # Build clean, readable content with enhanced CTA info
        lines = [f"<strong>{activity_type}</strong>"]

        if page_url:
            lines.append(f"Page: <a href='{page_url}' target='_blank'>{page_url}</a>")

        # Enhanced CTA information display
        if cta_name:
            lines.append(f"<strong>CTA:</strong> {cta_name}")
        if cta_location:
            lines.append(f"<strong>Location:</strong> {cta_location}")
        if cta_type:
            lines.append(f"<strong>Type:</strong> {cta_type}")

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
            "subject": activity_type + (f" - {cta_name}" if cta_name else ""),
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

        # Find all Communications linked to this Web Visitor
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
    """
    Extract UTM parameters from request data
    FIXED: Now checks multiple sources
    """
    utm_params = {}
    
    # Method 1: Direct from data
    utm_params['utm_source'] = data.get('utm_source')
    utm_params['utm_medium'] = data.get('utm_medium')
    utm_params['utm_campaign'] = data.get('utm_campaign')
    utm_params['utm_term'] = data.get('utm_term')
    utm_params['utm_content'] = data.get('utm_content')
    
    # Method 2: Parse from page_url if not in data
    page_url = data.get('page_url') or data.get('page_location') or ''
    if page_url and '?' in page_url:
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(page_url)
        query_params = parse_qs(parsed.query)
        
        if not utm_params['utm_source'] and 'utm_source' in query_params:
            utm_params['utm_source'] = query_params['utm_source'][0]
        if not utm_params['utm_medium'] and 'utm_medium' in query_params:
            utm_params['utm_medium'] = query_params['utm_medium'][0]
        if not utm_params['utm_campaign'] and 'utm_campaign' in query_params:
            utm_params['utm_campaign'] = query_params['utm_campaign'][0]
        if not utm_params['utm_term'] and 'utm_term' in query_params:
            utm_params['utm_term'] = query_params['utm_term'][0]
        if not utm_params['utm_content'] and 'utm_content' in query_params:
            utm_params['utm_content'] = query_params['utm_content'][0]
    
    frappe.logger().info(f"📊 UTM Params extracted: {utm_params}")
    
    return utm_params
