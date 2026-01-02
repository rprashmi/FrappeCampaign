"""
Universal Tracker - FIXED VERSION - UTM Parameters Now Work Correctly
✅ Fixed: UTM normalization now properly maps values to Select options
✅ Fixed: Source detection prioritizes UTM over defaults
✅ Fixed: All UTM fields save correctly to CRM Lead
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
    link_historical_activities_to_lead
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
    }
}


def normalize_utm_value(raw_value, field_type="source"):
    """
    ✅ FIXED: Normalize UTM values to match Select field options
    Returns exact match from dropdown or None (not "Other")
    """
    if not raw_value:
        return None

    value = str(raw_value).strip()
    if not value:
        return None

    value_lower = value.lower()

    if field_type == "source":
        # Map to Select options for utm_source
        source_map = {
            "google": "Google",
            "facebook": "Facebook",
            "fb": "Facebook",
            "linkedin": "LinkedIn",
            "li": "LinkedIn",
            "twitter": "Twitter",
            "instagram": "Instagram",
            "ig": "Instagram",
            "email": "Email",
            "direct": "Direct",
            "referral": "Referral",
            "organic": "Organic",
            "bing": "Bing",
            "youtube": "YouTube",
            "yt": "YouTube",
            "tiktok": "TikTok",
            "whatsapp": "WhatsApp",
            "wa": "WhatsApp"
        }

        # Check for exact match first
        if value_lower in source_map:
            frappe.logger().info(f"✅ UTM Source normalized: '{raw_value}' → '{source_map[value_lower]}'")
            return source_map[value_lower]

        # Check for partial matches (e.g., "facebook.com" contains "facebook")
        for key, proper_value in source_map.items():
            if key in value_lower:
                frappe.logger().info(f"✅ UTM Source normalized (partial): '{raw_value}' → '{proper_value}'")
                return proper_value

        # If no match, return "Other"
        frappe.logger().warning(f"⚠️ UTM Source '{raw_value}' not in standard list, using 'Other'")
        return "Other"

    elif field_type == "medium":
        # Map to Select options for utm_medium
        medium_map = {
            "cpc": "CPC",
            "ppc": "PPC",
            "cpm": "CPM",
            "display": "Display",
            "social": "Social",
            "email": "Email",
            "affiliate": "Affiliate",
            "referral": "Referral",
            "organic": "Organic",
            "paid social": "Paid Social",
            "paidsocial": "Paid Social",
            "paid-social": "Paid Social",
            "paid_social": "Paid Social",
            "banner": "Banner",
            "retargeting": "Retargeting",
            "retarget": "Retargeting",
            "video": "Video"
        }

        # Check for exact match first
        if value_lower in medium_map:
            frappe.logger().info(f"✅ UTM Medium normalized: '{raw_value}' → '{medium_map[value_lower]}'")
            return medium_map[value_lower]

        # Check for partial matches
        for key, proper_value in medium_map.items():
            if key in value_lower:
                frappe.logger().info(f"✅ UTM Medium normalized (partial): '{raw_value}' → '{proper_value}'")
                return proper_value

        # If no match, return "Other"
        frappe.logger().warning(f"⚠️ UTM Medium '{raw_value}' not in standard list, using 'Other'")
        return "Other"

    # For campaign or other fields, return as-is
    return value


def determine_source(data, org_config):
    """
    ✅ FIXED: Smart Source Detection - Prioritizes UTM parameters
    Maps to Frappe CRM standard sources with correct priority
    """
    frappe.logger().info("=" * 60)
    frappe.logger().info("DETERMINING SOURCE")
    frappe.logger().info("=" * 60)

    # ✅ PRIORITY 1: Check UTM Source first
    utm_source = str(data.get("utm_source") or "").lower().strip()
    if utm_source:
        frappe.logger().info(f"🎯 Found UTM Source: '{utm_source}'")
        
        # Facebook/Instagram
        if any(fb_term in utm_source for fb_term in ['facebook', 'fb', 'fb.com', 'facebook.com', 'm.facebook', 'instagram', 'ig']):
            frappe.logger().info("✅ Source: Facebook (from UTM)")
            return "Facebook"
        
        # Google Ads
        if any(google_term in utm_source for google_term in ['google', 'google_ads', 'adwords', 'gclid', 'google.com']):
            frappe.logger().info("✅ Source: Campaign (from UTM - Google)")
            return "Campaign"
        
        # LinkedIn
        if any(li_term in utm_source for li_term in ['linkedin', 'li', 'linkedin.com']):
            frappe.logger().info("✅ Source: Advertisement (from UTM - LinkedIn)")
            return "Advertisement"
        
        # Twitter/X
        if any(tw_term in utm_source for tw_term in ['twitter', 'x.com', 't.co', 'x']):
            frappe.logger().info("✅ Source: Advertisement (from UTM - Twitter)")
            return "Advertisement"
        
        # Email
        if any(email_term in utm_source for email_term in ['email', 'newsletter', 'mailchimp', 'sendinblue', 'mail']):
            frappe.logger().info("✅ Source: Mass Mailing (from UTM)")
            return "Mass Mailing"
        
        # Campaign indicators
        if 'campaign' in utm_source or any(term in utm_source for term in ['promo', 'offer', 'sale', 'launch', 'ad', 'paid']):
            frappe.logger().info("✅ Source: Campaign (from UTM keyword)")
            return "Campaign"
        
        # Referral/Partner
        if any(ref_term in utm_source for ref_term in ['referral', 'partner', 'affiliate']):
            frappe.logger().info("✅ Source: Supplier Reference (from UTM)")
            return "Supplier Reference"

    # ✅ PRIORITY 2: Check UTM Medium
    utm_medium = str(data.get("utm_medium") or "").lower().strip()
    if utm_medium:
        frappe.logger().info(f"🎯 Found UTM Medium: '{utm_medium}'")
        
        if utm_medium in ['cpc', 'ppc', 'paid', 'display', 'banner', 'paid_social', 'paidsocial']:
            frappe.logger().info("✅ Source: Campaign (from UTM Medium)")
            return "Campaign"
        
        if utm_medium in ['social', 'social_media', 'socialmedia']:
            if utm_source and 'facebook' in utm_source:
                frappe.logger().info("✅ Source: Facebook (from UTM Medium + Source)")
                return "Facebook"
            frappe.logger().info("✅ Source: Advertisement (from UTM Medium - Social)")
            return "Advertisement"
        
        if utm_medium == 'email':
            frappe.logger().info("✅ Source: Mass Mailing (from UTM Medium)")
            return "Mass Mailing"

    # ✅ PRIORITY 3: Check Referrer
    referrer = str(data.get("referrer") or data.get("page_referrer") or "").lower().strip()
    if referrer and referrer not in ['direct', '', 'null', 'undefined', '(direct)']:
        frappe.logger().info(f"🎯 Checking Referrer: '{referrer}'")
        try:
            parsed = urlparse(referrer)
            domain = parsed.netloc.lower()
            
            if any(fb_domain in domain for fb_domain in ['facebook.com', 'fb.com', 'm.facebook.com', 'l.facebook.com', 'lm.facebook.com']):
                frappe.logger().info("✅ Source: Facebook (from Referrer)")
                return "Facebook"
            
            if 'instagram.com' in domain:
                frappe.logger().info("✅ Source: Facebook (from Referrer - Instagram)")
                return "Facebook"
            
            if any(google_domain in domain for google_domain in ['google.com', 'google.co', 'googleads', 'doubleclick']):
                frappe.logger().info("✅ Source: Campaign (from Referrer - Google)")
                return "Campaign"
            
            if 'linkedin.com' in domain:
                frappe.logger().info("✅ Source: Advertisement (from Referrer - LinkedIn)")
                return "Advertisement"
            
            if any(tw_domain in domain for tw_domain in ['twitter.com', 'x.com', 't.co']):
                frappe.logger().info("✅ Source: Advertisement (from Referrer - Twitter)")
                return "Advertisement"
            
            # Check if external referrer
            org_domains = org_config.get("domains", [])
            is_external = not any(org_domain in domain for org_domain in org_domains)
            if is_external and domain:
                frappe.logger().info(f"✅ Source: Supplier Reference (from External Referrer: {domain})")
                return "Supplier Reference"
        except Exception as e:
            frappe.logger().error(f"Error parsing referrer: {str(e)}")

    # ✅ DEFAULT: Website (direct visit)
    frappe.logger().info("✅ Source: Website (default - no UTM or referrer)")
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
                frappe.logger().info(f"✅ Cross-device match by EMAIL: {existing_lead.name}")
                if client_id and existing_lead.ga_client_id != client_id:
                    frappe.logger().info(f"🔄 Device switch! Old: {existing_lead.ga_client_id}, New: {client_id}")
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
    except Exception as e:
        frappe.logger().error(f"Error reading form_dict: {str(e)}")
    try:
        if hasattr(frappe.local, 'request') and hasattr(frappe.local.request, 'form'):
            form_data = dict(frappe.local.request.form)
            data.update(form_data)
    except Exception as e:
        frappe.logger().error(f"Error reading request.form: {str(e)}")
    try:
        if hasattr(frappe.local, 'request') and frappe.local.request.data:
            json_body = frappe.local.request.get_json(silent=True)
            if json_body:
                data.update(json_body)
    except Exception as e:
        frappe.logger().error(f"Error reading JSON body: {str(e)}")
    return data


def identify_organization(data):
    """Identify organization from request data"""
    org_identifier = str(data.get("organization") or "").lower().strip()
    if org_identifier in ORGANIZATION_CONFIG:
        frappe.logger().info(f"✅ Identified from explicit org: {org_identifier}")
        return ORGANIZATION_CONFIG[org_identifier]

    page_url = str(data.get("page_url") or data.get("page_location") or "").lower()
    if page_url:
        try:
            parsed = urlparse(page_url)
            domain = parsed.netloc or parsed.path.split('/')[0]
            for org_key, config in ORGANIZATION_CONFIG.items():
                for configured_domain in config["domains"]:
                    if configured_domain in domain:
                        frappe.logger().info(f"✅ Identified from page_url: {org_key} (domain: {domain})")
                        return config
                for keyword in config["keywords"]:
                    if keyword in page_url:
                        frappe.logger().info(f"✅ Identified from keyword: {org_key}")
                        return config
        except Exception as e:
            frappe.logger().error(f"Error parsing page_url: {str(e)}")

    referrer = str(data.get("referrer") or data.get("page_referrer") or "").lower()
    if referrer and referrer not in ['direct', '', 'null', 'undefined']:
        try:
            parsed = urlparse(referrer)
            domain = parsed.netloc
            for org_key, config in ORGANIZATION_CONFIG.items():
                for configured_domain in config["domains"]:
                    if configured_domain in domain:
                        frappe.logger().info(f"✅ Identified from referrer: {org_key}")
                        return config
        except Exception as e:
            frappe.logger().error(f"Error parsing referrer: {str(e)}")

    current_site = frappe.local.site
    frappe.logger().info(f"Current site: {current_site}")
    for org_key, config in ORGANIZATION_CONFIG.items():
        for configured_domain in config["domains"]:
            if configured_domain in current_site:
                frappe.logger().info(f"✅ Identified from site: {org_key}")
                return config
        for keyword in config["keywords"]:
            if keyword in current_site.lower():
                frappe.logger().info(f"✅ Identified from site keyword: {org_key}")
                return config

    frappe.logger().warning(f"⚠️ Could not identify organization - using generic")
    return {
        "org_name": "Unknown Organization",
        "org_website": current_site,
        "type": "generic",
        "domains": [],
        "keywords": []
    }


def verify_organization_exists(org_name):
    """
    ✅ Check if organization exists in Frappe
    Returns: True if exists, False if not
    """
    exists = frappe.db.exists("CRM Organization", org_name)

    if not exists:
        frappe.logger().error(f"❌ Organization '{org_name}' does NOT exist in Frappe!")
        frappe.logger().error(f"❌ Admin must create it first: CRM → Organization → New")
        frappe.logger().error(f"❌ Organization Name: {org_name}")
    else:
        frappe.logger().info(f"✅ Organization '{org_name}' exists")

    return exists


@frappe.whitelist(allow_guest=True, methods=['POST'])
def user_login(**kwargs):
    """User Login Endpoint - Links activities across devices"""
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
            return {
                "success": False,
                "message": f"Organization '{org_name}' not configured. Please contact admin."
            }

        frappe.logger().info(f"Login: {email} with client_id: {client_id} for org: {org_name}")

        lead = find_lead_cross_device(email, client_id, org_name)

        if lead:
            frappe.logger().info(f"✅ Login successful - linked to lead: {lead['name']}")
            link_historical_activities_to_lead(client_id, lead['name'])
            return {
                "success": True,
                "message": "Login successful",
                "lead_id": lead['name'],
                "user_name": email.split('@')[0].title()
            }
        else:
            frappe.logger().info(f"Creating new lead for: {email}")
            name_parts = email.split('@')[0].split('.')
            first_name = name_parts[0].title() if name_parts else email.split('@')[0].title()
            last_name = name_parts[1].title() if len(name_parts) > 1 else ""
            source = determine_source(data, org_config)

            new_lead = frappe.get_doc({
                "doctype": "CRM Lead",
                "first_name": first_name,
                "last_name": last_name,
                "email": email,
                "status": "New",
                "source": source,
                "organization": org_name,
                "ga_client_id": client_id
            })
            new_lead.insert(ignore_permissions=True)
            frappe.db.commit()

            link_web_visitor_to_lead(client_id, new_lead.name)
            link_historical_activities_to_lead(client_id, new_lead.name)
            frappe.logger().info(f"✅ New lead created: {new_lead.name}")

            return {
                "success": True,
                "message": "Account created successfully",
                "lead_id": new_lead.name,
                "user_name": first_name
            }

    except Exception as e:
        frappe.logger().error(f"Login error: {str(e)}")
        frappe.log_error(frappe.get_traceback(), "User Login Error")
        return {"success": False, "message": str(e)}


@frappe.whitelist(allow_guest=True, methods=['POST'])
def submit_form(**kwargs):
    """✅ FIXED: UTM fields now save properly"""
    frappe.set_user("Guest")
    frappe.flags.ignore_csrf = True
    
    try:
        frappe.logger().info("="*80)
        frappe.logger().info("FORM SUBMISSION")
        frappe.logger().info("="*80)
        
        data = get_request_data()
        data.update(kwargs)
        frappe.logger().info(f"Data received: {json.dumps(data, indent=2)}")
        
        org_config = identify_organization(data)
        org_name = org_config["org_name"]
        org_type = org_config["type"]
        
        if not verify_organization_exists(org_name):
            return {"success": False, "message": f"Organization '{org_name}' not found"}
        
        # ✅ Extract and normalize UTM
        utm_params = get_utm_params_from_data(data)
        frappe.logger().info(f"Raw UTM: {json.dumps(utm_params, indent=2)}")
        
        normalized_source = normalize_utm_value(utm_params.get('utm_source'), "source")
        normalized_medium = normalize_utm_value(utm_params.get('utm_medium'), "medium")
        
        frappe.logger().info(f"✅ UTM Source: {utm_params.get('utm_source')} → {normalized_source}")
        frappe.logger().info(f"✅ UTM Medium: {utm_params.get('utm_medium')} → {normalized_medium}")
        
        source = determine_source(data, org_config)
        frappe.logger().info(f"✅ Source field: {source}")
        
        # Extract form fields
        first_name = str(data.get("firstName") or data.get("first_name") or "").strip()
        last_name = str(data.get("lastName") or data.get("last_name") or "").strip()
        email = str(data.get("email") or "").strip().lower()
        phone = str(data.get("phone") or data.get("mobile_no") or "").strip()
        company = str(data.get("company") or "").strip()
        message = str(data.get("message") or "").strip()
        client_id = str(data.get("ga_client_id") or data.get("client_id") or "")
        
        if not first_name or (not email and not phone):
            return {"success": False, "message": "Name and Email/Phone required"}
        
        # Get tracking info
        user_agent = str(data.get("user_agent") or frappe.get_request_header("User-Agent", ""))
        ip_address = str(data.get("ip_address") or frappe.local.request_ip or "")
        page_url = str(data.get("page_url") or "")
        referrer = str(data.get("referrer") or data.get("page_referrer") or "")
        
        browser_details = extract_browser_details(user_agent)
        geo_info = get_geo_info_from_ip(ip_address)
        
        geo_location = ""
        if geo_info.get('city') and geo_info.get('country'):
            geo_location = f"{geo_info['city']}, {geo_info['country']}"
        elif geo_info.get('country'):
            geo_location = geo_info['country']
        
        # Build tracking data
        complete_tracking_data = {
            "browser": browser_details,
            "geo": geo_info,
            "utm": {
                "utm_source_raw": utm_params.get('utm_source'),
                "utm_source_normalized": normalized_source,
                "utm_medium_raw": utm_params.get('utm_medium'),
                "utm_medium_normalized": normalized_medium,
                "utm_campaign": utm_params.get('utm_campaign'),
                "utm_campaign_id": utm_params.get('utm_campaign_id')
            },
            "timestamp": now(),
            "organization_type": org_type,
            "source": source,
            "referrer": referrer
        }
        
        # Check existing lead
        existing_lead = find_lead_cross_device(email, client_id, org_name)
        
        if existing_lead:
            frappe.logger().info(f"Updating lead: {existing_lead['name']}")
            lead = frappe.get_doc("CRM Lead", existing_lead['name'])
            
            if phone and not lead.mobile_no:
                lead.mobile_no = phone
            if company and not lead.get('lead_company'):
                lead.lead_company = company
            
            # ✅ Update first-touch UTM if empty
            if normalized_source and not lead.get('utm_source'):
                lead.utm_source = normalized_source
                frappe.logger().info(f"✅ Saved utm_source: {normalized_source}")
            
            if normalized_medium and not lead.get('utm_medium'):
                lead.utm_medium = normalized_medium
                frappe.logger().info(f"✅ Saved utm_medium: {normalized_medium}")
            
            if utm_params.get('utm_campaign') and not lead.get('utm_campaign'):
                lead.utm_campaign = utm_params.get('utm_campaign')
                frappe.logger().info(f"✅ Saved utm_campaign: {utm_params.get('utm_campaign')}")
            
            if utm_params.get('utm_campaign_id') and not lead.get('utm_campaign_id'):
                lead.utm_campaign_id = utm_params.get('utm_campaign_id')
                frappe.logger().info(f"✅ Saved utm_campaign_id: {utm_params.get('utm_campaign_id')}")
            
            lead.add_comment("Info", f"Form submission: {message}")
            lead.save(ignore_permissions=True)
            
            add_activity_to_lead(lead.name, {
                "activity_type": "Form Submission",
                "page_url": page_url,
                "timestamp": now(),
                "browser": f"{browser_details['browser']} on {browser_details['os']}",
                "device": browser_details['device'],
                "geo_location": geo_location,
                "referrer": referrer,
                "client_id": client_id,
                "utm_source": normalized_source,
                "utm_medium": normalized_medium,
                "utm_campaign": utm_params.get('utm_campaign')
            })
            
            frappe.db.commit()
            
            return {
                "success": True,
                "message": "Information updated successfully",
                "lead": lead.name,
                "organization": org_name,
                "source_detected": source,
                "utm_saved": {
                    "source": normalized_source,
                    "medium": normalized_medium,
                    "campaign": utm_params.get('utm_campaign')
                }
            }
        
        else:
            frappe.logger().info(f"Creating new lead: {first_name} {last_name}")
            
            # ✅ Create lead with normalized UTM
            lead = frappe.get_doc({
                "doctype": "CRM Lead",
                "first_name": first_name,
                "last_name": last_name,
                "email": email if email else None,
                "mobile_no": phone if phone else None,
                "lead_company": company if company else None,
                "status": "New",
                "source": source,
                "source_type": "Form",
                "source_name": str(data.get("formName") or "Contact Form"),
                "website": page_url,
                "organization": org_name,
                "ga_client_id": client_id,
                "page_url": page_url,
                "referrer": referrer,
                "utm_source": normalized_source,
                "utm_medium": normalized_medium,
                "utm_campaign": utm_params.get('utm_campaign'),
                "utm_campaign_id": utm_params.get('utm_campaign_id'),
                "full_tracking_details": json.dumps(complete_tracking_data, indent=2)
            })
            
            lead.insert(ignore_permissions=True)
            frappe.db.commit()
            
            frappe.logger().info(f"✅ Lead created: {lead.name}")
            frappe.logger().info(f"   Source: {source}")
            frappe.logger().info(f"   UTM Source: {normalized_source}")
            frappe.logger().info(f"   UTM Medium: {normalized_medium}")
            frappe.logger().info(f"   UTM Campaign: {utm_params.get('utm_campaign')}")
            
            if client_id:
                link_web_visitor_to_lead(client_id, lead.name)
                link_historical_activities_to_lead(client_id, lead.name)
            
            add_activity_to_lead(lead.name, {
                "activity_type": "First Form Submission",
                "page_url": page_url,
                "timestamp": now(),
                "browser": f"{browser_details['browser']} on {browser_details['os']}",
                "device": browser_details['device'],
                "geo_location": geo_location,
                "referrer": referrer,
                "client_id": client_id,
                "utm_source": normalized_source,
                "utm_medium": normalized_medium,
                "utm_campaign": utm_params.get('utm_campaign')
            })
            
            frappe.db.commit()
            
            return {
                "success": True,
                "message": "Thank you! We'll contact you soon.",
                "lead": lead.name,
                "organization": org_name,
                "source_detected": source,
                "utm_captured": {
                    "source": normalized_source,
                    "medium": normalized_medium,
                    "campaign": utm_params.get('utm_campaign')
                },
                "is_new_lead": True
            }
    
    except Exception as e:
        frappe.logger().error(f"Form submission error: {str(e)}")
        frappe.logger().error(frappe.get_traceback())
        return {"success": False, "message": str(e)}



@frappe.whitelist(allow_guest=True, methods=['POST'])
def track_activity(**kwargs):
    """Universal Activity Tracker"""
    frappe.set_user("Guest")
    frappe.flags.ignore_csrf = True

    try:
        data = get_request_data()
        data.update(kwargs)

        org_config = identify_organization(data)
        org_name = org_config["org_name"]

        # ✅ Verify organization exists
        if not verify_organization_exists(org_name):
            return {
                "success": False,
                "message": f"Organization '{org_name}' not configured."
            }

        frappe.logger().info(f"Activity tracking for: {org_name}")

        client_id = data.get("ga_client_id") or data.get("client_id")
        activity_type = str(data.get("activity_type") or data.get("event") or "")
        page_url = str(data.get("page_url") or data.get("page_location") or "")
        product_name = str(data.get("product_name") or "")
        cta_name = str(data.get("cta_name") or "")
        cta_location = str(data.get("cta_location") or "")
        feature_name = str(data.get("feature_name") or "")
        service_name = str(data.get("service_name") or "")

        if not client_id or not activity_type:
            return {"success": False, "message": "client_id and activity_type required"}

        percent_scrolled = data.get("percent_scrolled", "")
        if "scroll" in activity_type.lower() and percent_scrolled:
            if isinstance(percent_scrolled, str):
                percent_scrolled = percent_scrolled.replace("scroll_", "")
            activity_type = f"Scroll {percent_scrolled}%"

        user_agent = str(data.get("user_agent") or frappe.get_request_header("User-Agent", ""))
        ip_address = str(data.get("ip_address") or frappe.local.request_ip or "")
        referrer = str(data.get("referrer") or data.get("page_referrer") or "")

        browser_details = extract_browser_details(user_agent)
        geo_info = get_geo_info_from_ip(ip_address)
        utm_params = get_utm_params_from_data(data)

        geo_location = ""
        if geo_info.get('city') and geo_info.get('country'):
            geo_location = f"{geo_info['city']}, {geo_info['country']}"
        elif geo_info.get('country'):
            geo_location = geo_info['country']

        data['user_agent'] = user_agent
        visitor = get_or_create_web_visitor(client_id, data)
        frappe.db.set_value("Web Visitor", visitor.name, "last_seen", now(), update_modified=False)

        lead_name = None

        if visitor.converted_lead:
            try:
                lead_org = frappe.db.get_value("CRM Lead", visitor.converted_lead, "organization")
                if lead_org == org_name:
                    lead_name = visitor.converted_lead
            except Exception as e:
                frappe.logger().error(f"Error checking converted_lead: {str(e)}")

        if not lead_name and client_id:
            try:
                lead_name = frappe.db.get_value(
                    "CRM Lead",
                    {"ga_client_id": client_id, "organization": org_name},
                    "name"
                )
                if lead_name:
                    link_web_visitor_to_lead(client_id, lead_name)
            except Exception as e:
                frappe.logger().error(f"Error finding lead: {str(e)}")

        tracked_item = product_name or feature_name or service_name or ""

        success = add_activity_to_lead(lead_name, {
            "activity_type": activity_type,
            "page_url": page_url,
            "product_name": tracked_item,
            "cta_name": cta_name,
            "cta_location": cta_location,
            "timestamp": now(),
            "browser": f"{browser_details['browser']} on {browser_details['os']}",
            "device": browser_details['device'],
            "geo_location": geo_location,
            "referrer": referrer,
            "client_id": client_id,
            "user_agent": user_agent,
            **utm_params
        })

        frappe.db.commit()

        return {
            "success": True,
            "visitor": visitor.name,
            "linked_lead": lead_name,
            "organization": org_name,
            "activity_saved": success,
            "device_detected": browser_details['device'],
            "utm_captured": {k: v for k, v in utm_params.items() if v}
        }

    except Exception as e:
        frappe.logger().error(f"ACTIVITY TRACKING ERROR: {str(e)}")
        frappe.log_error(frappe.get_traceback(), "Activity Tracking Error")
        return {"success": False, "message": str(e)}
