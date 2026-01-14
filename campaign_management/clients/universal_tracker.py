"""
Universal Tracker - COMPLETE VERSION WITH AD TRACKING
"""
import frappe
from frappe.utils import now
import json
from urllib.parse import urlparse, parse_qs
from campaign_management.clients.base import (
    extract_browser_details,
    get_geo_info_from_ip,
    get_or_create_web_visitor,
    link_web_visitor_to_lead,
    add_activity_to_lead,
    get_utm_params_from_data,
    link_historical_activities_to_lead,
    get_ad_click_data  
)


# Organization Configuration Database
ORGANIZATION_CONFIG = {
    "quickshop": {
        "org_name": "QuickShop",
        "org_website": "quickshop-4f6f5.web.app",
        "type": "ecommerce",
        "domains": ["quickshop-4f6f5.web.app", "quickshop.com"],
        "keywords": ["quickshop"]
    },
    "walue": {
        "org_name": "Walue",
        "org_website": "walue.com",
        "type": "saas",
        "domains": ["walue.com", "waluetracking.m.frappe.cloud", "waluetracking.web.app"],
        "keywords": ["walue"]
    },
    "EE": {  
        "org_name": "EE",
        "org_website": "ee-dev.m.frappe.cloud",
        "type": "education",  
        "domains": ["ee-dev.m.frappe.cloud"],
        "keywords": ["EE", "orbis", "education"]
    }
}


def normalize_utm_value(raw_value, field_type="source"):
    """Normalize UTM values to match Select field options"""
    if not raw_value:
        return None

    value = str(raw_value).strip()
    if not value:
        return None

    value_lower = value.lower()

    if field_type == "source":
        source_map = {
            "google": "Google", "facebook": "Facebook", "fb": "Facebook",
            "linkedin": "LinkedIn", "li": "LinkedIn", "twitter": "Twitter",
            "instagram": "Instagram", "ig": "Instagram", "email": "Email",
            "direct": "Direct", "referral": "Referral", "organic": "Organic",
            "bing": "Bing", "youtube": "YouTube", "yt": "YouTube",
            "tiktok": "TikTok", "whatsapp": "WhatsApp", "wa": "WhatsApp"
        }

        if value_lower in source_map:
            return source_map[value_lower]
        for key, proper_value in source_map.items():
            if key in value_lower:
                return proper_value
        return "Other"

    elif field_type == "medium":
        medium_map = {
            "cpc": "CPC", "ppc": "PPC", "cpm": "CPM", "display": "Display",
            "social": "Social", "email": "Email", "affiliate": "Affiliate",
            "referral": "Referral", "organic": "Organic",
            "paid social": "Paid Social", "paidsocial": "Paid Social",
            "paid-social": "Paid Social", "paid_social": "Paid Social",
            "banner": "Banner", "retargeting": "Retargeting",
            "retarget": "Retargeting", "video": "Video"
        }

        if value_lower in medium_map:
            return medium_map[value_lower]
        for key, proper_value in medium_map.items():
            if key in value_lower:
                return proper_value
        return "Other"

    return value


def determine_source(data, org_config):
    """
    Smart Source Detection - Checks ad click IDs FIRST
    """
    frappe.logger().info("=" * 60)
    frappe.logger().info("DETERMINING SOURCE")
    frappe.logger().info("=" * 60)

    #  Check for Ad Click IDs 
    ad_data = get_ad_click_data(data)
    if ad_data['ad_platform']:
        platform = ad_data['ad_platform']
        frappe.logger().info(f"🎯 Ad Click Detected: {platform}")
        
        if platform == "Facebook/Instagram":
            frappe.logger().info("✅ Source: Facebook (from ad click ID)")
            return "Facebook"
        elif platform == "Google Ads":
            frappe.logger().info("✅ Source: Campaign (from Google ad click ID)")
            return "Campaign"
        elif platform == "LinkedIn Ads":
            frappe.logger().info("✅ Source: Advertisement (from LinkedIn ad click ID)")
            return "Advertisement"
        else:
            frappe.logger().info("✅ Source: Campaign (from ad click ID)")
            return "Campaign"

    # Check UTM Source
    utm_source = str(data.get("utm_source") or "").lower().strip()
    if utm_source:
        frappe.logger().info(f"🎯 Found UTM Source: '{utm_source}'")
        
        if any(fb_term in utm_source for fb_term in ['facebook', 'fb', 'instagram', 'ig']):
            frappe.logger().info("✅ Source: Facebook (from UTM)")
            return "Facebook"
        
        if any(google_term in utm_source for google_term in ['google', 'google_ads', 'adwords']):
            frappe.logger().info("✅ Source: Campaign (from UTM - Google)")
            return "Campaign"
        
        if any(li_term in utm_source for li_term in ['linkedin', 'li']):
            frappe.logger().info("✅ Source: Advertisement (from UTM - LinkedIn)")
            return "Advertisement"
        
        if any(email_term in utm_source for email_term in ['email', 'newsletter']):
            frappe.logger().info("✅ Source: Mass Mailing (from UTM)")
            return "Mass Mailing"
        
        if 'campaign' in utm_source or any(term in utm_source for term in ['promo', 'offer', 'ad', 'paid']):
            frappe.logger().info("✅ Source: Campaign (from UTM keyword)")
            return "Campaign"

    # Check UTM Medium
    utm_medium = str(data.get("utm_medium") or "").lower().strip()
    if utm_medium:
        if utm_medium in ['cpc', 'ppc', 'paid', 'display', 'paid_social']:
            frappe.logger().info("✅ Source: Campaign (from UTM Medium)")
            return "Campaign"
        if utm_medium in ['social']:
            if utm_source and 'facebook' in utm_source:
                return "Facebook"
            frappe.logger().info("✅ Source: Advertisement (from UTM Medium)")
            return "Advertisement"
        if utm_medium == 'email':
            frappe.logger().info("✅ Source: Mass Mailing (from UTM Medium)")
            return "Mass Mailing"

    # Check Referrer
    referrer = str(data.get("referrer") or data.get("page_referrer") or "").lower().strip()
    if referrer and referrer not in ['direct', '', 'null', 'undefined']:
        try:
            parsed = urlparse(referrer)
            domain = parsed.netloc.lower()
            
            if any(fb_domain in domain for fb_domain in ['facebook.com', 'fb.com', 'instagram.com']):
                frappe.logger().info("✅ Source: Facebook (from Referrer)")
                return "Facebook"
            
            if any(google_domain in domain for google_domain in ['google.com', 'googleads']):
                frappe.logger().info("✅ Source: Campaign (from Referrer)")
                return "Campaign"
            
            org_domains = org_config.get("domains", [])
            is_external = not any(org_domain in domain for org_domain in org_domains)
            if is_external and domain:
                frappe.logger().info(f"✅ Source: Supplier Reference (from Referrer: {domain})")
                return "Supplier Reference"
        except Exception as e:
            frappe.logger().error(f"Error parsing referrer: {str(e)}")

    frappe.logger().info("✅ Source: Website (default)")
    frappe.logger().info("=" * 60)
    return "Website"


def find_lead_cross_device(email, client_id, org_name):
    """Cross-Device Mapping: Find lead by email OR client_id"""
    existing_lead = None

    if email:
        try:
            existing_lead = frappe.db.get_value(
                "CRM Lead",
                {"email": email, "organization": org_name},
                ["name", "email", "mobile_no", "ga_client_id"],
                as_dict=True
            )
            if existing_lead:
                frappe.logger().info(f"✅ Found by email: {existing_lead.name}")
                if client_id and existing_lead.ga_client_id != client_id:
                    frappe.db.set_value("CRM Lead", existing_lead.name, "ga_client_id", client_id, update_modified=False)
                    link_web_visitor_to_lead(client_id, existing_lead.name)
                return existing_lead
        except Exception as e:
            frappe.logger().error(f"Error finding by email: {str(e)}")

    if not existing_lead and client_id:
        try:
            existing_lead = frappe.db.get_value(
                "CRM Lead",
                {"ga_client_id": client_id, "organization": org_name},
                ["name", "email", "mobile_no", "ga_client_id"],
                as_dict=True
            )
            if existing_lead:
                frappe.logger().info(f"✅ Found by client_id: {existing_lead.name}")
                return existing_lead
        except Exception as e:
            frappe.logger().error(f"Error finding by client_id: {str(e)}")

    return None


def get_request_data():
    """Safely extract data from various request formats"""
    data = {}
    try:
        if frappe.local.form_dict:
            data.update(frappe.local.form_dict)
        if hasattr(frappe.local, 'request') and hasattr(frappe.local.request, 'form'):
            form_data = dict(frappe.local.request.form)
            data.update(form_data)
        if hasattr(frappe.local, 'request') and frappe.local.request.data:
            json_body = frappe.local.request.get_json(silent=True)
            if json_body:
                data.update(json_body)
    except Exception as e:
        frappe.logger().error(f"Error reading request data: {str(e)}")
    return data


def identify_organization(data):
    """Identify organization from request data"""
    org_identifier = str(data.get("organization") or "").lower().strip()
    if org_identifier in ORGANIZATION_CONFIG:
        return ORGANIZATION_CONFIG[org_identifier]

    page_url = str(data.get("page_url") or data.get("page_location") or "").lower()
    if page_url:
        try:
            parsed = urlparse(page_url)
            domain = parsed.netloc or parsed.path.split('/')[0]
            for org_key, config in ORGANIZATION_CONFIG.items():
                for configured_domain in config["domains"]:
                    if configured_domain in domain:
                        return config
        except:
            pass

    return ORGANIZATION_CONFIG.get("walue", {
        "org_name": "Unknown Organization",
        "org_website": frappe.local.site,
        "type": "generic",
        "domains": [],
        "keywords": []
    })


def verify_organization_exists(org_name):
    """Check if organization exists in Frappe"""
    exists = frappe.db.exists("CRM Organization", org_name)
    if not exists:
        frappe.logger().error(f" Organization '{org_name}' does NOT exist!")
    return exists


@frappe.whitelist(allow_guest=True, methods=['POST'])
def user_login(**kwargs):
    frappe.set_user("Guest")
    frappe.flags.ignore_csrf = True

    try:
        data = get_request_data()
        data.update(kwargs)

        email = str(data.get("email") or "").strip().lower()
        client_id = str(data.get("ga_client_id") or data.get("client_id") or "")

        if not email or not client_id:
            return {"success": False, "message": "Email and client_id required"}

        org_config = identify_organization(data)
        org_name = org_config["org_name"]

        if not verify_organization_exists(org_name):
            return {"success": False, "message": f"Organization '{org_name}' not configured"}

        lead = find_lead_cross_device(email, client_id, org_name)

        if lead:
            link_historical_activities_to_lead(client_id, lead['name'])
            return {
                "success": True,
                "message": "Login successful",
                "lead_id": lead['name'],
                "user_name": email.split('@')[0].title()
            }
        else:
            name_parts = email.split('@')[0].split('.')
            first_name = name_parts[0].title() if name_parts else email.split('@')[0].title()
            last_name = name_parts[1].title() if len(name_parts) > 1 else ""
            source = determine_source(data, org_config)

            # Get ad tracking data
            ad_data = get_ad_click_data(data)

            new_lead = frappe.get_doc({
                "doctype": "CRM Lead",
                "first_name": first_name,
                "last_name": last_name,
                "email": email,
                "status": "New",
                "source": source,
                "organization": org_name,
                "ga_client_id": client_id,
                "ad_platform": ad_data['ad_platform'] or None,
                "ad_click_id": ad_data['ad_click_id'] or None,
                "ad_click_timestamp": ad_data['ad_click_timestamp'] or None,
                "ad_landing_page": ad_data['ad_landing_page'] or None
            })
            new_lead.insert(ignore_permissions=True)
            frappe.db.commit()

            link_web_visitor_to_lead(client_id, new_lead.name)
            link_historical_activities_to_lead(client_id, new_lead.name)

            return {
                "success": True,
                "message": "Account created successfully",
                "lead_id": new_lead.name,
                "user_name": first_name
            }

    except Exception as e:
        frappe.logger().error(f"Login error: {str(e)}")
        return {"success": False, "message": str(e)}


@frappe.whitelist(allow_guest=True, methods=['POST'])
def submit_form(**kwargs):
    """Form submission with Facebook ad enrichment"""
    frappe.set_user("Guest")
    frappe.flags.ignore_csrf = True
    
    try:
        data = get_request_data()
        data.update(kwargs)
        
        org_config = identify_organization(data)
        org_name = org_config["org_name"]
        
        if not verify_organization_exists(org_name):
            return {"success": False, "message": f"Organization '{org_name}' not found"}
        
        from campaign_management.clients.base import (
            extract_browser_details,
            get_geo_info_from_ip,
            link_web_visitor_to_lead,
            add_activity_to_lead,
            get_utm_params_from_data,
            link_historical_activities_to_lead,
            get_facebook_ad_data,
            enrich_lead_with_facebook_data
        )
        
        # Extract form fields
        first_name = str(data.get("firstName") or data.get("First Name") or "").strip()
        last_name = str(data.get("lastName") or data.get("Last Name") or "").strip()
        email = str(data.get("email") or data.get("Email") or "").strip().lower()
        phone = str(data.get("phone") or data.get("Mobile No") or "").strip()
        gender = str(data.get("gender") or data.get("Gender") or "").strip()
        company = ""
        message = ""
        client_id = str(data.get("ga_client_id") or data.get("client_id") or "")
        
        if not first_name or (not email and not phone):
            return {"success": False, "message": "Name and Email/Phone required"}
        
        # Tracking data
        user_agent = str(data.get("user_agent") or frappe.get_request_header("User-Agent", ""))
        ip_address = str(data.get("ip_address") or frappe.local.request_ip or "")
        page_url = str(data.get("page_url") or "")
        referrer = str(data.get("referrer") or data.get("page_referrer") or "")
        
        browser_details = extract_browser_details(user_agent)
        geo_info = get_geo_info_from_ip(ip_address)
        utm_params = get_utm_params_from_data(data)
        fb_data = get_facebook_ad_data(data)
        
    
        source = determine_source(data, org_config)
        source_type = "Form" 
        
        # Check existing lead
        existing_lead = find_lead_cross_device(email, client_id, org_name)
        
        if existing_lead:
            # Update existing lead
            lead = frappe.get_doc("CRM Lead", existing_lead['name'])
            
            if phone and not lead.mobile_no:
                lead.mobile_no = phone
            if company and not lead.get('lead_company'):
                lead.lead_company = company
            
            lead.add_comment("Info", f"Form submission: {message}")
            lead.save(ignore_permissions=True)
            
            # Add form submission activity
            add_activity_to_lead(lead.name, {
                "activity_type": "Form Submission",
                "page_url": page_url,
                "timestamp": now(),
                "browser": f"{browser_details['browser']} on {browser_details['os']}",
                "device": browser_details['device'],
                "geo_location": f"{geo_info.get('city')}, {geo_info.get('country')}" if geo_info.get('city') else geo_info.get('country', ''),
                "referrer": referrer,
                "client_id": client_id
            })
            
            frappe.db.commit()
            
            return {
                "success": True,
                "message": "Information updated successfully",
                "lead": lead.name,
                "organization": org_name
            }
        
        else:
            # Create new lead with normalized UTM
            normalized_source = normalize_utm_value(utm_params.get('utm_source'), "source")
            normalized_medium = normalize_utm_value(utm_params.get('utm_medium'), "medium")
            
            lead = frappe.get_doc({
                "doctype": "CRM Lead",
                "first_name": first_name,
                "last_name": last_name,
                "email": email if email else None,
                "mobile_no": phone if phone else None,
                "lead_company": company if company else None,
                "status": "New",
                "source": source,
                "source_type": source_type,  
                "source_name": str(data.get("formName") or "Contact Form"),
                "website": page_url,
                "organization": org_name,
                "ga_client_id": client_id,
                "page_url": page_url,
                "referrer": referrer,
                "utm_source": normalized_source,
                "utm_medium": normalized_medium,
                "utm_campaign": utm_params.get('utm_campaign'),
                "utm_campaign_id": utm_params.get('utm_campaign_id')
            })
            
            # Enrich with Facebook data
            lead = enrich_lead_with_facebook_data(lead, data)
            
            lead.insert(ignore_permissions=True)
            frappe.db.commit()
            
            # Link visitor and MOVE all historic activities to lead
            if client_id:
                link_web_visitor_to_lead(client_id, lead.name)
                link_historical_activities_to_lead(client_id, lead.name)
            
            # Add form submission activity
            add_activity_to_lead(lead.name, {
                "activity_type": "First Form Submission",
                "page_url": page_url,
                "timestamp": now(),
                "browser": f"{browser_details['browser']} on {browser_details['os']}",
                "device": browser_details['device'],
                "geo_location": f"{geo_info.get('city')}, {geo_info.get('country')}" if geo_info.get('city') else geo_info.get('country', ''),
                "referrer": referrer,
                "client_id": client_id
            })
            
            frappe.db.commit()
            
            return {
                "success": True,
                "message": "Thank you! We'll contact you soon.",
                "lead": lead.name,
                "organization": org_name,
                "is_new_lead": True,
                "from_facebook_ad": fb_data['has_facebook_click']
            }
    
    except Exception as e:
        frappe.logger().error(f"Form submission error: {str(e)}")
        frappe.log_error(frappe.get_traceback(), "Form Submit Error")
        return {"success": False, "message": str(e)}

@frappe.whitelist(allow_guest=True, methods=['POST'])
def track_activity(**kwargs):
    """
    Enhanced activity tracker with Facebook ad support
    """
    frappe.set_user("Guest")
    frappe.flags.ignore_csrf = True

    try:
        data = get_request_data()
        data.update(kwargs)

        org_config = identify_organization(data)
        org_name = org_config["org_name"]

        if not verify_organization_exists(org_name):
            return {"success": False, "message": f"Organization '{org_name}' not configured"}

        client_id = data.get("ga_client_id") or data.get("client_id")
        activity_type = str(data.get("activity_type") or data.get("event") or "")
        
        if not client_id:
            return {"success": False, "message": "client_id required"}

        # Facebook Ad Click tracking
        if activity_type == "Facebook Ad Click" or data.get("fbclid"):
            frappe.logger().info("Processing Facebook Ad Click")
            from campaign_management.clients.base import track_facebook_ad_click
            
            result = track_facebook_ad_click(client_id, data, org_name)
            
            return {
                "success": result,
                "message": "Facebook ad click tracked" if result else "Tracking failed",
                "organization": org_name
            }

        # Regular activity tracking 
        page_url = str(data.get("page_url") or data.get("page_location") or "")
        user_agent = str(data.get("user_agent") or frappe.get_request_header("User-Agent", ""))
        ip_address = str(data.get("ip_address") or frappe.local.request_ip or "")
        referrer = str(data.get("referrer") or data.get("page_referrer") or "")

        from campaign_management.clients.base import (
            extract_browser_details,
            get_geo_info_from_ip,
            get_or_create_web_visitor,
            link_web_visitor_to_lead,
            add_activity_to_lead,
            get_utm_params_from_data
        )

        browser_details = extract_browser_details(user_agent)
        geo_info = get_geo_info_from_ip(ip_address)
        utm_params = get_utm_params_from_data(data)

        geo_location = f"{geo_info.get('city')}, {geo_info.get('country')}" if geo_info.get('city') else geo_info.get('country', '')

        visitor = get_or_create_web_visitor(client_id, data)
        frappe.db.set_value("Web Visitor", visitor.name, "last_seen", now(), update_modified=False)

        lead_name = None
        if visitor.converted_lead:
            try:
                lead_org = frappe.db.get_value("CRM Lead", visitor.converted_lead, "organization")
                if lead_org == org_name:
                    lead_name = visitor.converted_lead
            except:
                pass

        if not lead_name and client_id:
            try:
                lead_name = frappe.db.get_value("CRM Lead", {"ga_client_id": client_id, "organization": org_name}, "name")
                if lead_name:
                    link_web_visitor_to_lead(client_id, lead_name)
            except:
                pass

        add_activity_to_lead(lead_name, {
            "activity_type": activity_type,
            "page_url": page_url,
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
            "organization": org_name
        }

    except Exception as e:
        frappe.logger().error(f"Activity tracking error: {str(e)}")
        frappe.log_error(frappe.get_traceback(), "Track Activity Error")
        return {"success": False, "message": str(e)}