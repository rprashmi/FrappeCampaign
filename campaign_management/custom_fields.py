from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

def get_custom_fields():
    return {
        "CRM Lead": [
            {"fieldname": "ga_client_id", "label": "GA4 Client ID", "fieldtype": "Data", "insert_after": "email_id", "in_list_view": 1, "in_standard_filter": 1, "bold": 1, "description": "Auto-captured from Google Analytics 4"},
            
            {"fieldname": "campaign_section", "label": "Campaign Information", "fieldtype": "Section Break", "insert_after": "lead_owner"},

            {"fieldname": "utm_source",
             "label": "UTM Source",
             "fieldtype": "Select",
             "options": "\nGoogle\nFacebook\nLinkedIn\nTwitter\nInstagram\nEmail\nDirect\nReferral\nOrganic\nBing\nYouTube\nTikTok\nWhatsApp\nOther",
             "insert_after": "campaign_section",
             "in_list_view": 1,
             "in_standard_filter": 1},

            {"fieldname": "source_type",
             "label": "Source Type",
             "fieldtype": "Select",
             "options": "Landing Page\nForm",
             "insert_after": "utm_source",
             "in_list_view": 1,
             "in_standard_filter": 1},

            {"fieldname": "utm_medium",
             "label": "UTM Medium",
             "fieldtype": "Select",
             "options": "\nCPC\nPPC\nCPM\nDisplay\nSocial\nEmail\nAffiliate\nReferral\nOrganic\nPaid Social\nBanner\nRetargeting\nVideo\nOther",
             "insert_after": "source_type",
             "in_standard_filter": 1},

            {"fieldname": "source_name",
             "label": "Source Name",
             "fieldtype": "Data",
             "insert_after": "utm_medium",
             "in_list_view": 1},

            {"fieldname": "utm_campaign",
             "label": "UTM Campaign",
             "fieldtype": "Data",
             "insert_after": "source_name"},

            {"fieldname": "utm_campaign_id",
             "label": "UTM Campaign ID",
             "fieldtype": "Data",
             "insert_after": "utm_campaign",
             "description": "Campaign ID from advertising platforms (utm_id)"},

            # ✅ Ad Tracking Section
            {"fieldname": "ad_tracking_section",
             "label": "Ad Click Tracking",
             "fieldtype": "Section Break",
             "insert_after": "utm_campaign_id",
             "collapsible": 1},

            {"fieldname": "ad_platform",
             "label": "Ad Platform",
             "fieldtype": "Select",
             "options": "\nFacebook/Instagram\nGoogle Ads\nLinkedIn Ads\nMicrosoft Ads\nTwitter Ads\nTikTok Ads\nOther",
             "insert_after": "ad_tracking_section",
             "in_list_view": 1,
             "in_standard_filter": 1,
             "description": "Automatically detected from click ID parameter"},

            {"fieldname": "ad_click_id",
             "label": "Ad Click ID",
             "fieldtype": "Long Text",
             "insert_after": "ad_platform",
             "in_list_view": 1,
             "description": "Unique identifier from ad platform (fbclid, gclid, msclkid, etc.)"},

            {"fieldname": "ad_tracking_column",
             "fieldtype": "Column Break",
             "insert_after": "ad_click_id"},

            {"fieldname": "ad_click_timestamp",
             "label": "Ad Click Time",
             "fieldtype": "Datetime",
             "insert_after": "ad_tracking_column",
             "read_only": 1,
             "description": "When the ad was clicked"},

            {"fieldname": "ad_landing_page",
             "label": "Ad Landing Page",
             "fieldtype": "Data",
             "insert_after": "ad_click_timestamp",
             "read_only": 1,
             "description": "First page visited from ad click"},

            # ✅ FIXED: lead_company now comes AFTER ad fields
            {"fieldname": "lead_company",
             "label": "Lead Company",
             "fieldtype": "Data",
             "insert_after": "ad_landing_page",
             "description": "Company/Business the lead represents"},

            {"fieldname": "campaign_lead_link",
             "label": "Campaign Lead",
             "fieldtype": "Link",
             "options": "Campaign Lead",
             "insert_after": "lead_company",
             "in_list_view": 1,
             "description": "Click to view detailed tracking information"},

            {"fieldname": "page_url",
             "label": "Page URL",
             "fieldtype": "Long Text",
             "insert_after": "campaign_lead_link"},

            {"fieldname": "campaign_column",
             "fieldtype": "Column Break",
             "insert_after": "page_url"},

            {"fieldname": "referrer",
             "label": "Referrer",
             "fieldtype": "Data",
             "insert_after": "campaign_column"},

            {"fieldname": "tracking_info",
             "label": "Tracking Information",
             "fieldtype": "Code",
             "options": "JSON",
             "insert_after": "referrer"},

            {"fieldname": "full_tracking_details",
             "label": "Full Tracking Details",
             "fieldtype": "Code",
             "options": "JSON",
             "insert_after": "tracking_info",
             "read_only": 1,
             "description": "Complete tracking data including browser, device, geo, and client info"},
        ],

        "CRM Organization": [
            {"fieldname": "analytics_section",
             "label": "Analytics",
             "fieldtype": "Section Break",
             "insert_after": "website"},

            {"fieldname": "looker_studio_url",
             "label": "Looker Studio Dashboard",
             "fieldtype": "Data",
             "insert_after": "analytics_section",
             "description": "Embedded Looker Studio URL for GA4 analytics dashboard"},

            {"fieldname": "analytics_column",
             "fieldtype": "Column Break",
             "insert_after": "looker_studio_url"},

            {"fieldname": "ga4_property_id",
             "label": "GA4 Property ID",
             "fieldtype": "Data",
             "insert_after": "analytics_column",
             "description": "Google Analytics 4 Property ID (optional)"},

            # ✅ NEW: Facebook Pixel Configuration
            {"fieldname": "advertising_section",
             "label": "Advertising & Conversion Tracking",
             "fieldtype": "Section Break",
             "insert_after": "ga4_property_id",
             "collapsible": 1},

            {"fieldname": "facebook_pixel_id",
             "label": "Facebook Pixel ID",
             "fieldtype": "Data",
             "insert_after": "advertising_section",
             "description": "Facebook/Instagram Pixel ID for conversion tracking"},

            {"fieldname": "google_ads_conversion_id",
             "label": "Google Ads Conversion ID",
             "fieldtype": "Data",
             "insert_after": "facebook_pixel_id",
             "description": "Google Ads Conversion Tracking ID"},
        ]
    }

def execute():
    create_custom_fields(get_custom_fields())