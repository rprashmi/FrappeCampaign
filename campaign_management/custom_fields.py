from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

def get_custom_fields():
    return {
        "CRM Lead": [
            {"fieldname": "ga_client_id", "label": "GA4 Client ID", "fieldtype": "Data", "insert_after": "email_id", "in_list_view": 1, "in_standard_filter": 1, "bold": 1, "description": "Auto-captured from Google Analytics 4"},
            {"fieldname": "campaign_section", "label": "Campaign Information", "fieldtype": "Section Break", "insert_after": "lead_owner"},

            # ✅ FIXED: Changed from Data to Select with common UTM sources
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

            # ✅ FIXED: Changed from Data to Select with common UTM mediums
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

            # ✅ OPTION 1: Keep as Data if you have many unique campaigns
            # OR use Select if you have a limited set of campaigns
            {"fieldname": "utm_campaign",
             "label": "UTM Campaign",
             "fieldtype": "Data",  # Keep as Data for flexibility
             "insert_after": "source_name"},

            # Alternative: If you want to use it in charts, uncomment below and comment above
            # {"fieldname": "utm_campaign",
            #  "label": "UTM Campaign",
            #  "fieldtype": "Select",
            #  "options": "\nSummer Sale 2025\nBlack Friday\nProduct Launch\nWebinar Series\nNewsletter\nRetargeting\nBrand Awareness\nOther",
            #  "insert_after": "source_name",
            #  "in_standard_filter": 1},

            {"fieldname": "utm_campaign_id",
             "label": "UTM Campaign ID",
             "fieldtype": "Data",
             "insert_after": "utm_campaign",
             "description": "Campaign ID from advertising platforms (utm_id)"},

            {"fieldname": "lead_company",
             "label": "Lead Company",
             "fieldtype": "Data",
             "insert_after": "utm_campaign_id",
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
             "fieldtype": "Data",
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
        ]
    }

def execute():
    create_custom_fields(get_custom_fields())
