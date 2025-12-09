import frappe
import json
from frappe import _
from frappe.utils import now, get_datetime
from werkzeug.wrappers import Response
import uuid

def bypass_csrf_protection():
    """Bypass CSRF protection for guest submissions."""
    frappe.flags.ignore_csrf = True
    if hasattr(frappe.local, 'request'):
        frappe.local.request.csrf_verified = True


# Import user_agents if installed
try:
    from user_agents import parse as parse_user_agent
    HAS_USER_AGENTS = True
except ImportError:
    HAS_USER_AGENTS = False

# ---------- TRACKING JAVASCRIPT ----------
def get_tracking_script(source_type, source_name):
    """Generate tracking script to embed in pages."""
    return f"""
<script>
// ========== AUTO TRACK PAGE VISIT ON LOAD ==========
(function() {{
    async function trackPageVisit() {{
        const browserData = collectBrowserData();
        const utmParams = getUTM();

        const visitData = new FormData();
        visitData.append('source_type', '{source_type}');
        visitData.append('source_name', '{source_name}');
        visitData.append('page_url', window.location.href);
        visitData.append('referrer', document.referrer || 'Direct');

        Object.entries(browserData).forEach(([key, value]) => {{
            visitData.append(key, value);
        }});

        Object.entries(utmParams).forEach(([key, value]) => {{
            visitData.append(key, value);
        }});

        try {{
            await fetch('/api/method/campaign_management.api.track_page_visit', {{
                method: 'POST',
                body: visitData
            }});
            console.log('✅ Page visit tracked');
        }} catch (error) {{
            console.error('❌ Visit tracking failed:', error);
        }}
    }}

    function collectBrowserData() {{
        const conn = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
        return {{
            screen_resolution: `${{screen.width}}x${{screen.height}}`,
            viewport_size: `${{window.innerWidth}}x${{window.innerHeight}}`,
            color_depth: `${{screen.colorDepth}}-bit`,
            pixel_ratio: window.devicePixelRatio || 1,
            platform: navigator.platform,
            language: navigator.language,
            timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
            user_agent: navigator.userAgent,
            connection_type: conn ? conn.effectiveType : 'unknown'
        }};
    }}

    function getUTM() {{
        const params = new URLSearchParams(window.location.search);
        const utm = {{}};
        ['utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content'].forEach(key => {{
            if (params.has(key)) utm[key] = params.get(key);
        }});
        return utm;
    }}

    // Track on page load
    if (document.readyState === 'loading') {{
        document.addEventListener('DOMContentLoaded', trackPageVisit);
    }} else {{
        trackPageVisit();
    }}

    // Make functions globally available for form submission
    window.collectBrowserData = collectBrowserData;
    window.getUTM = getUTM;
}})();
</script>
"""

# ---------- HELPERS ----------
def _get_site_url():
    try:
        return frappe.utils.get_url()
    except Exception:
        try:
            return frappe.request.host_url
        except Exception:
            return ""

def _file_url(value):
    if not value:
        return ""
    try:
        return frappe.utils.get_url(value)
    except Exception:
        return value

def _replace_placeholders(html_content, doc):
    """Replace placeholders like {{fieldname}} with values from doc."""
    values = {}
    try:
        for field in doc.meta.fields:
            fname = field.fieldname
            val = doc.get(fname) or ""
            if getattr(field, "fieldtype", "") in ("Attach", "Attach Image") and val:
                val = _file_url(val)
            values[fname] = val
    except Exception:
        values = {}

    if "hero_image" in values and values.get("hero_image"):
        values.setdefault("background_image", values.get("hero_image"))

    for k, v in values.items():
        html_content = html_content.replace(f"{{{{{k}}}}}", str(v))
        html_content = html_content.replace(f"{{{{ {k} }}}}", str(v))

    import re
    html_content = re.sub(r"\{\{\s*[a-zA-Z0-9_]+\s*\}\}", "", html_content)
    return html_content

# ---------- RENDER LANDING PAGE WITH TRACKING ----------
def render_landing_page(doc, context=None, is_preview=False):
    """Render landing page with embedded tracking and submission script."""
    template_doc = None
    try:
        template_doc = frappe.get_doc("Landing Page Template", doc.template)
    except Exception:
        template_doc = None

    html_content = ""
    if template_doc and getattr(template_doc, "template_html", None):
        html_content = template_doc.template_html or ""
    else:
        html_content = getattr(doc, "body_content", "") or "<div>No content</div>"

    html_content = _replace_placeholders(html_content, doc)

    preview_banner = """
    <div style="position: fixed; top: 10px; right: 10px; background: rgba(0,0,0,0.8);
                color: white; padding: 8px 16px; border-radius: 6px; z-index: 9999;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                font-size: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.3);">
        👁️ Preview Mode
    </div>
    """

    # Get tracking script
    tracking_script = get_tracking_script("Landing Page", doc.slug or doc.name)

    # Add form submission handler if there's a form
    form_handler = f"""
<script>
// ========== FORM SUBMISSION HANDLER ==========
document.addEventListener('DOMContentLoaded', function() {{
    const forms = document.querySelectorAll('form');

    forms.forEach(form => {{
        // Skip if already has handler
        if (form.dataset.handlerAdded) return;
        form.dataset.handlerAdded = 'true';

        form.addEventListener('submit', async function(e) {{
            e.preventDefault();

            const submitBtn = form.querySelector('button[type="submit"], input[type="submit"]');
            if (submitBtn) {{
                submitBtn.disabled = true;
                submitBtn.dataset.originalText = submitBtn.textContent;
                submitBtn.textContent = 'Submitting...';
            }}

            const formData = new FormData(form);
            formData.append('landing_page', '{doc.slug}');
            formData.append('page_url', window.location.href);
            formData.append('referrer', document.referrer || 'Direct');

            // Add browser data
            if (typeof window.collectBrowserData === 'function') {{
                const browserData = window.collectBrowserData();
                Object.entries(browserData).forEach(([key, value]) => {{
                    formData.append(key, value);
                }});
            }}

            // Add UTM params
            if (typeof window.getUTM === 'function') {{
                const utmParams = window.getUTM();
                Object.entries(utmParams).forEach(([key, value]) => {{
                    formData.append(key, value);
                }});
            }}

            try {{
                const response = await fetch('/api/method/campaign_management.api.submit_landing_page_lead', {{
                    method: 'POST',
                    body: formData
                }});

                const result = await response.json();

                if (result.message && result.message.success) {{
                    alert(result.message.message || 'Thank you! We will contact you soon.');
                    form.reset();
                }} else {{
                    throw new Error(result.message?.message || 'Submission failed');
                }}
            }} catch (error) {{
                console.error('Submission error:', error);
                alert('Error: ' + error.message);
            }} finally {{
                if (submitBtn) {{
                    submitBtn.disabled = false;
                    submitBtn.textContent = submitBtn.dataset.originalText || 'Submit';
                }}
            }}
        }});
    }});
}});
</script>
"""

    stripped = html_content.strip().lower()
    if not (stripped.startswith("<!doctype") or stripped.startswith("<html")):
        html_content = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>{doc.title or 'Landing Page'}</title>
</head>
<body>
{preview_banner if is_preview else ''}
{html_content}
{tracking_script if not is_preview else ''}
{form_handler if not is_preview else ''}
</body>
</html>
"""
    else:
        if is_preview:
            html_content = html_content.replace("<body>", "<body>\n" + preview_banner, 1)
        else:
            # Inject tracking before </body>
            if "</body>" in html_content:
                html_content = html_content.replace("</body>", f"{tracking_script}\n{form_handler}\n</body>", 1)
            else:
                html_content += tracking_script + form_handler

    return html_content

# ---------- BROWSER DETECTION ----------
def extract_browser_details(user_agent_string):
    """Extract detailed browser information."""
    details = {
        "browser_name": "Unknown",
        "browser_version": "Unknown",
        "os_name": "Unknown",
        "os_version": "Unknown",
        "device_type": "Desktop",
        "device_brand": "Unknown",
        "is_mobile": False,
        "is_tablet": False,
        "is_pc": True,
        "is_bot": False
    }

    if not user_agent_string:
        return details

    try:
        if HAS_USER_AGENTS:
            ua = parse_user_agent(user_agent_string)
            details.update({
                "browser_name": ua.browser.family or "Unknown",
                "browser_version": ua.browser.version_string or "Unknown",
                "os_name": ua.os.family or "Unknown",
                "os_version": ua.os.version_string or "Unknown",
                "device_type": "Mobile" if ua.is_mobile else ("Tablet" if ua.is_tablet else "Desktop"),
                "device_brand": ua.device.brand or "Unknown",
                "is_mobile": ua.is_mobile,
                "is_tablet": ua.is_tablet,
                "is_pc": ua.is_pc,
                "is_bot": ua.is_bot
            })
        else:
            ua_lower = user_agent_string.lower()

            if any(x in ua_lower for x in ['mobile', 'android', 'iphone', 'ipod']):
                details["is_mobile"] = True
                details["is_pc"] = False
                details["device_type"] = "Mobile"
            elif 'tablet' in ua_lower or 'ipad' in ua_lower:
                details["is_tablet"] = True
                details["is_pc"] = False
                details["device_type"] = "Tablet"

            if 'chrome' in ua_lower and 'edg' not in ua_lower:
                details["browser_name"] = "Chrome"
            elif 'firefox' in ua_lower:
                details["browser_name"] = "Firefox"
            elif 'safari' in ua_lower and 'chrome' not in ua_lower:
                details["browser_name"] = "Safari"
            elif 'edg' in ua_lower:
                details["browser_name"] = "Edge"

            if 'windows' in ua_lower:
                details["os_name"] = "Windows"
            elif 'mac' in ua_lower:
                details["os_name"] = "macOS"
            elif 'linux' in ua_lower:
                details["os_name"] = "Linux"
            elif 'android' in ua_lower:
                details["os_name"] = "Android"
            elif 'iphone' in ua_lower or 'ipad' in ua_lower:
                details["os_name"] = "iOS"

    except Exception as e:
        frappe.log_error(f"Browser detection error: {str(e)}", "Browser Detection Error")

    return details

def get_geo_info_from_ip(ip_address):
    """Get geographic information from IP."""
    geo_info = {
        'country': None, 'country_code': None, 'region': None,
        'region_code': None, 'city': None, 'postal_code': None,
        'latitude': None, 'longitude': None, 'timezone': None, 'isp': None
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
            params={'fields': 'status,country,countryCode,region,regionName,city,zip,lat,lon,timezone,isp'}
        )

        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 'success':
                geo_info.update({
                    'country': data.get('country'),
                    'country_code': data.get('countryCode'),
                    'region': data.get('regionName'),
                    'region_code': data.get('region'),
                    'city': data.get('city'),
                    'postal_code': data.get('zip'),
                    'latitude': data.get('lat'),
                    'longitude': data.get('lon'),
                    'timezone': data.get('timezone'),
                    'isp': data.get('isp')
                })
    except Exception as e:
        frappe.log_error(f"Geo IP failed: {str(e)}", "Geo IP Error")

    return geo_info

def calculate_lead_score(utm_source, utm_medium, email, has_phone=True):
    """Calculate lead score."""
    score = 50

    if utm_source:
        source_scores = {
            'google': 20, 'linkedin': 15, 'facebook': 10,
            'instagram': 10, 'twitter': 8, 'email': 15,
            'direct': 12, 'bing': 15, 'youtube': 10
        }
        score += source_scores.get(utm_source.lower(), 5)

    if utm_medium:
        medium_scores = {
            'cpc': 15, 'paid': 12, 'organic': 10,
            'social': 8, 'email': 12, 'referral': 10
        }
        score += medium_scores.get(utm_medium.lower(), 5)

    if email:
        score += 10
    if has_phone:
        score += 5

    return min(score, 100)


@frappe.whitelist(allow_guest=True, methods=['GET'])
def get_csrf_token():
    """Return CSRF token for guest forms."""
    # Generate a session for guest if not exists
    if frappe.session.user == "Guest":
        frappe.local.cookie_manager.init_cookies()
    
    return {
        "csrf_token": frappe.sessions.get_csrf_token()
    }

# ---------- API: TRACK PAGE VISIT ----------
@frappe.whitelist(allow_guest=True, methods=['POST'])
def track_page_visit(**kwargs):
    """Track page visit - called automatically when page loads."""
    bypass_csrf_protection()
    frappe.set_user("Guest")
    
    try:
        data = frappe.local.form_dict.copy()

        if frappe.local.request.data:
            try:
                json_body = frappe.local.request.get_json(silent=True) or {}
                data.update(json_body)
            except:
                pass

        source_type = data.get("source_type", "Landing Page")
        source_name = data.get("source_name", "")

        if not source_name:
            return {"success": False, "message": "Source name required"}

        user_agent = frappe.get_request_header("User-Agent", "")
        browser_details = extract_browser_details(user_agent)
        ip_address = frappe.local.request_ip or ""
        geo_info = get_geo_info_from_ip(ip_address)
        session_id = str(uuid.uuid4())

        visit = frappe.get_doc({
            "doctype": "Page Visit",
            "source_type": source_type,
            "source_name": source_name,
            "visitor_ip": ip_address,
            "user_agent": user_agent,
            "browser_name": browser_details.get("browser_name"),
            "browser_version": browser_details.get("browser_version"),
            "os_name": browser_details.get("os_name"),
            "os_version": browser_details.get("os_version"),
            "device_type": browser_details.get("device_type"),
            "country": geo_info.get("country"),
            "city": geo_info.get("city"),
            "region": geo_info.get("region"),
            "isp": geo_info.get("isp"),
            "utm_source": data.get("utm_source"),
            "utm_medium": data.get("utm_medium"),
            "utm_campaign": data.get("utm_campaign"),
            "utm_term": data.get("utm_term"),
            "utm_content": data.get("utm_content"),
            "page_url": data.get("page_url"),
            "referrer": data.get("referrer"),
            "screen_resolution": data.get("screen_resolution"),
            "viewport_size": data.get("viewport_size"),
            "timezone": data.get("timezone"),
            "language": data.get("language"),
            "visited_at": get_datetime(now()),
            "session_id": session_id
        })

        visit.insert(ignore_permissions=True)
        frappe.db.commit()

        # Update views count
        if source_type == "Landing Page":
            try:
                lp = frappe.get_doc("Landing Page", source_name)
                lp.views = (lp.views or 0) + 1
                lp.save(ignore_permissions=True)
                frappe.db.commit()
            except:
                pass
        elif source_type == "Form":
            try:
                form = frappe.get_doc("Dynamic Form", source_name)
                form.views = (form.views or 0) + 1
                form.save(ignore_permissions=True)
                frappe.db.commit()
            except:
                pass

        return {"success": True, "visit_id": visit.name}

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Page Visit Tracking Failed")
        return {"success": False, "message": str(e)}

# ---------- API: SUBMIT LANDING PAGE LEAD ----------
@frappe.whitelist(allow_guest=True, methods=['POST'])
def submit_landing_page_lead(**kwargs):
    """Submit landing page lead."""
    frappe.set_user("Guest")
    frappe.flags.ignore_csrf = True

    try:
        # CRITICAL FIX: Get data from multiple sources
        data = {}
        
        # Method 1: From form_dict
        if frappe.local.form_dict:
            data.update(frappe.local.form_dict)
        
        # Method 2: From request.form (for FormData)
        if hasattr(frappe.local, 'request') and hasattr(frappe.local.request, 'form'):
            data.update(dict(frappe.local.request.form))
        
        # Method 3: From kwargs
        data.update(kwargs)
        
        # Method 4: From JSON body
        if frappe.local.request.data:
            try:
                json_body = frappe.local.request.get_json(silent=True) or {}
                data.update(json_body)
            except:
                pass

        # Log what we received
        frappe.log_error(f"Landing page data received: {json.dumps(data, indent=2)}", "Landing Page Data Debug")

        landing_page_identifier = data.get("landing_page") or data.get("landing_page_slug") or data.get("source_name")

        if not landing_page_identifier:
            return {"success": False, "message": f"Landing page reference missing. Received data: {list(data.keys())}"}

        # Find landing page
        landing_page_doc = None
        try:
            if frappe.db.exists("Landing Page", landing_page_identifier):
                landing_page_doc = frappe.get_doc("Landing Page", landing_page_identifier)
            else:
                landing_page_doc = frappe.get_doc("Landing Page", {
                    "slug": landing_page_identifier,
                    "status": "Published"
                })
        except Exception as e:
            return {"success": False, "message": f"Landing page not found: {str(e)}"}

        # Get form data
        full_name = (data.get("full_name") or data.get("name") or "").strip()
        phone = (data.get("phone") or data.get("mobile") or "").strip()
        email = (data.get("email") or "").strip() or None

        if not full_name:
            return {"success": False, "message": "Name is required"}
        if not phone:
            return {"success": False, "message": "Phone is required"}

        # Get tracking data
        user_agent = frappe.get_request_header("User-Agent", "")
        browser_details = extract_browser_details(user_agent)
        ip_address = frappe.local.request_ip or ""
        geo_info = get_geo_info_from_ip(ip_address)
        lead_score = calculate_lead_score(
            data.get("utm_source"),
            data.get("utm_medium"),
            email,
            has_phone=bool(phone)
        )

        content_info = {
            "browser": browser_details,
            "geo": geo_info,
            "client_data": {
                "screen_resolution": data.get("screen_resolution"),
                "viewport_size": data.get("viewport_size"),
                "timezone": data.get("timezone"),
                "language": data.get("language")
            },
            "lead_score": lead_score,
            "submission_timestamp": now()
        }

        # Create lead
        lead = frappe.get_doc({
            "doctype": "Campaign Lead",
            "landing_page": landing_page_doc.name,
            "campaign": data.get("campaign"),
            "lead_type": "Landing Page",
            "full_name": full_name,
            "phone": phone,
            "email": email,
            "utm_source": data.get("utm_source"),
            "utm_medium": data.get("utm_medium"),
            "utm_campaign": data.get("utm_campaign"),
            "utm_term": data.get("utm_term"),
            "utm_content": data.get("utm_content"),
            "page_url": data.get("page_url"),
            "referrer": data.get("referrer"),
            "user_ip": ip_address,
            "user_agent": user_agent,
            "submitted_at": get_datetime(now()),
            "content_info": json.dumps(content_info),
            "notes": data.get("notes")
        })

        lead.insert(ignore_permissions=True)
        frappe.db.commit()

        # Update submission count
        try:
            lp = frappe.get_doc("Landing Page", landing_page_doc.name)
            lp.submissions = (lp.submissions or 0) + 1
            lp.save(ignore_permissions=True)
            frappe.db.commit()
        except:
            pass

        return {
            "success": True,
            "message": "Thank you! We'll contact you soon.",
            "lead_id": lead.name
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Lead Submission Failed")
        return {"success": False, "message": str(e)}



# ---------- LANDING PAGE APIs ----------
@frappe.whitelist()
def preview_landing_page(name=None, docname=None, **kwargs):
    """Preview landing page."""
    landing_page_name = name or docname or frappe.form_dict.get("name")

    if not landing_page_name:
        frappe.throw("Landing Page name required")

    doc = frappe.get_doc("Landing Page", landing_page_name)
    html_content = render_landing_page(doc, is_preview=True)
    return Response(html_content, content_type='text/html; charset=utf-8')

@frappe.whitelist()
def get_public_url(name=None, docname=None, **kwargs):
    """Get public URL for landing page."""
    landing_page_name = name or docname or frappe.form_dict.get("name")

    if not landing_page_name:
        frappe.throw("Landing Page name required")

    doc = frappe.get_doc("Landing Page", landing_page_name)
    if doc.status != "Published":
        frappe.throw("Landing Page is not published")

    site = frappe.utils.get_url()
    url = f"{site}/lp/{doc.slug}"
    return {"url": url}

@frappe.whitelist(allow_guest=True)
def serve_landing_page(slug=None, **kwargs):
    """Serve published landing page."""
    if not slug:
        slug = kwargs.get('slug') or frappe.form_dict.get('slug')

    if not slug:
        try:
            path = frappe.local.request.path
            parts = [p for p in path.split('/') if p]
            if len(parts) >= 2 and parts[0] == 'lp':
                slug = parts[1]
        except:
            pass

    if not slug:
        frappe.respond_as_web_page("Not Found", "Landing page not found", http_status_code=404)
        return

    try:
        filters = {"slug": slug, "status": "Published"}
        if not frappe.db.exists("Landing Page", filters):
            frappe.respond_as_web_page("Not Found", "Landing page not found", http_status_code=404)
            return

        doc = frappe.get_doc("Landing Page", filters)
        html = render_landing_page(doc, is_preview=False)

        frappe.response['type'] = 'html'
        return html
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Landing Page Serve Error")
        frappe.respond_as_web_page("Error", "Could not load page", http_status_code=500)
        return

# ---------- DYNAMIC FORMS RENDERING ----------
# ---------- DYNAMIC FORMS RENDERING ----------

def render_dynamic_form(doc, is_preview=False):
    """Render Dynamic Form with Default Fields + Browser Tracking + Console Logs"""
    
    # Build fields HTML - Default fields first, then custom fields
    fields_html = ""
    
    # DEFAULT FIELDS (Always present)
    fields_html += """
    <div class="form-group">
        <label for="full_name">Full Name <span class="required">*</span></label>
        <input type="text" id="full_name" name="full_name" placeholder="Enter your full name" required>
    </div>
    
    <div class="form-group">
        <label for="phone">Phone Number <span class="required">*</span></label>
        <input type="tel" id="phone" name="phone" placeholder="e.g. 98765 43210" class="phone-input" required>
        <small style="color:#64748b;display:block;margin-top:6px;">
            Enter your mobile number with country code
        </small>
    </div>
    """
    
    # CUSTOM FIELDS
    if doc.form_fields:
        for field in sorted(doc.form_fields, key=lambda x: x.display_order or 0):
            fields_html += generate_form_field_html(field)

    tracking_script = get_tracking_script("Form", doc.slug or doc.name)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{doc.form_title}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: white;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 2rem;
        }}
        .form-container {{
            max-width: 700px; width: 100%; background: white;
            padding: 3rem 2.5rem; border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
        }}
        h1 {{ font-size: 2.5rem; color: #1e293b; margin-bottom: .5rem; font-weight: 800; }}
        .description {{ font-size: 1.1rem; color: #64748b; margin-bottom: 2.5rem; line-height: 1.6; }}
        .form-group {{ margin-bottom: 1.8rem; }}
        label {{ font-size: .95rem; color: #334155; font-weight: 600; margin-bottom: .5rem; display: block; }}
        .required {{ color: #ef4444; }}
        input, textarea, select {{
            width: 100%; padding: 1rem; border-radius: 10px; border: 2px solid #cbd5e1;
            font-size: 1rem; background: white; transition: all .3s;
        }}
        input:focus, textarea:focus, select:focus {{
            outline: none; border-color: #667eea;
            box-shadow: 0 0 0 3px rgba(102,126,234,.1);
        }}
        .submit-btn {{
            width: 100%; padding: 1.3rem; background: black;
            color: white; font-size: 1.2rem; font-weight: 700; border: none; border-radius: 12px;
            cursor: pointer; text-transform: uppercase; margin-top: 1rem; transition: all .3s;
        }}
        .submit-btn:hover {{ transform: translateY(-3px); box-shadow: 0 10px 30px rgba(102,126,234,.5); }}
        .submit-btn:disabled {{ background: #94a3b8; cursor: not-allowed; transform: none; }}
        .success-message, .error-message {{
            display: none; margin-top: 1.5rem; padding: 1.2rem; border-radius: 12px;
            font-weight: 600; text-align: center;
        }}
        .success-message {{ background: #dcfce7; color: #166534; border: 2px solid #86efac; }}
        .error-message {{ background: #fee2e2; color: #991b1b; border: 2px solid #fca5a5; }}
        .preview-badge {{
            position: fixed; top: 10px; right: 10px; background: rgba(0,0,0,.9);
            color: white; padding: 10px 20px; border-radius: 8px; font-size: 13px; 
            z-index: 9999; font-weight: 600; letter-spacing: 0.5px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        }}
        .iti {{ width: 100%; }}
        .iti__flag-container {{ z-index: 10; }}
        .phone-input {{ padding-left: 60px !important; }}
        .checkbox-group label {{ display: flex; align-items: center; cursor: pointer; }}
        .checkbox-group input[type="checkbox"] {{ 
            width: auto; margin-right: 10px; cursor: pointer; 
            width: 18px; height: 18px;
        }}
    </style>
</head>
<body>
    {'<div class="preview-badge">👁️ PREVIEW MODE</div>' if is_preview else ''}
    <div class="form-container">
        <h1>{doc.form_title}</h1>
        {f'<div class="description">{doc.form_description}</div>' if doc.form_description else ''}
        <form id="dynamicForm">
            <input type="hidden" name="form_slug" value="{doc.slug}">
            <input type="hidden" name="form_name" value="{doc.name}">
            <input type="hidden" name="organisation" value="{doc.organisation or ''}">
            {fields_html}
            <button type="submit" class="submit-btn" id="submitBtn">Submit Form</button>
        </form>
        <div class="success-message" id="successMessage">
            {doc.success_message or 'Thank you! Your response has been submitted successfully.'}
        </div>
        <div class="error-message" id="errorMessage">Something went wrong. Please try again.</div>
    </div>

    {tracking_script if not is_preview else ''}

    <script>
        console.log('🚀 Form Loaded:', {{
            formName: '{doc.name}',
            formSlug: '{doc.slug}',
            isPreview: {str(is_preview).lower()}
        }});

        // Collect and log browser data
        function logBrowserInfo() {{
            const conn = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
            const browserData = {{
                screen_resolution: `${{screen.width}}x${{screen.height}}`,
                viewport_size: `${{window.innerWidth}}x${{window.innerHeight}}`,
                color_depth: `${{screen.colorDepth}}-bit`,
                pixel_ratio: window.devicePixelRatio || 1,
                platform: navigator.platform,
                language: navigator.language,
                timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
                user_agent: navigator.userAgent,
                connection_type: conn ? conn.effectiveType : 'unknown',
                page_url: window.location.href,
                referrer: document.referrer || 'Direct'
            }};
            
            console.log('📊 Browser Data Collected:', browserData);
            return browserData;
        }}

        // Log browser info on load
        const collectedData = logBrowserInfo();

        // CSRF Token Handler
        let csrfToken = null;
        async function getCSRFToken() {{
            if (csrfToken) return csrfToken;
            
            // Check cookies first
            const cookies = document.cookie.split(';');
            for (let c of cookies) {{
                const [n, v] = c.trim().split('=');
                if (n === 'csrf_token') {{ 
                    csrfToken = decodeURIComponent(v); 
                    console.log('✅ CSRF Token from Cookie');
                    return csrfToken; 
                }}
            }}
            
            // Try to get from API
            try {{
                const r = await fetch('/api/method/frappe.auth.get_logged_user', {{ credentials: 'include' }});
                const h = r.headers.get('X-Frappe-CSRF-Token');
                if (h) {{ 
                    csrfToken = h; 
                    console.log('✅ CSRF Token from API');
                    return csrfToken; 
                }}
            }} catch(e) {{
                console.warn('⚠️ CSRF Token fetch failed:', e);
            }}
            return null;
        }}

        // Form Submission Handler
        document.getElementById('dynamicForm').addEventListener('submit', async function(e) {{
            e.preventDefault();
            
            const btn = document.getElementById('submitBtn');
            const originalText = btn.textContent;
            btn.disabled = true; 
            btn.textContent = "Submitting...";
            
            document.getElementById('successMessage').style.display = 'none';
            document.getElementById('errorMessage').style.display = 'none';

            console.log('📤 Starting form submission...');

            const token = await getCSRFToken();
            const fd = new FormData(this);
            
            // Add tracking data
            fd.append('page_url', location.href);
            fd.append('referrer', document.referrer || 'Direct');
            
            // Add browser data
            if (typeof window.collectBrowserData === 'function') {{
                const browserData = window.collectBrowserData();
                Object.entries(browserData).forEach(([k,v]) => {{
                    fd.append(k, v);
                    console.log(`Adding browser data: ${{k}} = ${{v}}`);
                }});
            }} else {{
                // Fallback: add collected data
                Object.entries(collectedData).forEach(([k,v]) => {{
                    fd.append(k, v);
                }});
            }}
            
            // Add UTM params
            if (typeof window.getUTM === 'function') {{
                const utmParams = window.getUTM();
                Object.entries(utmParams).forEach(([k,v]) => {{
                    fd.append(k, v);
                    console.log(`Adding UTM: ${{k}} = ${{v}}`);
                }});
            }}

            // Log all form data
            console.log('📋 Form Data Being Sent:');
            for (let [key, value] of fd.entries()) {{
                console.log(`  ${{key}}: ${{value}}`);
            }}

            try {{
                const headers = token ? {{ 'X-Frappe-CSRF-Token': token }} : {{}};
                console.log('🔐 Headers:', headers);
                
                const res = await fetch('/api/method/campaign_management.api.submit_form_response', {{
                    method: 'POST', 
                    body: fd, 
                    headers, 
                    credentials: 'include'
                }});
                
                console.log('📥 Response Status:', res.status);
                const json = await res.json();
                console.log('📥 Response Data:', json);
                
                if (res.ok && json.message?.success) {{
                    console.log('✅ Form submitted successfully!');
                    document.getElementById('successMessage').style.display = 'block';
                    this.reset();
                    btn.style.display = 'none';
                    document.getElementById('successMessage').scrollIntoView({{behavior:'smooth'}});
                }} else {{
                    throw new Error(json.message?.message || 'Submission failed');
                }}
            }} catch(err) {{
                console.error('❌ Submission Error:', err);
                document.getElementById('errorMessage').textContent = err.message;
                document.getElementById('errorMessage').style.display = 'block';
                document.getElementById('errorMessage').scrollIntoView({{behavior:'smooth'}});
                btn.disabled = false; 
                btn.textContent = originalText;
            }}
        }});
    </script>

    <!-- International Phone Input -->
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/intl-tel-input@19.2.16/build/css/intlTelInput.css">
    <script src="https://cdn.jsdelivr.net/npm/intl-tel-input@19.2.16/build/js/intlTelInput.min.js"></script>
    <script>
        let itiInstance;
        
        document.addEventListener('DOMContentLoaded', function() {{
            const phoneInput = document.querySelector('.phone-input');
            if (phoneInput) {{
                itiInstance = window.intlTelInput(phoneInput, {{
                    initialCountry: "in",
                    preferredCountries: ["in", "us", "gb"],
                    separateDialCode: true,
                    utilsScript: "https://cdn.jsdelivr.net/npm/intl-tel-input@19.2.16/build/js/utils.js",
                }});
                
                console.log('📱 Phone input initialized with country:', itiInstance.getSelectedCountryData().iso2);
            }}
        }});

        // Phone validation on submit
        document.getElementById('dynamicForm').addEventListener('submit', function(e) {{
            const phoneInput = document.querySelector('.phone-input');
            
            if (phoneInput && itiInstance) {{
                // Get full international number
                const fullNumber = itiInstance.getNumber();
                const countryData = itiInstance.getSelectedCountryData();
                
                console.log('📱 Phone Validation:', {{
                    input: phoneInput.value,
                    fullNumber: fullNumber,
                    country: countryData.iso2,
                    dialCode: countryData.dialCode,
                    isValid: itiInstance.isValidNumber()
                }});
                
                if (!itiInstance.isValidNumber()) {{
                    e.preventDefault();
                    alert('Please enter a valid phone number');
                    phoneInput.focus();
                    document.getElementById('submitBtn').disabled = false;
                    document.getElementById('submitBtn').textContent = 'Submit Form';
                    return false;
                }}
                
                // Set the full international number
                phoneInput.value = fullNumber;
                console.log('✅ Phone number set to:', fullNumber);
            }}
        }});
    </script>
</body>
</html>"""
    return html


def generate_form_field_html(field):
    """Generate HTML for a single form field"""
    # Get label - try field_label first, then field_title
    label_text = getattr(field, 'field_label', None) or getattr(field, 'field_title', None) or 'Field'
    field_name_value = getattr(field, 'field_name', None) or 'field'

    required_mark = '<span class="required">*</span>' if getattr(field, 'is_required', False) else ''
    required_attr = 'required' if getattr(field, 'is_required', False) else ''
    placeholder_text = getattr(field, 'placeholder', '') or ''

    field_type = getattr(field, 'field_type', 'Text')

    if field_type == "Text" or field_type == "Data":
        return f"""
        <div class="form-group">
            <label for="{field_name_value}">{label_text} {required_mark}</label>
            <input type="text" id="{field_name_value}" name="{field_name_value}"
                   placeholder="{placeholder_text}" {required_attr}>
        </div>
        """

    elif field_type == "Email":
        return f"""
        <div class="form-group">
            <label for="{field_name_value}">{label_text} {required_mark}</label>
            <input type="email" id="{field_name_value}" name="{field_name_value}"
                   placeholder="{placeholder_text}" {required_attr}>
        </div>
        """

    elif field_type == "Phone":
        return f"""
        <div class="form-group">
            <label for="{field_name_value}">{label_text} {required_mark}</label>
            <input type="tel"
                   id="{field_name_value}"
                   name="{field_name_value}"
                   placeholder="{placeholder_text or 'Enter phone number'}"
                   {required_attr}>
        </div>
        """

    elif field_type == "Int":
        return f"""
        <div class="form-group">
            <label for="{field_name_value}">{label_text} {required_mark}</label>
            <input type="number" id="{field_name_value}" name="{field_name_value}"
                   placeholder="{placeholder_text}" {required_attr}>
        </div>
        """

    elif field_type == "Textarea":
        return f"""
        <div class="form-group">
            <label for="{field_name_value}">{label_text} {required_mark}</label>
            <textarea id="{field_name_value}" name="{field_name_value}"
                      placeholder="{placeholder_text}" rows="4" {required_attr}></textarea>
        </div>
        """

    elif field_type == "Select":
        options_html = '<option value="">-- Select --</option>\n'
        options_text = getattr(field, 'options', '') or ''
        if options_text:
            for option in options_text.split('\n'):
                option = option.strip()
                if option:
                    options_html += f'<option value="{option}">{option}</option>\n'

        return f"""
        <div class="form-group">
            <label for="{field_name_value}">{label_text} {required_mark}</label>
            <select id="{field_name_value}" name="{field_name_value}" {required_attr}>
                {options_html}
            </select>
        </div>
        """

    elif field_type == "Checkbox":
        return f"""
        <div class="form-group checkbox-group">
            <label>
                <input type="checkbox" id="{field_name_value}" name="{field_name_value}"
                       value="1" {required_attr}>
                <span>{label_text} {required_mark}</span>
            </label>
        </div>
        """

    elif field_type == "Date":
        return f"""
        <div class="form-group">
            <label for="{field_name_value}">{label_text} {required_mark}</label>
            <input type="date" id="{field_name_value}" name="{field_name_value}" {required_attr}>
        </div>
        """

    return ""


@frappe.whitelist(allow_guest=True)
def serve_dynamic_form(slug=None, **kwargs):
    """Serve published dynamic form by slug"""
    if not slug:
        slug = kwargs.get('slug') or frappe.form_dict.get('slug')

    if not slug:
        try:
            path = frappe.local.request.path
            parts = [p for p in path.split('/') if p]
            if len(parts) >= 2 and parts[0] == 'forms':
                slug = parts[1]
        except:
            pass

    if not slug:
        frappe.respond_as_web_page("Not Found", "Form not found", http_status_code=404)
        return

    try:
        forms = frappe.get_all("Dynamic Form",
                              filters={"slug": slug, "status": "Published"},
                              limit=1)

        if not forms:
            frappe.respond_as_web_page("Not Found", "Form not found or not published", http_status_code=404)
            return

        form_doc = frappe.get_doc("Dynamic Form", forms[0].name)
        html = render_dynamic_form(form_doc, is_preview=False)

        frappe.response['type'] = 'html'
        return html

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Form Load Error")
        frappe.respond_as_web_page("Error", "Could not load form", http_status_code=500)
        return


@frappe.whitelist(allow_guest=True, methods=['POST'])
def submit_form_response(**kwargs):
    """Submit dynamic form response with full tracking and optional CRM Lead creation"""
    frappe.set_user("Guest")
    frappe.flags.ignore_csrf = True

    try:
        # Collect data from all possible sources
        data = {}

        if frappe.local.form_dict:
            data.update(frappe.local.form_dict)

        if hasattr(frappe.local, 'request') and hasattr(frappe.local.request, 'form'):
            data.update(dict(frappe.local.request.form))

        data.update(kwargs)

        if frappe.local.request.data:
            try:
                json_body = frappe.local.request.get_json(silent=True) or {}
                data.update(json_body)
            except:
                pass

        frappe.logger().info(f"📥 Form submission received: {json.dumps(data, indent=2)}")

        # Find form
        form_identifier = data.get("form_slug") or data.get("form_name")
        if not form_identifier:
            return {"success": False, "message": "Form reference missing"}

        form_doc = None
        try:
            if frappe.db.exists("Dynamic Form", form_identifier):
                form_doc = frappe.get_doc("Dynamic Form", form_identifier)
            else:
                forms = frappe.get_all("Dynamic Form",
                                      filters={"slug": form_identifier},
                                      limit=1)
                if forms:
                    form_doc = frappe.get_doc("Dynamic Form", forms[0].name)
        except Exception as e:
            frappe.logger().error(f"❌ Form lookup error: {str(e)}")
            return {"success": False, "message": f"Form not found: {str(e)}"}

        if not form_doc:
            return {"success": False, "message": "Form not found"}

        # Extract form data
        form_data = {}

        # Get default fields
        full_name = (data.get("full_name") or "").strip()
        phone = (data.get("phone") or "").strip()

        if not full_name:
            return {"success": False, "message": "Full Name is required"}
        if not phone:
            return {"success": False, "message": "Phone Number is required"}

        form_data["full_name"] = full_name
        form_data["phone"] = phone

        # Get organisation (hidden field)
        organisation = data.get("organisation") or form_doc.organisation or ""

        # Get custom fields
        for field in form_doc.form_fields:
            field_name_value = getattr(field, 'field_name', None)
            if not field_name_value:
                continue

            field_value = data.get(field_name_value, "")

            if getattr(field, 'is_required', False) and not field_value:
                field_label = getattr(field, 'field_label', None) or getattr(field, 'field_title', 'This field')
                return {"success": False, "message": f"{field_label} is required"}

            form_data[field_name_value] = field_value

        # Get tracking data
        user_agent = frappe.get_request_header("User-Agent", "")
        browser_details = extract_browser_details(user_agent)
        ip_address = frappe.local.request_ip or ""

        frappe.logger().info(f"🌍 Getting geo info for IP: {ip_address}")
        geo_info = get_geo_info_from_ip(ip_address)
        frappe.logger().info(f"📍 Geo info received: {json.dumps(geo_info, indent=2)}")

        # Build content_info
        content_info = {
            "form_data": form_data,
            "browser": browser_details,
            "geo": geo_info,
            "client_data": {
                "screen_resolution": data.get("screen_resolution"),
                "viewport_size": data.get("viewport_size"),
                "timezone": data.get("timezone"),
                "language": data.get("language"),
                "platform": data.get("platform"),
                "color_depth": data.get("color_depth"),
                "pixel_ratio": data.get("pixel_ratio"),
                "connection_type": data.get("connection_type")
            },
            "submission_timestamp": now()
        }

        # Extract email from form data
        email = (form_data.get("email") or form_data.get("Email") or
                data.get("email") or "")

        # Create Campaign Lead
        lead = frappe.get_doc({
            "doctype": "Campaign Lead",
            "form": form_doc.name,
            "lead_type": "Forms",
            "full_name": full_name,
            "phone": phone,
            "email": email if email else None,
            "utm_source": data.get("utm_source"),
            "utm_medium": data.get("utm_medium"),
            "utm_campaign": data.get("utm_campaign"),
            "utm_term": data.get("utm_term"),
            "utm_content": data.get("utm_content"),
            "page_url": data.get("page_url"),
            "referrer": data.get("referrer"),
            "user_ip": ip_address,
            "user_agent": user_agent,
            "submitted_at": get_datetime(now()),
            "content_info": json.dumps(content_info, indent=2)
        })

        lead.insert(ignore_permissions=True)
        frappe.db.commit()

        frappe.logger().info(f"✅ Campaign Lead created: {lead.name}")

        # Create CRM Lead if checkbox is enabled
        crm_lead_name = None
        if form_doc.create_crm_lead:
            try:
                frappe.logger().info("🔄 Creating CRM Lead...")

                if not frappe.db.exists("DocType", "CRM Lead"):
                    frappe.logger().error("❌ CRM Lead doctype not found!")
                else:
                    # Split full name into first and last name
                    name_parts = full_name.strip().split(maxsplit=1)
                    first_name = name_parts[0] if name_parts else full_name
                    last_name = name_parts[1] if len(name_parts) > 1 else ""

                    crm_lead = frappe.get_doc({
                        "doctype": "CRM Lead",
                        "first_name": first_name,
                        "last_name": last_name,
                        "email": email if email else None,
                        "mobile_no": phone,
                        "organization": organisation,
                        "status": "New",
                        "source": "Dynamic Form",  # ✅ CHANGED: Use source instead of source_type
                        "source_name": form_doc.name,
                        "campaign_lead_link": lead.name
                    })

                    crm_lead.insert(ignore_permissions=True)
                    frappe.db.commit()
                    crm_lead_name = crm_lead.name

                    frappe.logger().info(f"✅ CRM Lead created: {crm_lead_name}")

            except Exception as e:
                frappe.logger().error(f"❌ CRM Lead creation failed: {str(e)}")
                frappe.log_error(frappe.get_traceback(), "CRM Lead Creation Failed")

        # Update submission count
        try:
            form_doc.reload()
            form_doc.submissions = (form_doc.submissions or 0) + 1
            form_doc.save(ignore_permissions=True)
            frappe.db.commit()
        except Exception as e:
            frappe.logger().error(f"Failed to update submission count: {str(e)}")

        response_data = {
            "success": True,
            "message": getattr(form_doc, 'success_message', None) or "Thank you! Your response has been submitted.",
            "lead_id": lead.name
        }

        if crm_lead_name:
            response_data["crm_lead_id"] = crm_lead_name

        return response_data

    except Exception as e:
        frappe.logger().error(f"❌ Form submission failed: {str(e)}")
        frappe.log_error(frappe.get_traceback(), "Form Submission Failed")
        return {"success": False, "message": f"Error: {str(e)}"}

@frappe.whitelist()
def preview_dynamic_form(name=None, docname=None, **kwargs):
    """Preview dynamic form"""
    form_name = name or docname or frappe.form_dict.get("name")

    if not form_name:
        frappe.throw("Form name required")

    doc = frappe.get_doc("Dynamic Form", form_name)
    html_content = render_dynamic_form(doc, is_preview=True)
    return Response(html_content, content_type='text/html; charset=utf-8')


@frappe.whitelist()
def get_form_public_url(name=None, docname=None):
    """Get public URL for form and update the published_url field"""
    form_name = name or docname or frappe.form_dict.get("name")
    if not form_name:
        frappe.throw("Form name required")

    doc = frappe.get_doc("Dynamic Form", form_name)
    
    if doc.status != "Published":
        frappe.throw("Form must be published first")
    
    site_url = frappe.utils.get_url()
    public_url = f"{site_url.rstrip('/')}/forms/{doc.slug}"

    # Update published_url field
    try:
        doc.published_url = public_url
        doc.save(ignore_permissions=True)
        frappe.db.commit()
    except Exception as e:
        frappe.logger().error(f"Failed to update published_url: {str(e)}")

    return {"url": public_url}
