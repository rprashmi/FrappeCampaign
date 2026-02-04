"""
Universal Tracker - FIXED VERSION WITH ENHANCED DEBUGGING
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


def get_all_tracking_organizations():
    """
    Fetch all active tracking organizations from database.
    Returns dict with tracking_key as keys.
    """
    try:
        orgs = frappe.get_all(
            "Tracking Organization",
            filters={"is_active": 1},
            fields=[
                "name", 
                "organization_name", 
                "tracking_key", 
                "org_type", 
                "domains", 
                "keywords", 
                "crm_organization"
            ]
        )
        
        org_map = {}
        for org in orgs:
            try:
                # Parse JSON fields
                domains = json.loads(org.get("domains") or "[]")
                keywords = json.loads(org.get("keywords") or "[]")
                
                # Use CRM Organization if linked, otherwise use organization_name
                org_name = org.crm_organization if org.crm_organization else org.organization_name
                
                org_map[org.tracking_key.lower()] = {
                    "org_name": org_name,
                    "org_website": domains[0] if domains else "",
                    "type": org.org_type or "other",
                    "domains": [d.lower().strip() for d in domains if d],
                    "keywords": [k.lower().strip() for k in keywords if k],
                    "tracking_org": org.name  # Reference to Tracking Org doctype
                }
                
                frappe.logger().debug(f"Loaded tracking org: {org.tracking_key} -> {org_name}")
                
            except json.JSONDecodeError as e:
                frappe.logger().error(f"Invalid JSON in Tracking Org {org.name}: {str(e)}")
                continue
            except Exception as e:
                frappe.logger().error(f"Error processing Tracking Org {org.name}: {str(e)}")
                continue
        
        frappe.logger().info(f"Loaded {len(org_map)} active tracking organizations")
        return org_map
    
    except Exception as e:
        frappe.logger().error(f"Error fetching tracking organizations: {str(e)}")
        frappe.logger().error(frappe.get_traceback())
        return {}


def get_organization_config_cached():
    """
    Get organization config with caching.
    Cache expires every 5 minutes to pick up new orgs automatically.
    """
    cache_key = "tracking_organizations_config"
    cached_config = frappe.cache().get_value(cache_key)
    
    if cached_config:
        frappe.logger().debug("Using cached organization config")
        return cached_config
    
    # Fetch from DB
    frappe.logger().info("Fetching organization config from database...")
    config = get_all_tracking_organizations()
    
    # Cache for 5 minutes (300 seconds)
    if config:
        frappe.cache().set_value(cache_key, config, expires_in_sec=300)
        frappe.logger().info(f"Cached {len(config)} organizations for 5 minutes")
    
    return config


def clear_organization_cache():
    """
    Clear the organization config cache.
    Call this when Tracking Organization docs are created/updated.
    """
    frappe.cache().delete_value("tracking_organizations_config")
    frappe.logger().info("Organization config cache cleared")


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

    #  1. Check for Ad Click IDs 
    ad_data = get_ad_click_data(data)
    if ad_data['ad_platform']:
        platform = ad_data['ad_platform']
        frappe.logger().info(f" Ad Click Detected: {platform}")
        
        if platform == "Facebook/Instagram":
            frappe.logger().info(" Source: Facebook (from ad click ID)")
            return "Facebook"
        elif platform == "Google Ads":
            frappe.logger().info("Source: Campaign (from Google ad click ID)")
            return "Campaign"
        elif platform == "LinkedIn Ads":
            frappe.logger().info(" Source: Advertisement (from LinkedIn ad click ID)")
            return "Advertisement"
        else:
            frappe.logger().info("Source: Campaign (from ad click ID)")
            return "Campaign"

    # Check UTM Source
    utm_source = str(data.get("utm_source") or "").lower().strip()
    if utm_source:
        frappe.logger().info(f"🎯 Found UTM Source: '{utm_source}'")
        
        if any(fb_term in utm_source for fb_term in ['facebook', 'fb', 'instagram', 'ig']):
            frappe.logger().info(" Source: Facebook (from UTM)")
            return "Facebook"
        
        if any(google_term in utm_source for google_term in ['google', 'google_ads', 'adwords']):
            frappe.logger().info(" Source: Campaign (from UTM - Google)")
            return "Campaign"
        
        if any(li_term in utm_source for li_term in ['linkedin', 'li']):
            frappe.logger().info(" Source: Advertisement (from UTM - LinkedIn)")
            return "Advertisement"
        
        if any(email_term in utm_source for email_term in ['email', 'newsletter']):
            frappe.logger().info(" Source: Mass Mailing (from UTM)")
            return "Mass Mailing"
        
        if 'campaign' in utm_source or any(term in utm_source for term in ['promo', 'offer', 'ad', 'paid']):
            frappe.logger().info(" Source: Campaign (from UTM keyword)")
            return "Campaign"

    # Check UTM Medium
    utm_medium = str(data.get("utm_medium") or "").lower().strip()
    if utm_medium:
        if utm_medium in ['cpc', 'ppc', 'paid', 'display', 'paid_social']:
            frappe.logger().info(" Source: Campaign (from UTM Medium)")
            return "Campaign"
        if utm_medium in ['social']:
            if utm_source and 'facebook' in utm_source:
                return "Facebook"
            frappe.logger().info(" Source: Advertisement (from UTM Medium)")
            return "Advertisement"
        if utm_medium == 'email':
            frappe.logger().info(" Source: Mass Mailing (from UTM Medium)")
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

    frappe.logger().info("Source: Direct (default)")
    frappe.logger().info("=" * 60)
    return "Direct"


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
                frappe.logger().info(f" Found by email: {existing_lead.name}")
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

def normalize_country_to_territory(country_value):
    """
    Convert country data to territory format.
    CRM Lead uses 'territory' field for country/region data.
    
    Args:
        country_value: Country name, code, or territory value
        
    Returns:
        str: Territory value suitable for CRM Lead territory field
    """
    if not country_value:
        return None
    
    # Common country code to name mapping (add more as needed)
    country_map = {
        "US": "United States",
        "USA": "United States",
        "UK": "United Kingdom",
        "GB": "United Kingdom",
        "IN": "India",
        "IND": "India",
        "CA": "Canada",
        "AU": "Australia",
        "AUS": "Australia",
    }
    
    value = str(country_value).strip()
    value_upper = value.upper()
    
    if value_upper in country_map:
        return country_map[value_upper]
    
    return value



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
    """
    Dynamic Organization Detection using Tracking Organization doctype
    
    """
    frappe.logger().info("=" * 60)
    frappe.logger().info("IDENTIFYING ORGANIZATION")
    frappe.logger().info("=" * 60)
    
    # Get dynamic config from database 
    ORGANIZATION_CONFIG = get_organization_config_cached()
    
    if not ORGANIZATION_CONFIG:
        frappe.logger().error(" No active tracking organizations found!")
        frappe.logger().error("Please create at least one Tracking Organization in the system")
        raise ValueError("No tracking organizations configured. Please contact administrator.")
    
    frappe.logger().info(f"Available organizations: {list(ORGANIZATION_CONFIG.keys())}")
    
    # 1. Check explicit tracking_key parameter 
    tracking_key = str(data.get("tracking_key") or data.get("org_key") or "").lower().strip()
    if tracking_key:
        frappe.logger().info(f"🔑 Checking explicit tracking_key: '{tracking_key}'")
        if tracking_key in ORGANIZATION_CONFIG:
            frappe.logger().info(f" Org identified via tracking_key: {tracking_key}")
            return ORGANIZATION_CONFIG[tracking_key]
        else:
            frappe.logger().warning(f" tracking_key '{tracking_key}' not found in config")
    
    # 2. Check page_url domain
    page_url = str(data.get("page_url") or data.get("page_location") or "").lower()
    if page_url:
        frappe.logger().info(f" Checking page_url: {page_url}")
        try:
            parsed = urlparse(page_url)
            domain = parsed.netloc.lower()
            frappe.logger().info(f"   Extracted domain: {domain}")
            
            for key, config in ORGANIZATION_CONFIG.items():
                for org_domain in config["domains"]:
                    if org_domain in domain or domain in org_domain:
                        frappe.logger().info(f" Org identified via page_url domain: {key} (matched: {org_domain})")
                        return config
        except Exception as e:
            frappe.logger().error(f"Error parsing page_url: {str(e)}")
    
    # 3. Check referrer domain
    referrer = str(data.get("referrer") or data.get("page_referrer") or "").lower()
    if referrer and referrer not in ['direct', '', 'null', 'undefined']:
        frappe.logger().info(f"🔗 Checking referrer: {referrer}")
        try:
            parsed = urlparse(referrer)
            domain = parsed.netloc.lower()
            frappe.logger().info(f"   Extracted domain: {domain}")
            
            for key, config in ORGANIZATION_CONFIG.items():
                for org_domain in config["domains"]:
                    if org_domain in domain or domain in org_domain:
                        frappe.logger().info(f" Org identified via referrer domain: {key} (matched: {org_domain})")
                        return config
        except Exception as e:
            frappe.logger().error(f"Error parsing referrer: {str(e)}")
    
    # 4. Check site_domain parameter
    site_domain = str(data.get("site_domain") or "").lower()
    if site_domain:
        frappe.logger().info(f" Checking site_domain: {site_domain}")
        for key, config in ORGANIZATION_CONFIG.items():
            for org_domain in config["domains"]:
                if org_domain in site_domain or site_domain in org_domain:
                    frappe.logger().info(f" Org identified via site_domain: {key} (matched: {org_domain})")
                    return config
    
    # 5. Fallback: keyword matching
    search_text = f"{page_url} {referrer} {site_domain}".lower()
    frappe.logger().info(f" Attempting keyword matching in: {search_text[:100]}...")
    
    for key, config in ORGANIZATION_CONFIG.items():
        keywords = config.get("keywords", [])
        if keywords:
            for keyword in keywords:
                if keyword and keyword in search_text:
                    frappe.logger().info(f" Org identified via keyword match: {key} (keyword: {keyword})")
                    return config
    
    # 6. Default to first organization if only one exists
    if len(ORGANIZATION_CONFIG) == 1:
        default_key = list(ORGANIZATION_CONFIG.keys())[0]
        default_org = ORGANIZATION_CONFIG[default_key]
        frappe.logger().info(f"Only one organization exists, defaulting to: {default_key}")
        frappe.logger().info(f"   Organization: {default_org['org_name']}")
        return default_org
    
    # Could not identify
    frappe.logger().error(" Could not identify organization from request data!")
    frappe.logger().error(f"   Available organizations: {list(ORGANIZATION_CONFIG.keys())}")
    frappe.logger().error(f"   page_url: {page_url}")
    frappe.logger().error(f"   referrer: {referrer}")
    frappe.logger().error(f"   site_domain: {site_domain}")
    frappe.logger().error(f"   tracking_key: {tracking_key}")
    
    raise ValueError(
        f"Could not identify organization. Available: {', '.join(ORGANIZATION_CONFIG.keys())}. "
        f"Please provide tracking_key or ensure domain matches one of the configured domains."
    )

def verify_organization_exists(org_name, org_config=None):
    """
    FIXED: Verify if organization exists in CRM.
    Handles both direct CRM Organization names and Tracking Organization links.
    
    Args:
        org_name: Name to check (from identify_organization)
        org_config: Optional org_config dict with crm_organization field
    
    Returns:
        bool: True if organization exists in CRM, False otherwise
    """
    try:
        frappe.logger().info(f"🔍 Verifying organization: '{org_name}'")
        
        # Method 1: If org_config has crm_organization, use that
        if org_config and org_config.get("crm_organization"):
            crm_org_name = org_config["crm_organization"]
            frappe.logger().info(f"🔗 Using CRM Organization from config: '{crm_org_name}'")
            
            if frappe.db.exists("CRM Organization", crm_org_name):
                frappe.logger().info(f"✅ CRM Organization '{crm_org_name}' exists")
                return True
            else:
                frappe.logger().error(f"❌ CRM Organization '{crm_org_name}' not found in database")
        
        # Method 2: Try direct lookup by org_name
        if frappe.db.exists("CRM Organization", org_name):
            frappe.logger().info(f"✅ Found CRM Organization directly: '{org_name}'")
            return True
        
        # Method 3: Query Tracking Organization for crm_organization link
        tracking_org_data = frappe.db.get_value(
            "Tracking Organization",
            {"organization_name": org_name, "is_active": 1},
            ["crm_organization", "tracking_key"],
            as_dict=True
        )
        
        if tracking_org_data and tracking_org_data.get("crm_organization"):
            crm_org = tracking_org_data["crm_organization"]
            frappe.logger().info(f" Found via Tracking Org (key: {tracking_org_data.get('tracking_key')}). CRM Org: '{crm_org}'")
            
            if frappe.db.exists("CRM Organization", crm_org):
                frappe.logger().info(f" CRM Organization '{crm_org}' exists")
                return True
            else:
                frappe.logger().error(f" Linked CRM Organization '{crm_org}' not found")
        
        # Organization not found - provide detailed debug info
        frappe.logger().error(f" Organization '{org_name}' not found in CRM")
        
        # Debug: List available organizations
        all_crm_orgs = frappe.get_all("CRM Organization", pluck="name", limit=20)
        all_tracking_orgs = frappe.get_all(
            "Tracking Organization",
            filters={"is_active": 1},
            fields=["organization_name", "crm_organization", "tracking_key"],
            limit=20
        )
        
        frappe.logger().error(f"📋 Available CRM Organizations (first 20): {all_crm_orgs}")
        frappe.logger().error(f"📋 Available Tracking Organizations (first 20): {json.dumps(all_tracking_orgs, indent=2)}")
        frappe.logger().error("💡 Fix options:")
        frappe.logger().error("   1. Create a CRM Organization with this exact name")
        frappe.logger().error("   2. OR link an existing CRM Organization in the Tracking Organization")
        
        return False
        
    except Exception as e:
        frappe.logger().error(f"❌ Error verifying organization: {str(e)}")
        frappe.logger().error(frappe.get_traceback())
        return False



@frappe.whitelist(allow_guest=True, methods=['POST'])
def submit_form(**kwargs):
    """
    FIXED: Form submission with enhanced field mapping and debugging
    """
    frappe.set_user("Guest")
    frappe.flags.ignore_csrf = True

    try:
        data = get_request_data()
        data.update(kwargs)

        frappe.logger().info("=" * 80)
        frappe.logger().info("📥 FORM SUBMISSION RECEIVED")
        frappe.logger().info("=" * 80)
        frappe.logger().info(json.dumps(data, indent=2, default=str))
        frappe.logger().info("=" * 80)

        org_config = identify_organization(data)
        org_name = org_config["org_name"]
        org_type = org_config.get("org_type")

        if not verify_organization_exists(org_name):
            return {
                "success": False,
                "message": f"Organization '{org_name}' not found"
            }

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

        first_name = str(
            data.get("firstName") or
            data.get("first_name") or
            data.get("First Name") or ""
        ).strip()

        last_name = str(
            data.get("lastName") or
            data.get("last_name") or
            data.get("Last Name") or ""
        ).strip()

        email = str(
            data.get("lead_email") or
            data.get("email") or ""
        ).strip().lower()

        phone = str(
            data.get("mobileNo") or
            data.get("phone") or 
            data.get("mobile_no") or
            data.get("mobile") or 
            data.get("phoneNumber") or ""
        ).strip()

        gender = str(data.get("gender") or "").strip()
        company = str(data.get("company") or data.get("lead_company") or "").strip()
        country_raw = str(
            data.get("country") or
            data.get("territory") or
            data.get("country_code") or ""
        ).strip()
        territory = normalize_country_to_territory(country_raw)
        #country = str(data.get("country") or "").strip()
        message = str(data.get("message") or data.get("comments") or "").strip()

        client_id = str(
            data.get("ga_client_id") or
            data.get("client_id") or ""
        )

        if not first_name:
            return {"success": False, "message": "First name is required"}

        if not email and not phone:
            return {"success": False, "message": "Email or Phone is required"}

        utm_params = get_utm_params_from_data(data)

        normalized_source = normalize_utm_value(
            utm_params.get("utm_source"), "source"
        )
        normalized_medium = normalize_utm_value(
            utm_params.get("utm_medium"), "medium"
        )

        source = determine_source(data, org_config)
        source_type = "Form"

        fb_data = get_facebook_ad_data(data)

        user_agent = str(
            data.get("user_agent") or
            frappe.get_request_header("User-Agent", "")
        )

        ip_address = str(
            data.get("ip_address") or
            frappe.local.request_ip or ""
        )

        page_url = str(data.get("page_url") or "")
        referrer = str(data.get("referrer") or data.get("page_referrer") or "")

        browser_details = extract_browser_details(user_agent)
        geo_info = get_geo_info_from_ip(ip_address)

        geo_location = (
            f"{geo_info.get('city')}, {geo_info.get('country')}"
            if geo_info.get("city") else geo_info.get("country", "")
        )

        complete_tracking_data = {
            "browser": browser_details,
            "geo": geo_info,
            "utm": {
                "utm_source_raw": utm_params.get("utm_source"),
                "utm_source_normalized": normalized_source,
                "utm_medium_raw": utm_params.get("utm_medium"),
                "utm_medium_normalized": normalized_medium,
                "utm_campaign": utm_params.get("utm_campaign"),
                "utm_campaign_id": utm_params.get("utm_campaign_id")
            },
            "timestamp": now(),
            "organization_type": org_type,
            "source": source,
            "referrer": referrer
        }

        existing_lead = find_lead_cross_device(email, client_id, org_name)

        if existing_lead:
            lead = frappe.get_doc("CRM Lead", existing_lead["name"])

            if phone and not lead.get("mobile_no"):
                lead.mobile_no = phone
                frappe.logger().info(f"Updated phone: {phone}")

            if company and not lead.get("lead_company"):
                lead.lead_company = company
                frappe.logger().info(f"Updated company: {company}")


            if territory and not lead.get("territory"):
                lead.territory = territory
                frappe.logger().info(f"Updated territory: {territory}")

            if gender and not lead.get("gender"):
                lead.gender = gender
                frappe.logger().info(f"Updated gender: {gender}")

            if message:
                lead.add_comment("Info", f"Form submission: {message}")
                frappe.logger().info(f"Added comment")

            if normalized_source and not lead.utm_source:
                lead.utm_source = normalized_source

            if normalized_medium and not lead.utm_medium:
                lead.utm_medium = normalized_medium

            if utm_params.get("utm_campaign") and not lead.utm_campaign:
                lead.utm_campaign = utm_params.get("utm_campaign")

            if utm_params.get("utm_campaign_id") and not lead.utm_campaign_id:
                lead.utm_campaign_id = utm_params.get("utm_campaign_id")

            lead.save(ignore_permissions=True)

            add_activity_to_lead(lead.name, {
                "activity_type": "Form Submission",
                "page_url_full": page_url,
                "timestamp": now(),
                "browser": f"{browser_details['browser']} on {browser_details['os']}",
                "device": browser_details["device"],
                "geo_location": geo_location,
                "referrer": referrer,
                "client_id": client_id,
                "utm_source": normalized_source,
                "utm_medium": normalized_medium,
                "utm_campaign": utm_params.get("utm_campaign")
            })

            frappe.db.commit()

            return {
                "success": True,
                "lead": lead.name,
                "organization": org_name
            }

        website_url = page_url.split("?")[0]
        if len(website_url) > 140:
            website_url = website_url[:140]

        lead_data = {
            "doctype": "CRM Lead",
            "first_name": first_name,
            "last_name": last_name or None,
            "email": email or None,
            "mobile_no": phone or None,
            "gender": gender or None,
            "lead_company": company or None,
            #"country": country or None,
            "territory": territory or None,
            "status": "New",
            "source": source,
            "source_type": source_type,
            "source_name": str(data.get("formName") or "Contact Form"),
            "website": website_url,
            "organization": org_name,
            "ga_client_id": client_id or None,
            "page_url_full": page_url,
            "referrer": referrer,
            "utm_source": normalized_source,
            "utm_medium": normalized_medium,
            "utm_campaign": utm_params.get("utm_campaign"),
            "utm_campaign_id": utm_params.get("utm_campaign_id"),
            "full_tracking_details": json.dumps(
                complete_tracking_data, indent=2, default=str
            )
        }

        lead = frappe.get_doc(lead_data)
        lead = enrich_lead_with_facebook_data(lead, data)
        lead.insert(ignore_permissions=True)
        frappe.db.commit()

        if client_id:
            link_web_visitor_to_lead(client_id, lead.name)
            link_historical_activities_to_lead(client_id, lead.name)

        add_activity_to_lead(lead.name, {
            "activity_type": "First Form Submission",
            "page_url_full": page_url,
            "timestamp": now(),
            "browser": f"{browser_details['browser']} on {browser_details['os']}",
            "device": browser_details["device"],
            "geo_location": geo_location,
            "referrer": referrer,
            "client_id": client_id,
            "utm_source": normalized_source,
            "utm_medium": normalized_medium,
            "utm_campaign": utm_params.get("utm_campaign")
        })

        frappe.db.commit()

        return {
            "success": True,
            "lead": lead.name,
            "organization": org_name,
            "is_new_lead": True,
            "from_facebook_ad": fb_data.get("has_facebook_click")
        }

    except Exception as e:
        frappe.logger().error(frappe.get_traceback())
        return {"success": False, "message": str(e)}


@frappe.whitelist(allow_guest=True, methods=["POST"])
def track_activity(**kwargs):
    """Universal Activity Tracker (Old logic + Facebook Ads support)"""

    frappe.set_user("Guest")
    frappe.flags.ignore_csrf = True

    try:
        data = get_request_data()
        data.update(kwargs)
        org_config = identify_organization(data)
        org_name = org_config["org_name"]

        if not verify_organization_exists(org_name):
            return {
                "success": False,
                "message": f"Organization '{org_name}' not configured."
            }

        frappe.logger().info(f"Activity tracking for: {org_name}")

        client_id = data.get("ga_client_id") or data.get("client_id")
        activity_type = str(data.get("activity_type") or data.get("event") or "")
        page_url = str(data.get("page_url") or data.get("page_location") or "")

        if not client_id or not activity_type:
            return {
                "success": False,
                "message": "client_id and activity_type required"
            }

        from campaign_management.clients.base import (
            extract_browser_details,
            get_geo_info_from_ip,
            get_or_create_web_visitor,
            link_web_visitor_to_lead,
            add_activity_to_lead,
            get_utm_params_from_data,
            track_facebook_ad_click,
            link_historical_activities_to_lead
        )

        if activity_type == "Facebook Ad Click" or data.get("fbclid"):
            frappe.logger().info(f"Processing Facebook Ad Click for client_id={client_id}")
            track_facebook_ad_click(client_id, data, org_name)

        user_agent = str(
            data.get("user_agent") or
            frappe.get_request_header("User-Agent", "")
        )

        ip_address = str(
            data.get("ip_address") or
            frappe.local.request_ip or ""
        )

        referrer = str(data.get("referrer") or data.get("page_referrer") or "")

        browser_details = extract_browser_details(user_agent)
        geo_info = get_geo_info_from_ip(ip_address)
        utm_params = get_utm_params_from_data(data)

        geo_location = ""
        if geo_info.get("city") and geo_info.get("country"):
            geo_location = f"{geo_info['city']}, {geo_info['country']}"
        elif geo_info.get("country"):
            geo_location = geo_info["country"]

        data["user_agent"] = user_agent
        visitor = get_or_create_web_visitor(client_id, data)

        frappe.db.set_value(
            "Web Visitor",
            visitor.name,
            "last_seen",
            now(),
            update_modified=False
        )

        
        lead_name = None
        lead_org = None

        if visitor.converted_lead:
            lead_name = visitor.converted_lead

        if not lead_name and client_id:
            lead_name = frappe.db.get_value(
                "CRM Lead",
                {"ga_client_id": client_id},
                "name"
            )

        if lead_name:
            lead_org = frappe.db.get_value(
                "CRM Lead",
                lead_name,
                "organization"
            )

            if lead_org != org_name:
                frappe.logger().warning(
                    f"Lead {lead_name} belongs to {lead_org}, "
                    f"but activity is for {org_name}. Skipping lead link."
                )
                lead_name = None
            else:
                link_web_visitor_to_lead(client_id, lead_name)
                link_historical_activities_to_lead(client_id, lead_name)

        percent_scrolled = data.get("percent_scrolled", "")
        if "scroll" in activity_type.lower() and percent_scrolled:
            if isinstance(percent_scrolled, str):
                percent_scrolled = percent_scrolled.replace("scroll_", "")
            activity_type = f"Scroll {percent_scrolled}%"

        tracked_item = (
            data.get("product_name")
            or data.get("feature_name")
            or data.get("service_name")
            or ""
        )

        cta_name = (
            data.get("cta_name")
            or data.get("link_name")
            or data.get("nav_item")
            or data.get("formName")
            or ""
        )
    
        cta_location = data.get("cta_location") or activity_type

        success = add_activity_to_lead(lead_name, {
            "activity_type": activity_type,
            "page_url_full": page_url,
            "product_name": tracked_item,
            "cta_name": cta_name,
            "cta_location": cta_location,
            "timestamp": now(),
            "browser": f"{browser_details['browser']} on {browser_details['os']}",
            "device": browser_details["device"],
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
            "device_detected": browser_details["device"],
            "utm_captured": {k: v for k, v in utm_params.items() if v}
        }

    except Exception as e:
        frappe.logger().error(f"ACTIVITY TRACKING ERROR: {str(e)}")
        frappe.log_error(frappe.get_traceback(), "Track Activity Error")
        return {"success": False, "message": str(e)}
