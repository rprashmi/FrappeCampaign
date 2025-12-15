from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

def get_custom_fields():
    return {
        "CRM Lead": [
            {"fieldname": "ga_client_id", "label": "GA4 Client ID", "fieldtype": "Data", "insert_after": "email_id", "in_list_view": 1, "in_standard_filter": 1, "bold": 1, "description": "Auto-captured from Google Analytics 4"},
            {"fieldname": "campaign_section", "label": "Campaign Information", "fieldtype": "Section Break", "insert_after": "lead_owner"},
            {"fieldname": "utm_source", "label": "UTM Source", "fieldtype": "Data", "insert_after": "campaign_section"},
            {"fieldname": "source_type", "label": "Source Type", "fieldtype": "Select", "options": "Landing Page\nForm", "insert_after": "campaign_section", "in_list_view": 1, "in_standard_filter": 1},
            {"fieldname": "utm_medium", "label": "UTM Medium", "fieldtype": "Data", "insert_after": "utm_source"},
            {"fieldname": "source_name", "label": "Source Name", "fieldtype": "Data", "insert_after": "source_type", "in_list_view": 1},
            {"fieldname": "utm_campaign", "label": "UTM Campaign", "fieldtype": "Data", "insert_after": "utm_medium"},
            {"fieldname": "campaign_lead_link", "label": "Campaign Lead", "fieldtype": "Link", "options": "Campaign Lead", "insert_after": "source_name", "in_list_view": 1, "description": "Click to view detailed tracking information"},
            {"fieldname": "page_url", "label": "Page URL", "fieldtype": "Data", "insert_after": "utm_campaign"},
            {"fieldname": "campaign_column", "fieldtype": "Column Break", "insert_after": "campaign_lead_link"},
            {"fieldname": "referrer", "label": "Referrer", "fieldtype": "Data", "insert_after": "page_url"},
            {"fieldname": "tracking_info", "label": "Tracking Information", "fieldtype": "Code", "options": "JSON", "insert_after": "referrer"},
            {"fieldname": "full_tracking_details", "label": "Full Tracking Details", "fieldtype": "Code", "options": "JSON", "insert_after": "ga_client_id", "read_only": 1, "description": "Complete tracking data including browser, device, geo, and client info"},
        ]
    }

def execute():
    create_custom_fields(get_custom_fields())
