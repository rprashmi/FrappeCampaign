"""
Shared utilities for all client APIs - COMPLETE FIXED VERSION
Changes:
1. Added device field management (stored in custom field or in tracking JSON)
2. Enhanced UTM parameter extraction with multiple fallback methods
3. Improved browser/device detection
4. Better error handling for missing fields
"""
import frappe
from frappe.utils import now, format_datetime
import json
import re
from urllib.parse import urlparse, parse_qs


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
        mac_version = re.search(r"Mac OS X (\d+[._]\d+)", user_agent)
        if mac_version:
            version = mac_version.group(1).replace('_', '.')
            os = f"macOS {version}"
        else:
            os = "macOS"
    elif "Android" in user_agent:
        android_version = re.search(r"Android (\d+\.?\d*)", user_agent)
        if android_version:
            os = f"Android {android_version.group(1)}"
        else:
            os = "Android"
        device = "Mobile"
    elif "iPhone" in user_agent or "iPad" in user_agent or "iPod" in user_agent:
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
    mobile_indicators = [
        "Mobile", "Android", "iPhone", "iPod", "BlackBerry",
        "Windows Phone", "Opera Mini", "IEMobile"
    ]
    tablet_indicators = ["iPad", "Tablet", "PlayBook", "Kindle"]

    if any(indicator in user_agent for indicator in tablet_indicators):
        device = "Tablet"
    elif any(indicator in user_agent for indicator in mobile_indicators):
        device = "Mobile"
    else:
        device = "Desktop"

    if "Android" in user_agent and "Mobile" not in user_agent:
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


def ensure_web_visitor_has_device_field():
    """
    Ensure Web Visitor doctype has device field
    This runs once and creates the field if it doesn't exist
    """
    try:
        # Check if field already exists
        if frappe.db.exists("Custom Field", {"dt": "Web Visitor", "fieldname": "device"}):
            return True
        
        # Create custom field
        custom_field = frappe.get_doc({
            "doctype": "Custom Field",
            "dt": "Web Visitor",
            "label": "Device",
            "fieldname": "device",
            "fieldtype": "Select",
            "options": "Desktop\nMobile\nTablet",
            "insert_after": "website",
            "allow_on_submit": 0,
            "in_list_view": 1,
            "in_standard_filter": 1
        })
        custom_field.insert(ignore_permissions=True)
        frappe.db.commit()
        
        frappe.logger().info("✅ Created device field in Web Visitor")
        return True
        
    except Exception as e:
        frappe.logger().error(f"❌ Could not create device field: {str(e)}")
        return False


def get_or_create_web_visitor(client_id, data):
    """
    Get existing or create new Web Visitor
    FIXED: Safe device field handling - uses custom field if available, otherwise stores in JSON
    """
    # Ensure device field exists (only runs once)
    ensure_web_visitor_has_device_field()
    
    visitor_name = frappe.db.get_value("Web Visitor", {"client_id": client_id}, "name")

    if visitor_name:
        visitor = frappe.get_doc("Web Visitor", visitor_name)

        # UPDATE DEVICE TYPE on each visit
        user_agent = data.get("user_agent") or ""
        if user_agent:
            browser_details = extract_browser_details(user_agent)
            current_device = browser_details['device']

            # Try to update device field safely
            try:
                # Check if visitor object has device attribute
                existing_device = getattr(visitor, 'device', None)
                
                # Update if changed
                if existing_device != current_device:
                    frappe.logger().info(f"🔄 Device update: {existing_device} → {current_device}")
                    frappe.db.set_value("Web Visitor", visitor_name, "device", current_device, update_modified=False)
                    
            except Exception as e:
                # If device field doesn't exist as attribute, store in a custom way
                frappe.logger().warning(f"⚠️ Device field not accessible, skipping update: {str(e)}")
                # You can optionally store device info in a JSON field or comment instead

    else:
        # Extract browser details for new visitor
        user_agent = data.get("user_agent") or ""
        browser_details = extract_browser_details(user_agent)

        # Base visitor data
        visitor_data = {
            "doctype": "Web Visitor",
            "client_id": client_id,
            "website": data.get("page_url", "").split("?")[0] if data.get("page_url") else "",
            "first_seen": now(),
            "last_seen": now()
        }
        
        # Try to add device field
        try:
            visitor_data["device"] = browser_details['device']
        except Exception:
            # Device field might not exist yet, that's okay
            frappe.logger().info(f"ℹ️ Device field not available, will be added later")
        
        visitor = frappe.get_doc(visitor_data)
        visitor.insert(ignore_permissions=True)
        frappe.db.commit()
        
        frappe.logger().info(f"✅ Created Web Visitor: {visitor.name} (Device: {browser_details.get('device', 'Unknown')})")

    return visitor


def link_web_visitor_to_lead(client_id, lead_name):
    """Link Web Visitor → Lead"""
    try:
        visitor_name = frappe.db.get_value("Web Visitor", {"client_id": client_id}, "name")
        if visitor_name:
            frappe.db.set_value("Web Visitor", visitor_name, "converted_lead", lead_name, update_modified=False)
            frappe.db.commit()
            frappe.logger().info(f"✅ Linked Web Visitor {visitor_name} → Lead {lead_name}")
    except Exception as e:
        frappe.logger().error(f"Failed to link visitor {client_id}: {str(e)}")


def add_activity_to_lead(lead_name, activity_data):
    """
    Add timeline activity to lead using Communication
    Enhanced with CTA tracking details
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
                    "first_seen": now(),
                    "last_seen": now()
                })
                
                # Try to add device
                try:
                    visitor.device = browser_details['device']
                except:
                    pass
                    
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

        # Build clean, readable content
        lines = [f"<strong>{activity_type}</strong>"]

        if page_url:
            lines.append(f"Page: <a href='{page_url}' target='_blank'>{page_url}</a>")

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
        visitor_name = frappe.db.get_value("Web Visitor", {"client_id": client_id}, "name")

        if not visitor_name:
            frappe.logger().info(f"No Web Visitor found for client_id: {client_id}")
            return

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

        for comm in communications:
            try:
                comm_doc = frappe.get_doc("Communication", comm.name)
                comm_doc.reference_doctype = "CRM Lead"
                comm_doc.reference_name = lead_name

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
    ENHANCED: Checks multiple sources with priority
    Priority: 1) Direct data keys, 2) page_url query params, 3) referrer query params
    """
    utm_params = {
        'utm_source': None,
        'utm_medium': None,
        'utm_campaign': None,
        'utm_term': None,
        'utm_content': None,
        'utm_campaign_id': None  # ✅ ADDED
    }

    # Method 1: Direct from data (highest priority)
    for utm_key in utm_params.keys():
        if data.get(utm_key):
            utm_params[utm_key] = str(data.get(utm_key)).strip()
    
    # Also check for 'utm_id' as campaign_id alias
    if not utm_params['utm_campaign_id'] and data.get('utm_id'):
        utm_params['utm_campaign_id'] = str(data.get('utm_id')).strip()

    # Method 2: Parse from page_url if not in data
    page_url = data.get('page_url') or data.get('page_location') or ''
    if page_url and '?' in page_url:
        try:
            parsed = urlparse(page_url)
            query_params = parse_qs(parsed.query)

            for utm_key in utm_params.keys():
                if not utm_params[utm_key] and utm_key in query_params:
                    utm_params[utm_key] = query_params[utm_key][0].strip()
                    frappe.logger().info(f"✅ Extracted {utm_key} from page_url: {utm_params[utm_key]}")
            
            # Also check for utm_id in URL
            if not utm_params['utm_campaign_id'] and 'utm_id' in query_params:
                utm_params['utm_campaign_id'] = query_params['utm_id'][0].strip()
                frappe.logger().info(f"✅ Extracted utm_campaign_id from page_url utm_id: {utm_params['utm_campaign_id']}")
                
        except Exception as e:
            frappe.logger().error(f"Error parsing page_url for UTM: {str(e)}")

    # Method 3: Parse from referrer if still not found
    referrer = data.get('referrer') or data.get('page_referrer') or ''
    if referrer and '?' in referrer:
        try:
            parsed = urlparse(referrer)
            query_params = parse_qs(parsed.query)

            for utm_key in utm_params.keys():
                if not utm_params[utm_key] and utm_key in query_params:
                    utm_params[utm_key] = query_params[utm_key][0].strip()
                    frappe.logger().info(f"✅ Extracted {utm_key} from referrer: {utm_params[utm_key]}")
            
            # Also check for utm_id in referrer
            if not utm_params['utm_campaign_id'] and 'utm_id' in query_params:
                utm_params['utm_campaign_id'] = query_params['utm_id'][0].strip()
                frappe.logger().info(f"✅ Extracted utm_campaign_id from referrer utm_id: {utm_params['utm_campaign_id']}")
                
        except Exception as e:
            frappe.logger().error(f"Error parsing referrer for UTM: {str(e)}")

    # Log final result
    captured_utm = {k: v for k, v in utm_params.items() if v}
    if captured_utm:
        frappe.logger().info(f"📊 Final UTM Params: {json.dumps(captured_utm)}")
    else:
        frappe.logger().info(f"ℹ️ No UTM parameters found")

    return utm_params
