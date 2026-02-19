import frappe
from frappe.utils import now, format_datetime
import json
import re
from urllib.parse import urlparse, parse_qs


def get_ad_click_data(data):
    ad_info = {
        'ad_platform': None,
        'ad_click_id': None,
        'ad_click_timestamp': None,
        'ad_landing_page': None
    }
    
    # Map of click ID parameter names to platform names
    click_id_map = {
        'fbclid': 'Facebook/Instagram',
        'gclid': 'Google Ads',
        'msclkid': 'Microsoft Ads',
        'li_fat_id': 'LinkedIn Ads',
        'ttclid': 'TikTok Ads',
        'twclid': 'Twitter Ads'
    }
    
    # Method 1: Check direct parameters
    for param_name, platform_name in click_id_map.items():
        click_id = str(data.get(param_name) or "").strip()
        if click_id:
            ad_info['ad_platform'] = platform_name
            ad_info['ad_click_id'] = click_id
            ad_info['ad_click_timestamp'] = now()
            raw_landing = str(data.get('page_url') or data.get('page_location') or "")
            ad_info['ad_landing_page'] = raw_landing.split('?')[0][:140]
            # ad_info['ad_landing_page'] = str(data.get('page_url') or data.get('page_location') or "")
            frappe.logger().info(f"✅ Ad Click Detected: {platform_name} (from direct param: {param_name})")
            frappe.logger().info(f"   Click ID: {click_id}")
            return ad_info
    
    # Method 2: Parse from page_url
    page_url = data.get('page_url') or data.get('page_location') or ''
    if page_url and '?' in page_url:
        try:
            parsed = urlparse(page_url)
            query_params = parse_qs(parsed.query)
            
            for param_name, platform_name in click_id_map.items():
                if param_name in query_params:
                    click_id = query_params[param_name][0].strip()
                    if click_id:
                        ad_info['ad_platform'] = platform_name
                        ad_info['ad_click_id'] = click_id
                        ad_info['ad_click_timestamp'] = now()
                        raw_landing = str(data.get('page_url') or data.get('page_location') or "")
                        ad_info['ad_landing_page'] = raw_landing.split('?')[0][:140]
                        # ad_info['ad_landing_page'] = page_url.split('?')[0]
                        frappe.logger().info(f"✅ Ad Click Detected: {platform_name} (from page_url: {param_name})")
                        frappe.logger().info(f"   Click ID: {click_id}")
                        return ad_info
        except Exception as e:
            frappe.logger().error(f"Error parsing page_url for ad click ID: {str(e)}")
    
    # Method 3: Parse from referrer
    referrer = data.get('referrer') or data.get('page_referrer') or ''
    if referrer and '?' in referrer:
        try:
            parsed = urlparse(referrer)
            query_params = parse_qs(parsed.query)
            
            for param_name, platform_name in click_id_map.items():
                if param_name in query_params:
                    click_id = query_params[param_name][0].strip()
                    if click_id:
                        ad_info['ad_platform'] = platform_name
                        ad_info['ad_click_id'] = click_id
                        ad_info['ad_click_timestamp'] = now()
                        raw_landing = str(data.get('page_url') or data.get('page_location') or "")
                        ad_info['ad_landing_page'] = raw_landing.split('?')[0][:140]
                        # ad_info['ad_landing_page'] = str(data.get('page_url') or data.get('page_location') or "")
                        frappe.logger().info(f"✅ Ad Click Detected: {platform_name} (from referrer: {param_name})")
                        frappe.logger().info(f"   Click ID: {click_id}")
                        return ad_info
        except Exception as e:
            frappe.logger().error(f"Error parsing referrer for ad click ID: {str(e)}")
    
    # No ad click detected
    frappe.logger().info("ℹ️ No ad click ID detected (organic/direct traffic)")
    return ad_info



def extract_browser_details(user_agent):
    """Enhanced browser, OS, device detection with better accuracy"""
    if not user_agent:
        return {"browser": "Unknown", "os": "Unknown", "device": "Desktop", "user_agent": ""}

    user_agent = str(user_agent)
    browser = "Unknown"
    os = "Unknown"
    device = "Desktop"

    # BROWSER DETECTION
    if "Edg/" in user_agent or "Edge/" in user_agent:
        browser = "Edge"
    elif "OPR/" in user_agent or "Opera" in user_agent:
        browser = "Opera"
    elif "Chrome/" in user_agent and "Safari/" in user_agent:
        browser = "Brave" if "Brave" in user_agent else "Chrome"
    elif "Safari/" in user_agent and "Chrome" not in user_agent:
        browser = "Safari"
    elif "Firefox/" in user_agent:
        browser = "Firefox"
    elif "MSIE" in user_agent or "Trident/" in user_agent:
        browser = "Internet Explorer"

    # OPERATING SYSTEM DETECTION
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

    # DEVICE TYPE DETECTION
    mobile_indicators = ["Mobile", "Android", "iPhone", "iPod", "BlackBerry", "Windows Phone", "Opera Mini", "IEMobile"]
    tablet_indicators = ["iPad", "Tablet", "PlayBook", "Kindle"]

    if any(indicator in user_agent for indicator in tablet_indicators):
        device = "Tablet"
    elif any(indicator in user_agent for indicator in mobile_indicators):
        device = "Mobile"
    else:
        device = "Desktop"

    if "Android" in user_agent and "Mobile" not in user_agent:
        device = "Tablet"

    return {"browser": browser, "os": os, "device": device, "user_agent": user_agent}


def get_geo_info_from_ip(ip_address):
    """Get geographic info from IP"""
    geo_info = {'country': None, 'country_code': None, 'region': None, 'city': None, 'latitude': None, 'longitude': None}

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
    """Ensure Web Visitor doctype has device field"""
    try:
        if frappe.db.exists("Custom Field", {"dt": "Web Visitor", "fieldname": "device"}):
            return True

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
        frappe.logger().info("Created device field in Web Visitor")
        return True
    except Exception as e:
        frappe.logger().error(f"Could not create device field: {str(e)}")
        return False


def get_or_create_web_visitor(client_id, data):
    """Get existing or create new Web Visitor"""
    ensure_web_visitor_has_device_field()
    visitor_name = frappe.db.get_value("Web Visitor", {"client_id": client_id}, "name")

    if visitor_name:
        visitor = frappe.get_doc("Web Visitor", visitor_name)
        user_agent = data.get("user_agent") or ""
        if user_agent:
            browser_details = extract_browser_details(user_agent)
            current_device = browser_details['device']
            try:
                existing_device = getattr(visitor, 'device', None)
                if existing_device != current_device:
                    frappe.logger().info(f"Device update: {existing_device} to {current_device}")
                    frappe.db.set_value("Web Visitor", visitor_name, "device", current_device, update_modified=False)
            except Exception as e:
                frappe.logger().warning(f"Device field not accessible: {str(e)}")
    else:
        user_agent = data.get("user_agent") or ""
        browser_details = extract_browser_details(user_agent)
        visitor_data = {
            "doctype": "Web Visitor",
            "client_id": client_id,
            "website": data.get("page_url", "").split("?")[0] if data.get("page_url") else "",
            "first_seen": now(),
            "last_seen": now()
        }
        try:
            visitor_data["device"] = browser_details['device']
        except Exception:
            frappe.logger().info("Device field not available")

        visitor = frappe.get_doc(visitor_data)
        visitor.insert(ignore_permissions=True)
        frappe.db.commit()
        frappe.logger().info(f"Created Web Visitor: {visitor.name}")

    return visitor


def link_web_visitor_to_lead(client_id, lead_name):
    """Link Web Visitor to Lead"""
    try:
        visitor_name = frappe.db.get_value(
            "Web Visitor",
            {"client_id": client_id},
            "name"
        )
        if visitor_name:
            frappe.db.set_value(
                "Web Visitor",
                visitor_name,
                "converted_lead",
                lead_name,
                update_modified=False
            )
            frappe.logger().info(
                f"Linked Web Visitor {visitor_name} to Lead {lead_name}"
            )
    except Exception as e:
        frappe.logger().error(
            f"Failed to link visitor {client_id}: {str(e)}"
        )




def truncate_url(url, max_length=60):
    """
    Truncate long URLs for display
    Returns: tuple (display_text, full_url)
    """
    if not url or len(url) <= max_length:
        return url, url

    return f"{url[:40]}...{url[-10:]}", url


def add_activity_to_lead(lead_name, activity_data):
    
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
                frappe.logger().error("No lead and no client_id provided")
                return False

            visitor_name = frappe.db.get_value("Web Visitor", {"client_id": client_id}, "name")
            if not visitor_name:
                user_agent = activity_data.get('user_agent', '')
                browser_details = extract_browser_details(user_agent)
                page_url = activity_data.get("page_url", "")
                visitor = frappe.get_doc({
                    "doctype": "Web Visitor",
                    "client_id": client_id,
                    "website": page_url.split("?")[0] if page_url else "",
                    "first_seen": now(),
                    "last_seen": now()
                })
                try:
                    visitor.device = browser_details['device']
                except:
                    pass
                visitor.insert(ignore_permissions=True)
                frappe.db.commit()
                visitor_name = visitor.name
                frappe.logger().info(f"Created Web Visitor: {visitor_name}")

            reference_doctype = "Web Visitor"
            reference_name = visitor_name
            lead_email = ""
            frappe.logger().info(f"Storing activity for future lead (visitor: {visitor_name})")

        activity_type = activity_data.get('activity_type', 'Web Activity')
        activity_type = re.sub(r'[^\w\s\-\(\)%]', '', activity_type).strip()
        
        page_url = activity_data.get('page_url', '')
        product_name = activity_data.get('product_name', '').strip()
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
        fbclid = activity_data.get('fbclid')
        utm_content = activity_data.get('utm_content')
        lines = [f"<strong>{activity_type}</strong>"]

        if fbclid:
            fbclid_display = fbclid[:20] + '...' if len(fbclid) > 20 else fbclid
            lines.append(f"<strong>Facebook Click ID:</strong> {fbclid_display}")    
        if utm_campaign:
            lines.append(f"<strong>Campaign:</strong> {utm_campaign}")        
        if utm_content:
            lines.append(f"<strong>Ad Creative:</strong> {utm_content}")      
        if page_url:
            display_url, full_url = truncate_url(page_url, 60)
            lines.append(f"<strong>Page:</strong> <a href='{full_url}' target='_blank' title='{full_url}'>{display_url}</a>")
        if cta_name:
            lines.append(f"<strong>CTA:</strong> {cta_name}")
        if cta_location:
            lines.append(f"<strong>Location:</strong> {cta_location}")
        if cta_type:
            lines.append(f"<strong>Type:</strong> {cta_type}")
        if product_name:
            lines.append(f"<strong>Product:</strong> {product_name}")
        
        # Device & Browser info
        device_info = []
        if browser:
            device_info.append(f"Browser: {browser}")
        if device:
            device_info.append(f"Device: {device}")
        if geo_location:
            device_info.append(f"Location: {geo_location}")
        if device_info:
            lines.append(" | ".join(device_info))

        # Referrer with truncation
        if referrer and referrer != "direct":
            display_ref, full_ref = truncate_url(referrer, 60)
            lines.append(f"<strong>Referrer:</strong> <a href='{full_ref}' target='_blank' title='{full_ref}'>{display_ref}</a>")

        # UTM parameters
        utm = []
        if utm_source:
            utm.append(f"Source: {utm_source}")
        if utm_medium:
            utm.append(f"Medium: {utm_medium}")
        if utm_campaign:
            utm.append(f"Campaign: {utm_campaign}")
        if utm:
            lines.append("<strong>UTM:</strong> " + " | ".join(utm))

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

        frappe.logger().info(f"Activity saved: {comm.name} for {reference_doctype} {reference_name}")
        return True

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Add Activity Failed")
        frappe.logger().error(f"Failed to add activity: {str(e)}")
        return False


def link_historical_activities_to_lead(client_id, lead_name):
    """Link all visitor activities to lead"""
    try:
        visitor_name = frappe.db.get_value(
            "Web Visitor",
            {"client_id": client_id},
            "name"
        )
        if not visitor_name:
            return

        communications = frappe.get_all(
            "Communication",
            filters={
                "reference_doctype": "Web Visitor",
                "reference_name": visitor_name
            },
            fields=["name"]
        )

        for comm in communications:
            comm_doc = frappe.get_doc("Communication", comm.name)
            comm_doc.reference_doctype = "CRM Lead"
            comm_doc.reference_name = lead_name
            comm_doc.save(ignore_permissions=True)

        frappe.logger().info(
            f"Linked {len(communications)} historical activities to lead {lead_name}"
        )

    except Exception as e:
        frappe.log_error(
            frappe.get_traceback(),
            "Link Historical Activities Failed"
        )


def get_utm_params_from_data(data):
    """Extract UTM parameters from request data"""
    utm_params = {
        'utm_source': None,
        'utm_medium': None,
        'utm_campaign': None,
        'utm_term': None,
        'utm_content': None,
        'utm_campaign_id': None
    }

    # Method 1: Direct from data
    for utm_key in utm_params.keys():
        if data.get(utm_key):
            utm_params[utm_key] = str(data.get(utm_key)).strip()

    if not utm_params['utm_campaign_id'] and data.get('utm_id'):
        utm_params['utm_campaign_id'] = str(data.get('utm_id')).strip()

    # Method 2: Parse from page_url
    page_url = data.get('page_url') or data.get('page_location') or ''
    if page_url and '?' in page_url:
        try:
            parsed = urlparse(page_url)
            query_params = parse_qs(parsed.query)
            for utm_key in utm_params.keys():
                if not utm_params[utm_key] and utm_key in query_params:
                    utm_params[utm_key] = query_params[utm_key][0].strip()
                    frappe.logger().info(f"Extracted {utm_key} from page_url: {utm_params[utm_key]}")
            if not utm_params['utm_campaign_id'] and 'utm_id' in query_params:
                utm_params['utm_campaign_id'] = query_params['utm_id'][0].strip()
                frappe.logger().info(f"Extracted utm_campaign_id from page_url")
        except Exception as e:
            frappe.logger().error(f"Error parsing page_url for UTM: {str(e)}")

    # Method 3: Parse from referrer
    referrer = data.get('referrer') or data.get('page_referrer') or ''
    if referrer and '?' in referrer:
        try:
            parsed = urlparse(referrer)
            query_params = parse_qs(parsed.query)
            for utm_key in utm_params.keys():
                if not utm_params[utm_key] and utm_key in query_params:
                    utm_params[utm_key] = query_params[utm_key][0].strip()
                    frappe.logger().info(f"Extracted {utm_key} from referrer: {utm_params[utm_key]}")
            if not utm_params['utm_campaign_id'] and 'utm_id' in query_params:
                utm_params['utm_campaign_id'] = query_params['utm_id'][0].strip()
                frappe.logger().info(f"Extracted utm_campaign_id from referrer")
        except Exception as e:
            frappe.logger().error(f"Error parsing referrer for UTM: {str(e)}")

    captured_utm = {k: v for k, v in utm_params.items() if v}
    if captured_utm:
        frappe.logger().info(f"Final UTM Params: {json.dumps(captured_utm)}")
    else:
        frappe.logger().info("No UTM parameters found")

    return utm_params


def get_facebook_ad_data(data):
    """
    Extract Facebook ad click data
    Returns dict with fbclid and campaign info
    """
    fb_data = {
        'has_facebook_click': False,
        'fbclid': None,
        'utm_campaign': None,
        'utm_content': None,
        'landing_page': None
    }
    
    # Method 1: Direct parameter
    fbclid = str(data.get('fbclid') or '').strip()
    if fbclid:
        fb_data['has_facebook_click'] = True
        fb_data['fbclid'] = fbclid
        fb_data['landing_page'] = str(data.get('page_url') or data.get('page_location') or '')
        frappe.logger().info(f"✅ Facebook Ad Click: {fbclid}")
    
    # Method 2: Parse from URL
    if not fbclid:
        page_url = data.get('page_url') or data.get('page_location') or ''
        if 'fbclid=' in page_url:
            try:
                from urllib.parse import urlparse, parse_qs
                parsed = urlparse(page_url)
                params = parse_qs(parsed.query)
                if 'fbclid' in params:
                    fbclid = params['fbclid'][0].strip()
                    fb_data['has_facebook_click'] = True
                    fb_data['fbclid'] = fbclid
                    fb_data['landing_page'] = page_url.split('?')[0]
                    frappe.logger().info(f"Facebook Click from URL: {fbclid}")
            except Exception as e:
                frappe.logger().error(f"Error parsing URL: {str(e)}")
    
    # Get campaign info
    fb_data['utm_campaign'] = str(data.get('utm_campaign') or '').strip()
    fb_data['utm_content'] = str(data.get('utm_content') or '').strip()
    
    return fb_data


def track_facebook_ad_click(client_id, data, org_name):
    """
    Track Facebook ad click as activity
    Works for both anonymous visitors and existing leads
    """
    try:
        fb_data = get_facebook_ad_data(data)
        
        if not fb_data['has_facebook_click']:
            return False
        
        # Get visitor
        visitor = get_or_create_web_visitor(client_id, data)
        
        # Check if visitor is already a lead
        lead_name = None
        if visitor.converted_lead:
            lead_name = visitor.converted_lead
        else:
            # Try to find by client_id
            try:
                lead_name = frappe.db.get_value(
                    "CRM Lead",
                    {"ga_client_id": client_id, "organization": org_name},
                    "name"
                )
            except:
                pass
        
        # Get tracking details
        user_agent = str(data.get("user_agent") or frappe.get_request_header("User-Agent", ""))
        ip_address = str(data.get("ip_address") or frappe.local.request_ip or "")
        page_url = str(data.get("page_url") or "")
        
        browser_details = extract_browser_details(user_agent)
        geo_info = get_geo_info_from_ip(ip_address)
        
        utm_params = get_utm_params_from_data(data)
        
        geo_location = ""
        if geo_info.get('city') and geo_info.get('country'):
            geo_location = f"{geo_info['city']}, {geo_info['country']}"
        elif geo_info.get('country'):
            geo_location = geo_info['country']
        
        # reate activity with ALL UTM data
        activity_data = {
            "activity_type": "Facebook Ad Click",
            "page_url": page_url,
            "timestamp": now(),
            "browser": f"{browser_details['browser']} on {browser_details['os']}",
            "device": browser_details['device'],
            "geo_location": geo_location,
            "referrer": str(data.get("referrer") or ""),
            "client_id": client_id,
            "fbclid": fb_data['fbclid'],    
            "utm_source": utm_params.get('utm_source'),
            "utm_medium": utm_params.get('utm_medium'),
            "utm_campaign": utm_params.get('utm_campaign') or fb_data['utm_campaign'],
            "utm_content": utm_params.get('utm_content') or fb_data['utm_content'],
            "utm_term": utm_params.get('utm_term'),
            "utm_campaign_id": utm_params.get('utm_campaign_id')
        }
        
        # Add activity (to lead if exists, to visitor if not)
        add_activity_to_lead(lead_name, activity_data)
        frappe.db.commit()
        
        if lead_name:
            frappe.logger().info(f"✅ Facebook ad click tracked for lead: {lead_name}")
        else:
            frappe.logger().info(f"✅ Facebook ad click tracked for visitor (will link to lead later)")
        
        return True
        
    except Exception as e:
        frappe.logger().error(f"Error tracking Facebook click: {str(e)}")
        frappe.log_error(frappe.get_traceback(), "Facebook Ad Tracking Error")
        return False


def enrich_lead_with_facebook_data(lead_doc, data):
    """
    Add Facebook ad data to lead (first touch only)
    """
    fb_data = get_facebook_ad_data(data)
    
    if fb_data['has_facebook_click']:
        # Only set if empty 
        if not lead_doc.get('ad_platform'):
            lead_doc.ad_platform = 'Facebook/Instagram'
        
        if not lead_doc.get('ad_click_id'):
            lead_doc.ad_click_id = fb_data['fbclid']
        
        if not lead_doc.get('ad_click_timestamp'):
            lead_doc.ad_click_timestamp = now()
        
        if not lead_doc.get('ad_landing_page'):
            lead_doc.ad_landing_page = fb_data['landing_page']
        
        if fb_data['utm_campaign'] and not lead_doc.get('utm_campaign'):
            lead_doc.utm_campaign = fb_data['utm_campaign']
        
        # Update source
        if not lead_doc.get('source') or lead_doc.get('source') == 'Website':
            lead_doc.source = 'Facebook'
        
        frappe.logger().info(f"Lead enriched with Facebook data")
    
    return lead_doc
