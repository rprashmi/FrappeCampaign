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

def enrich_lead_tracking_fields(lead_doc, data, utm_params, normalized_source, normalized_medium, source, client_id):
    """
    Universal enrichment engine — applies ALL tracking fields to any lead doc.
    
    Called for BOTH new and existing leads. Also called from track_activity()
    when a lead is found and the current request carries tracking data.
    
    Attribution rules:
    - ga_client_id: always set if currently empty
    - UTM fields: first-touch wins, never overwrite existing values
    - Ad fields: first-touch wins, never overwrite existing values  
    - source: set only if currently empty
    - organization: backfill if missing
    """
    from campaign_management.clients.base import (
        get_ad_click_data,
        enrich_lead_with_facebook_data
    )

    # Always link ga_client_id if the lead doesn't have one
    if client_id and not lead_doc.get("ga_client_id"):
        lead_doc.ga_client_id = client_id
        frappe.logger().info(f"[Enrich] Set ga_client_id: {client_id}")

    # UTM fields — first touch wins, never overwrite
    if normalized_source and not lead_doc.get("utm_source"):
        lead_doc.utm_source = normalized_source
        frappe.logger().info(f"[Enrich] Set utm_source: {normalized_source}")

    if normalized_medium and not lead_doc.get("utm_medium"):
        lead_doc.utm_medium = normalized_medium
        frappe.logger().info(f"[Enrich] Set utm_medium: {normalized_medium}")

    if utm_params.get("utm_campaign") and not lead_doc.get("utm_campaign"):
        lead_doc.utm_campaign = utm_params.get("utm_campaign")
        frappe.logger().info(f"[Enrich] Set utm_campaign: {utm_params.get('utm_campaign')}")

    if utm_params.get("utm_campaign_id") and not lead_doc.get("utm_campaign_id"):
        lead_doc.utm_campaign_id = utm_params.get("utm_campaign_id")

    if utm_params.get("utm_term") and not lead_doc.get("utm_term"):
        lead_doc.utm_term = utm_params.get("utm_term")

    if utm_params.get("utm_content") and not lead_doc.get("utm_content"):
        lead_doc.utm_content = utm_params.get("utm_content")

    
    if source and not lead_doc.get("source"):
        lead_doc.source = source
        frappe.logger().info(f"[Enrich] Set source: {source}")

    
    ad_data = get_ad_click_data(data)
    if ad_data.get("ad_platform"):
        if not lead_doc.get("ad_platform"):
            lead_doc.ad_platform = ad_data["ad_platform"]
            frappe.logger().info(f"[Enrich] Set ad_platform: {ad_data['ad_platform']}")
        if not lead_doc.get("ad_click_id"):
            
            full_click_id = ad_data["ad_click_id"] or ""
            lead_doc.ad_click_id = full_click_id[:140] if full_click_id else None
            frappe.logger().info(f"[Enrich] Set ad_click_id (truncated): {lead_doc.ad_click_id}")
        if not lead_doc.get("ad_click_id_full"):
           
            lead_doc.ad_click_id_full = ad_data["ad_click_id"]
            frappe.logger().info(f"[Enrich] Set ad_click_id_full: {ad_data['ad_click_id']}")
        if not lead_doc.get("ad_click_timestamp"):
            lead_doc.ad_click_timestamp = ad_data["ad_click_timestamp"]
        if not lead_doc.get("ad_landing_page"):
            
            landing = ad_data["ad_landing_page"] or ""
            lead_doc.ad_landing_page = landing[:140] if landing else None
    else:
        frappe.logger().info(f"[Enrich] No ad click data in this request")

    # Facebook-specific enrichment (fbclid written to Facebook-specific fields, source label etc.)
    # enrich_lead_with_facebook_data already checks internally before overwriting
    lead_doc = enrich_lead_with_facebook_data(lead_doc, data)

    return lead_doc


def find_lead_cross_device(email, client_id, org_name):
    """
    Lead lookup — email is the ONLY uniqueness key.
    client_id is used only to backfill ga_client_id on an existing lead,
    never to block creation of a new one.
    """
    if not email:
        return None

    try:
        # Check same org first
        existing = frappe.db.get_value(
            "CRM Lead",
            {"email": email, "organization": org_name},
            ["name", "email", "mobile_no", "ga_client_id"],
            as_dict=True
        )
        # Fallback: any org
        if not existing:
            existing = frappe.db.get_value(
                "CRM Lead",
                {"email": email},
                ["name", "email", "mobile_no", "ga_client_id"],
                as_dict=True
            )

        if existing:
            frappe.logger().info(f"[find_lead] Found by email: {existing.name}")

            # Backfill org if missing
            if not frappe.db.get_value("CRM Lead", existing.name, "organization"):
                frappe.db.set_value("CRM Lead", existing.name,
                                    "organization", org_name, update_modified=False)

            # Backfill client_id if lead has none (cross-device arrival)
            if client_id and not existing.get("ga_client_id"):
                frappe.db.set_value("CRM Lead", existing.name,
                                    "ga_client_id", client_id, update_modified=False)
                link_web_visitor_to_lead(client_id, existing.name)
                frappe.logger().info(f"[find_lead] Backfilled ga_client_id={client_id}")

            return existing

    except Exception as e:
        frappe.logger().error(f"[find_lead] Error: {str(e)}")

    return None

# ==========================================================
# UPSERT LEAD (CREATE OR UPDATE SAFELY)
# ==========================================================
def get_or_create_lead_upsert(lead_data, email, client_id, org_name):
    """
    UPSERT PATTERN:
    - find lead by email/client_id
    - if exists → return it
    - if not → create safely
    """

    # 1️ Try finding existing lead
    existing = find_lead_cross_device(email, client_id, org_name)

    if existing:
        frappe.logger().info(f"[UPSERT] Existing lead found: {existing['name']}")
        return frappe.get_doc("CRM Lead", existing["name"]), False

    # 2️ Create new lead
    frappe.logger().info("[UPSERT] Creating new lead")

    lead = frappe.get_doc(lead_data)

    try:
        lead.insert(ignore_permissions=True)
        frappe.db.commit()
        return lead, True

    except Exception as e:
        #  race condition protection
        frappe.logger().warning("[UPSERT] Insert failed, retrying fetch")

        existing = find_lead_cross_device(email, client_id, org_name)

        if existing:
            return frappe.get_doc("CRM Lead", existing["name"]), False

        raise e



def normalize_country_to_territory(country_value):
    """
    Convert country data to territory format.
    CRM Lead uses 'territory' field for country/region data.
    
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
            frappe.logger().error(f"Available keys: {list(ORGANIZATION_CONFIG.keys())}")
            raise ValueError(f"Unknown tracking_key: {tracking_key}")
    
    
    page_url = str(data.get("page_url_full") or data.get("page_url") or data.get("page_location") or "")
    if page_url:
        
        display_url = page_url[:100] + "..." if len(page_url) > 100 else page_url
        frappe.logger().info(f"Checking page_url: {display_url}")
        
        try:
            parsed = urlparse(page_url)
            domain = parsed.netloc.lower()
            
            for key, config in ORGANIZATION_CONFIG.items():
                for org_domain in config["domains"]:
                    if org_domain in domain or domain in org_domain:
                        frappe.logger().info(f"Org identified via domain: {key}")
                        return config
        except Exception as e:
            frappe.logger().error(f"Error parsing page_url: {str(e)}")
            # Fallback: simple string matching
            page_url_lower = page_url.lower()
            for key, config in ORGANIZATION_CONFIG.items():
                for org_domain in config["domains"]:
                    if org_domain in page_url_lower:
                        frappe.logger().info(f"Org identified via fallback: {key}")
                        return config

    # 3. Check referrer domain
    referrer = str(data.get("referrer") or data.get("page_referrer") or "").lower()
    if referrer and referrer not in ['direct', '', 'null', 'undefined']:
        frappe.logger().info(f" Checking referrer: {referrer}")
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
    
    """
    try:
        frappe.logger().info(f"🔍 Verifying organization: '{org_name}'")
        
        
        if org_config and org_config.get("crm_organization"):
            crm_org_name = org_config["crm_organization"]
            frappe.logger().info(f"🔗 Using CRM Organization from config: '{crm_org_name}'")
            
            if frappe.db.exists("CRM Organization", crm_org_name):
                frappe.logger().info(f"✅ CRM Organization '{crm_org_name}' exists")
                return True
            else:
                frappe.logger().error(f"❌ CRM Organization '{crm_org_name}' not found in database")
        
        
        if frappe.db.exists("CRM Organization", org_name):
            frappe.logger().info(f"✅ Found CRM Organization directly: '{org_name}'")
            return True
        
       
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
        
        
        frappe.logger().error(f" Organization '{org_name}' not found in CRM")
        
     
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

        log_data = {**data}
        if log_data.get('page_url') and len(str(log_data['page_url'])) > 100:
            log_data['page_url'] = str(log_data['page_url'])[:100] + '...'
        
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

        page_url = str(data.get("page_url_full") or data.get("page_url") or data.get("page_location") or "")
        referrer = str(data.get("referrer") or data.get("page_referrer") or "")
        
        existing_lead = None
        
        if email:
            recent_lead = frappe.db.sql("""
                SELECT name, creation
                FROM `tabCRM Lead`  
                WHERE email = %s
                AND creation > DATE_SUB(NOW(), INTERVAL 30 SECOND)
                ORDER BY creation DESC 
                LIMIT 1
            """, (email,), as_dict=1)
            
            if recent_lead:
                frappe.logger().info(f"[Dedup] Race condition caught — lead exists, forcing enrichment path")
                
                existing_lead = frappe.db.get_value(
                    "CRM Lead",
                    recent_lead[0].name,
                    ["name", "email", "mobile_no", "ga_client_id"],
                    as_dict=True
                )

        browser_details = extract_browser_details(user_agent)
        geo_info = get_geo_info_from_ip(ip_address)

        geo_location = (
            f"{geo_info.get('city')}, {geo_info.get('country')}"
            if geo_info.get("city") else geo_info.get("country", "")
        )

        try:
            parsed = urlparse(page_url)
           
            website_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
            website_url = website_url.rstrip('/')
            
           
            if len(website_url) > 140:
                
                website_url = f"{parsed.scheme}://{parsed.netloc}"
                if len(website_url) > 140:
                    website_url = website_url[:140]
            
            frappe.logger().info(f"📍 Website URL: {website_url}")
            
        except Exception as e:
            frappe.logger().error(f"Error parsing page_url for website: {str(e)}")
            website_url = page_url.split("?")[0][:140]

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

        if not existing_lead:
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

            
            lead = enrich_lead_tracking_fields(
                lead_doc=lead,
                data=data,
                utm_params=utm_params,
                normalized_source=normalized_source,
                normalized_medium=normalized_medium,
                source=source,
                client_id=client_id
            )

            lead.save(ignore_permissions=True)

            if message:
                lead.add_comment("Info", f"Form submission: {message}")

            # Link visitor and migrate historical activities
            # (in case lead was created by another app and visitor was never linked)
            if client_id:
                link_web_visitor_to_lead(client_id, lead.name)
                link_historical_activities_to_lead(client_id, lead.name)

            add_activity_to_lead(lead.name, {
                "activity_type": "Form Submission",
                "page_url": page_url,          
                "timestamp": now(),
                "browser": f"{browser_details['browser']} on {browser_details['os']}",
                "device": browser_details["device"],
                "geo_location": geo_location,
                "referrer": referrer,
                "client_id": client_id,
                "utm_source": normalized_source,
                "utm_medium": normalized_medium,
                "utm_campaign": utm_params.get("utm_campaign"),
                "fbclid": data.get("fbclid") or data.get("ad_click_id_value") or ""
            })

            frappe.db.commit()

            return {
                "success": True,
                "lead": lead.name,
                "organization": org_name,
                "is_new_lead": False,
                "from_facebook_ad": bool(data.get("fbclid") or data.get("ad_click_id_value"))
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

        lead, is_new = get_or_create_lead_upsert(lead_data, email, client_id, org_name)
        lead = enrich_lead_tracking_fields(
            lead_doc=lead,
            data=data,
            utm_params=utm_params,
            normalized_source=normalized_source,
            normalized_medium=normalized_medium,
            source=source,
            client_id=client_id
        )
        lead.save(ignore_permissions=True)
        frappe.db.commit()

        if client_id:
            link_web_visitor_to_lead(client_id, lead.name)
            link_historical_activities_to_lead(client_id, lead.name)

        add_activity_to_lead(lead.name, {
            "activity_type": "First Form Submission" if is_new else "Form Submission",
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
    
    
    
def get_all_leads_for_client(client_id, visitor_converted_lead=None):
    """
    Returns ALL lead names associated with a client_id.
    
    Why: Multiple people can share a browser (same client_id) but each
    submits with their own email → multiple leads with same ga_client_id.
    Activities must fan out to all of them.
    
    Also includes cross-device leads found via visitor.converted_lead.
    """
    lead_names = set()

    if visitor_converted_lead:
        lead_names.add(visitor_converted_lead)

    if client_id:
        matches = frappe.get_all(
            "CRM Lead",
            filters={"ga_client_id": client_id},
            pluck="name"
        )
        lead_names.update(matches)

    return list(lead_names)


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
        #visitor = get_or_create_web_visitor(client_id, data)
        visitor = get_or_create_web_visitor(client_id, data)

        frappe.db.set_value(
            "Web Visitor",
            visitor.name,
            "last_seen",
            now(),
            update_modified=False
        )

        
        # --- Fan-out: find ALL leads for this client_id ---
        all_lead_names = get_all_leads_for_client(
            client_id,
            visitor_converted_lead=visitor.converted_lead if visitor else None
        )

        frappe.logger().info(
            f"[track_activity] client_id={client_id} → "
            f"{len(all_lead_names)} lead(s): {all_lead_names}"
        )

        utm_for_enrich = get_utm_params_from_data(data)
        has_tracking_data = bool(
            data.get("fbclid") or data.get("gclid") or
            data.get("msclkid") or data.get("li_fat_id") or
            data.get("ttclid") or utm_for_enrich.get("utm_source")
        )

        for ln in all_lead_names:
            try:
                # Keep visitor → lead pointer (first-touch only, won't overwrite)
                link_web_visitor_to_lead(client_id, ln)
                link_historical_activities_to_lead(client_id, ln)

                if has_tracking_data:
                    source_for_enrich = determine_source(data, org_config)
                    norm_source = normalize_utm_value(utm_for_enrich.get("utm_source"), "source")
                    norm_medium = normalize_utm_value(utm_for_enrich.get("utm_medium"), "medium")

                    lead_doc = frappe.get_doc("CRM Lead", ln)
                    lead_doc = enrich_lead_tracking_fields(
                        lead_doc=lead_doc,
                        data=data,
                        utm_params=utm_for_enrich,
                        normalized_source=norm_source,
                        normalized_medium=norm_medium,
                        source=source_for_enrich,
                        client_id=client_id
                    )
                    lead_doc.save(ignore_permissions=True)
                    frappe.logger().info(f"[track_activity] Enriched lead {ln}")

            except Exception as enrich_err:
                frappe.logger().error(
                    f"[track_activity] Enrichment failed for {ln}: {str(enrich_err)}"
                )
                frappe.log_error(frappe.get_traceback(), "track_activity Enrichment Error")

        # For activity logging purposes, use first lead (or None = store on visitor)
        lead_name = all_lead_names[0] if all_lead_names else None

        lead_email = str(data.get("lead_email") or "").strip().lower()
        if lead_email:
            try:
                email_lead = frappe.db.get_value(
                    "CRM Lead",
                    {"email": lead_email},
                    ["name", "ga_client_id"],
                    as_dict=True
                )
                if email_lead and email_lead.name not in all_lead_names:
                    frappe.logger().info(
                        f"[track_activity] Cross-device: found lead {email_lead.name} "
                        f"via email={lead_email}"
                    )
                    all_lead_names.append(email_lead.name)
                    lead_name = lead_name or email_lead.name

                    # Backfill new client_id onto that lead if it has none
                    if client_id and not email_lead.get("ga_client_id"):
                        frappe.db.set_value(
                            "CRM Lead", email_lead.name,
                            "ga_client_id", client_id,
                            update_modified=False
                        )
                        
                        
                    # Also link visitor and migrate historical activities
                    link_web_visitor_to_lead(client_id, email_lead.name)
                    link_historical_activities_to_lead(client_id, email_lead.name)

                    # Enrich this cross-device lead with tracking data too
                    if has_tracking_data:
                        try:
                            source_for_enrich = determine_source(data, org_config)
                            norm_source = normalize_utm_value(utm_for_enrich.get("utm_source"), "source")
                            norm_medium = normalize_utm_value(utm_for_enrich.get("utm_medium"), "medium")
                            cd_lead_doc = frappe.get_doc("CRM Lead", email_lead.name)
                            cd_lead_doc = enrich_lead_tracking_fields(
                                lead_doc=cd_lead_doc,
                                data=data,
                                utm_params=utm_for_enrich,
                                normalized_source=norm_source,
                                normalized_medium=norm_medium,
                                source=source_for_enrich,
                                client_id=client_id
                            )
                            cd_lead_doc.save(ignore_permissions=True)
                            frappe.logger().info(f"[track_activity] Cross-device lead {email_lead.name} enriched")
                        except Exception as ce:
                            frappe.logger().error(f"[track_activity] Cross-device enrichment failed: {str(ce)}")

            except Exception as e:
                frappe.logger().error(
                    f"[track_activity] Cross-device email lookup failed: {str(e)}"
                )

        
        activity_type_raw = str(data.get("activity_type") or data.get("event") or "")
        element_text = str(data.get("element_text") or "").strip()
        element_href = str(data.get("element_href") or "").strip()
        nav_item     = str(data.get("nav_item") or "").strip()
        tab_name     = str(data.get("tab_name") or "").strip()
        dom_path     = str(data.get("dom_path") or "").strip()
        page_title   = str(data.get("page_title") or "").strip()
        cta_name     = str(data.get("cta_name") or data.get("link_name") or "").strip()
        cta_location = str(data.get("cta_location") or "").strip()
        href_clean   = element_href.split("?")[0] if element_href else ""

        if activity_type_raw == "nav_click":
            parts = ["Nav Click"]
            if nav_item:           parts.append(nav_item.replace("-", " ").title())
            elif element_text:     parts.append(element_text[:50])
            if href_clean and href_clean != "#": parts.append(f"→ {href_clean}")
            activity_type = " | ".join(parts)

        elif activity_type_raw == "cta_click":
            parts = ["CTA Click"]
            if cta_name:     parts.append(cta_name)
            if cta_location: parts.append(f"in {cta_location}")
            activity_type = " | ".join(parts)

        elif activity_type_raw == "footer_click":
            label = str(data.get("link_name") or element_text or "").strip()
            activity_type = f"Footer Click | {label}" if label else "Footer Click"

        elif activity_type_raw == "tab_click":
            activity_type = f"Tab Click | {tab_name}" if tab_name else "Tab Click"

        elif activity_type_raw == "generic_click":
            label = element_text or href_clean or "unknown"
            activity_type = f"Click | {label[:60]}"

        elif "scroll" in activity_type_raw.lower():
            pct = str(data.get("percent_scrolled", "")).replace("scroll_", "")
            activity_type = f"Scroll {pct}%" if pct else "Scroll"

        elif activity_type_raw == "page_view":
            activity_type = f"Page View | {page_title}" if page_title else "Page View"

        elif activity_type_raw == "form_start":
            fname = str(data.get("form_name") or data.get("form_id") or "").strip()
            activity_type = f"Form Started | {fname}" if fname else "Form Started"

        else:
            activity_type = activity_type_raw

        if not cta_name:
            cta_name = element_text[:80] if element_text else ""
        if not cta_location:
            cta_location = dom_path or activity_type_raw

        tracked_item = (
            data.get("product_name")
            or data.get("feature_name")
            or data.get("service_name")
            or ""
        )

        # Build activity dict once, fan out to ALL leads sharing this client_id
        activity_dict = {
            "activity_type": activity_type,
            "page_url_full": page_url,
            "product_name": tracked_item,
            "cta_name": cta_name,
            "cta_location": cta_location,
            "element_href": element_href,
            "dom_path": dom_path,
            "timestamp": now(),
            "browser": f"{browser_details['browser']} on {browser_details['os']}",
            "device": browser_details["device"],
            "geo_location": geo_location,
            "referrer": referrer,
            "client_id": client_id,
            "user_agent": user_agent,
            **utm_params
        }

        if all_lead_names:
            for ln in all_lead_names:
                add_activity_to_lead(ln, activity_dict)
            activity_saved = True
        else:
            # No leads yet — store against visitor for future migration
            activity_saved = add_activity_to_lead(None, activity_dict)

        frappe.db.commit()

        return {
            "success": True,
            "visitor": visitor.name,
            "linked_leads": all_lead_names,
            "organization": org_name,
            "activity_saved": activity_saved,
            "device_detected": browser_details["device"],
            "utm_captured": {k: v for k, v in utm_params.items() if v}
        }

    except Exception as e:
        frappe.logger().error(f"ACTIVITY TRACKING ERROR: {str(e)}")
        frappe.log_error(frappe.get_traceback(), "Track Activity Error")
        return {"success": False, "message": str(e)}
