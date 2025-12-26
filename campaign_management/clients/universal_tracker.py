"""
Universal Tracker - Smart Central Handler with Cross-Device Mapping
Auto-detects organization from URL/domain and routes accordingly
Works for ALL websites: QuickShop, Walue, and any future clients
"""
import frappe
from frappe.utils import now
import json
from urllib.parse import urlparse
from campaign_management.clients.base import (
    extract_browser_details,
    get_geo_info_from_ip,
    get_or_create_web_visitor,
    link_web_visitor_to_lead,
    add_activity_to_lead,
    get_utm_params_from_data,
    link_historical_activities_to_lead
)


# Source Mapping Configuration
SOURCE_MAPPING = {
    "facebook": "Facebook",
    "fb": "Facebook",
    "instagram": "Facebook",
    "ig": "Facebook",
    "google": "Campaign",
    "google_ads": "Campaign",
    "adwords": "Campaign",
    "linkedin": "Advertisement",
    "twitter": "Advertisement",
    "x.com": "Advertisement",
    "email": "Mass Mailing",
    "newsletter": "Mass Mailing",
    "cold_call": "Cold Calling",
    "phone": "Cold Calling",
    "exhibition": "Exhibition",
    "event": "Exhibition",
    "trade_show": "Exhibition",
    "referral": "Supplier Reference",
    "partner": "Supplier Reference",
    "walk_in": "Walk In",
    "direct": "Walk In",
    "campaign": "Campaign",
}

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


def determine_source(data, org_config):
    """
    🎯 Smart Source Detection - Maps to Frappe CRM standard sources
    Priority: UTM Source > UTM Medium > Referrer > Default (Website)
    """
    # Method 1: Check UTM source
    utm_source = str(data.get("utm_source") or "").lower().strip()
    if utm_source:
        if "campaign" in utm_source:
            frappe.logger().info(f"✅ Source from UTM: {utm_source} → Campaign")
            return "Campaign"
        
        for key, crm_source in SOURCE_MAPPING.items():
            if key in utm_source:
                frappe.logger().info(f"✅ Source from UTM: {utm_source} → {crm_source}")
                return crm_source
        
        if any(term in utm_source for term in ['promo', 'offer', 'sale', 'launch']):
            frappe.logger().info(f"✅ Source from UTM (promotional): {utm_source} → Campaign")
            return "Campaign"
    
    # Method 2: Check UTM medium
    utm_medium = str(data.get("utm_medium") or "").lower().strip()
    if utm_medium:
        if utm_medium in ['cpc', 'ppc', 'paid', 'display', 'banner']:
            frappe.logger().info(f"✅ Source from UTM medium: {utm_medium} → Campaign")
            return "Campaign"
        elif utm_medium == 'email':
            frappe.logger().info(f"✅ Source from UTM medium: {utm_medium} → Mass Mailing")
            return "Mass Mailing"
    
    # Method 3: Check referrer
    referrer = str(data.get("referrer") or "").lower().strip()
    if referrer and referrer != "direct":
        try:
            parsed = urlparse(referrer)
            domain = parsed.netloc.lower()
            
            for key, crm_source in SOURCE_MAPPING.items():
                if key in domain:
                    frappe.logger().info(f"✅ Source from referrer: {referrer} → {crm_source}")
                    return crm_source
            
            org_domains = org_config.get("domains", [])
            is_external = not any(org_domain in domain for org_domain in org_domains)
            if is_external and domain:
                frappe.logger().info(f"✅ External referrer: {referrer} → Supplier Reference")
                return "Supplier Reference"
        except Exception as e:
            frappe.logger().error(f"Error parsing referrer: {str(e)}")
    
    # Method 4: Check if user is logged in
    user_email = data.get("user_email") or data.get("email")
    if user_email:
        frappe.logger().info(f"✅ Logged in user → Website")
        return "Website"
    
    # Default: Website
    frappe.logger().info(f"✅ Default source → Website")
    return "Website"


def find_lead_cross_device(email, client_id, org_name):
    """
    🔗 Cross-Device Mapping: Find lead by email OR client_id
    Priority: Email > Client ID
    """
    existing_lead = None
    
    # Priority 1: Find by email (most reliable)
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
                
                # Device switch detected - update client_id
                if client_id and existing_lead.ga_client_id != client_id:
                    frappe.logger().info(f"🔄 Device switch! Old: {existing_lead.ga_client_id}, New: {client_id}")
                    frappe.db.set_value("CRM Lead", existing_lead.name, "ga_client_id", client_id, update_modified=False)
                    link_web_visitor_to_lead(client_id, existing_lead.name)
                
                return existing_lead
        except Exception as e:
            frappe.logger().error(f"Error finding by email: {str(e)}")
    
    # Priority 2: Find by client_id
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
    """
    🎯 SMART DETECTION: Automatically identify organization
    YOUR ORIGINAL LOGIC - KEPT EXACTLY AS IS
    """
    # Method 1: Explicit organization identifier
    org_identifier = str(data.get("organization") or "").lower().strip()
    if org_identifier in ORGANIZATION_CONFIG:
        frappe.logger().info(f"✅ Identified from explicit org: {org_identifier}")
        return ORGANIZATION_CONFIG[org_identifier]

    # Method 2: Check page_url domain
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

    # Method 3: Check referrer
    referrer = str(data.get("referrer") or "").lower()
    if referrer and referrer != "direct":
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

    # Method 4: Check current Frappe site
    current_site = frappe.local.site
    frappe.logger().info(f"🌐 Current site: {current_site}")

    for org_key, config in ORGANIZATION_CONFIG.items():
        for configured_domain in config["domains"]:
            if configured_domain in current_site:
                frappe.logger().info(f"✅ Identified from site: {org_key}")
                return config

        for keyword in config["keywords"]:
            if keyword in current_site.lower():
                frappe.logger().info(f"✅ Identified from site keyword: {org_key}")
                return config

    # Default fallback
    frappe.logger().warning(f"⚠️ Could not identify organization - using generic")
    return {
        "org_name": "Unknown Organization",
        "org_website": current_site,
        "type": "generic",
        "domains": [],
        "keywords": []
    }


def ensure_organization_exists(org_config):
    """Create organization if it doesn't exist"""
    org_name = org_config["org_name"]

    if not frappe.db.exists("CRM Organization", org_name):
        org = frappe.get_doc({
            "doctype": "CRM Organization",
            "organization_name": org_name,
            "website": org_config["org_website"]
        })
        org.insert(ignore_permissions=True)
        frappe.db.commit()
        frappe.logger().info(f"✅ Created organization: {org_name}")

    return org_name


@frappe.whitelist(allow_guest=True, methods=['POST'])
def user_login(**kwargs):
    """
    🔐 NEW: User Login Endpoint - Links activities across devices
    """
    frappe.set_user("Guest")
    frappe.flags.ignore_csrf = True
    
    try:
        data = get_request_data()
        data.update(kwargs)
        
        email = str(data.get("email") or "").strip().lower()
        client_id = str(data.get("ga_client_id") or data.get("client_id") or "")
        
        if not email or not client_id:
            return {"success": False, "message": "Email and client_id required"}
        
        # Identify organization
        org_config = identify_organization(data)
        org_name = org_config["org_name"]
        
        frappe.logger().info(f"🔐 Login: {email} with client_id: {client_id} for org: {org_name}")
        
        # Find existing lead by email (cross-device)
        lead = find_lead_cross_device(email, client_id, org_name)
        
        if lead:
            frappe.logger().info(f"✅ Login successful - linked to lead: {lead['name']}")
            
            # Link historical activities from this device
            link_historical_activities_to_lead(client_id, lead['name'])
            
            return {
                "success": True,
                "message": "Login successful",
                "lead_id": lead['name'],
                "user_name": email.split('@')[0].title()
            }
        else:
            # Create new lead
            frappe.logger().info(f"➕ Creating new lead for: {email}")
            
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
            
            # Link web visitor and activities
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
        frappe.logger().error(f"❌ Login error: {str(e)}")
        frappe.log_error(frappe.get_traceback(), "User Login Error")
        return {"success": False, "message": str(e)}


@frappe.whitelist(allow_guest=True, methods=['POST'])
def submit_form(**kwargs):
    """
    🎯 UNIVERSAL FORM HANDLER
    """
    frappe.set_user("Guest")
    frappe.flags.ignore_csrf = True

    try:
        current_site = frappe.local.site
        frappe.logger().info("=" * 80)
        frappe.logger().info("📨 UNIVERSAL FORM SUBMISSION")
        frappe.logger().info(f"🌐 Site: {current_site}")
        frappe.logger().info("=" * 80)

        data = get_request_data()
        data.update(kwargs)

        frappe.logger().info(f"📊 Received Data: {json.dumps(data, indent=2)}")

        # Identify organization (YOUR ORIGINAL LOGIC)
        org_config = identify_organization(data)
        org_name = org_config["org_name"]
        org_type = org_config["type"]

        frappe.logger().info(f"✅ Organization: {org_name} ({org_type})")

        ensure_organization_exists(org_config)

        # NEW: Determine smart source
        source = determine_source(data, org_config)
        frappe.logger().info(f"✅ Determined Source: {source}")

        # Extract fields
        full_name = str(data.get("full_name") or data.get("name") or "").strip()
        first_name = str(data.get("firstName") or data.get("first_name") or "").strip()
        last_name = str(data.get("lastName") or data.get("last_name") or "").strip()

        if first_name and not full_name:
            full_name = f"{first_name} {last_name}".strip()

        email = str(data.get("email") or data.get("lead_email") or data.get("email_id") or "").strip().lower()
        phone = str(data.get("phone") or data.get("mobile_no") or "").strip()
        company = str(data.get("company") or "").strip()
        message = str(data.get("message") or "").strip()

        client_id_raw = data.get("ga_client_id") or data.get("client_id")
        client_id = str(client_id_raw) if client_id_raw else None

        frappe.logger().info(f"✅ Extracted: name={full_name}, email={email}, client_id={client_id}")

        # E-commerce fields
        cart_items = str(data.get("cart_items") or "")
        cart_total = data.get("cart_total", 0)

        # SaaS fields
        request_type = str(data.get("request_type") or data.get("formType") or "General Inquiry")
        form_name = str(data.get("formName") or "")
        interested_features = str(data.get("interested_features") or "")
        company_size = str(data.get("company_size") or "")
        use_case = str(data.get("use_case") or "")

        cta_source = str(data.get("cta_source") or "Direct Visit")

        # Validation
        if not full_name and not first_name:
            frappe.logger().error("❌ Validation failed: Name is required")
            return {"success": False, "message": "Name is required"}
        if not email and not phone:
            frappe.logger().error("❌ Validation failed: Email or Phone is required")
            return {"success": False, "message": "Email or Phone is required"}

        # Get tracking info
        user_agent = str(data.get("user_agent") or frappe.get_request_header("User-Agent", ""))
        ip_address = str(data.get("ip_address") or frappe.local.request_ip or "")
        page_url = str(data.get("page_url") or data.get("page_location") or "")
        referrer = str(data.get("referrer") or "")

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
            "organization_type": org_type,
            "cta_source": cta_source,
            "form_name": form_name,
            "source": source
        }

        if org_type == "ecommerce":
            complete_tracking_data.update({
                "cart_items": cart_items,
                "cart_total": cart_total
            })
        elif org_type == "saas":
            complete_tracking_data.update({
                "request_type": request_type,
                "interested_features": interested_features,
                "company_size": company_size,
                "use_case": use_case,
                "message": message
            })

        # NEW: Cross-device lead detection
        existing_lead = find_lead_cross_device(email, client_id, org_name)

        if existing_lead:
            # UPDATE EXISTING LEAD
            frappe.logger().info(f"🔄 Updating existing lead: {existing_lead['name']}")

            lead = frappe.get_doc("CRM Lead", existing_lead['name'])

            if phone and not lead.mobile_no:
                lead.mobile_no = phone
            if company and not lead.company_name:
                lead.company_name = company

            # Build comment
            if org_type == "ecommerce":
                comment = f"🛒 Order<br>Items: {cart_items}<br>Total: ₹{cart_total}<br>Via: {cta_source}"
                activity_type = f"🛒 Order - ₹{cart_total}"
                product_info = cart_items
            else:
                comment = f"📝 {request_type}<br>Message: {message}<br>Via: {cta_source}"
                activity_type = f"📝 {request_type} ({form_name})"
                product_info = interested_features

            lead.add_comment("Info", comment)
            lead.save(ignore_permissions=True)

            add_activity_to_lead(lead.name, {
                "activity_type": activity_type,
                "page_url": page_url,
                "product_name": product_info,
                "cta_name": cta_source,
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
                "message": "Thank you! Your information has been updated.",
                "lead": lead.name,
                "organization": org_name
            }

        else:
            # CREATE NEW LEAD
            frappe.logger().info(f"➕ Creating new lead: {full_name or (first_name + ' ' + last_name)}")

            if not first_name and full_name:
                name_parts = full_name.strip().split(maxsplit=1)
                first_name = name_parts[0] if name_parts else full_name
                last_name = name_parts[1] if len(name_parts) > 1 else ""

            lead = frappe.get_doc({
                "doctype": "CRM Lead",
                "first_name": first_name,
                "last_name": last_name,
                "email": email if email else None,
                "mobile_no": phone if phone else None,
                "company_name": company if company else None,
                "status": "New",
                "source": source,
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

            frappe.logger().info(f"✅ Lead created: {lead.name} with source: {source}")

            if client_id:
                link_web_visitor_to_lead(client_id, lead.name)
                link_historical_activities_to_lead(client_id, lead.name)

            if org_type == "ecommerce":
                activity_type = f"🛒 First Order - ₹{cart_total}"
                product_info = cart_items
            else:
                activity_type = f"📝 First {request_type} ({form_name})"
                product_info = interested_features

            add_activity_to_lead(lead.name, {
                "activity_type": activity_type,
                "page_url": page_url,
                "product_name": product_info,
                "cta_name": cta_source,
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
                "message": "Thank you! We'll contact you soon.",
                "lead": lead.name,
                "organization": org_name
            }

    except Exception as e:
        frappe.logger().error("=" * 80)
        frappe.logger().error(f"❌ FORM SUBMISSION ERROR: {str(e)}")
        frappe.logger().error(f"❌ Traceback: {frappe.get_traceback()}")
        frappe.logger().error("=" * 80)
        frappe.log_error(frappe.get_traceback(), "Universal Form Error")

        return {
            "success": False,
            "message": f"Error: {str(e)}"
        }


@frappe.whitelist(allow_guest=True, methods=['POST'])
def track_activity(**kwargs):
    """
    🎯 UNIVERSAL ACTIVITY TRACKER
    """
    frappe.set_user("Guest")
    frappe.flags.ignore_csrf = True

    try:
        data = get_request_data()
        data.update(kwargs)

        # Identify organization (YOUR ORIGINAL LOGIC)
        org_config = identify_organization(data)
        org_name = org_config["org_name"]

        frappe.logger().info(f"📊 Activity tracking for: {org_name}")

        client_id = data.get("ga_client_id") or data.get("client_id")
        activity_type = str(data.get("activity_type") or data.get("event") or "")
        page_url = str(data.get("page_url") or data.get("page_location") or "")
        product_name = str(data.get("product_name") or "")
        cta_name = str(data.get("cta_name") or "")
        cta_location = str(data.get("cta_location") or "")
        feature_name = str(data.get("feature_name") or "")
        service_name = str(data.get("service_name") or "")

        if not client_id or not activity_type:
            frappe.logger().error("❌ Missing client_id or activity_type")
            return {"success": False, "message": "client_id and activity_type required"}

        # Handle scroll events
        percent_scrolled = data.get("percent_scrolled", "")
        if "scroll" in activity_type.lower() and percent_scrolled:
            if isinstance(percent_scrolled, str):
                percent_scrolled = percent_scrolled.replace("scroll_", "")
            activity_type = f"📜 Scroll {percent_scrolled}%"

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

        visitor = get_or_create_web_visitor(client_id, data)
        frappe.db.set_value("Web Visitor", visitor.name, "last_seen", now(), update_modified=False)

        # Find linked lead FOR THIS ORGANIZATION
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
            **utm_params
        })

        frappe.db.commit()

        return {
            "success": True,
            "visitor": visitor.name,
            "linked_lead": lead_name,
            "organization": org_name,
            "activity_saved": success
        }

    except Exception as e:
        frappe.logger().error(f"❌ ACTIVITY TRACKING ERROR: {str(e)}")
        frappe.log_error(frappe.get_traceback(), "Activity Tracking Error")
        return {"success": False, "message": str(e)}
