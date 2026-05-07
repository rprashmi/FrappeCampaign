import frappe

def execute():
    """Add custom fields to CRM Lead for campaign tracking"""
    
    custom_fields = {
        "CRM Lead": [
            {
                "fieldname": "campaign_source_type",
                "label": "Campaign Source Type",
                "fieldtype": "Select",
                "options": "Landing Page\nDynamic Form",
                "insert_after": "source",
                "read_only": 1
            },
            {
                "fieldname": "campaign_source_name",
                "label": "Campaign Source Name",
                "fieldtype": "Data",
                "insert_after": "campaign_source_type",
                "read_only": 1
            },
            {
                "fieldname": "utm_source",
                "label": "UTM Source",
                "fieldtype": "Data",
                "insert_after": "campaign_source_name"
            },
            {
                "fieldname": "utm_medium",
                "label": "UTM Medium",
                "fieldtype": "Data",
                "insert_after": "utm_source"
            },
            {
                "fieldname": "utm_campaign",
                "label": "UTM Campaign",
                "fieldtype": "Data",
                "insert_after": "utm_medium"
            },
            {
                "fieldname": "page_url",
                "label": "Page URL",
                "fieldtype": "Data",
                "insert_after": "utm_campaign"
            },
            {
                "fieldname": "referrer",
                "label": "Referrer",
                "fieldtype": "Data",
                "insert_after": "page_url"
            },
            {
                "fieldname": "tracking_info",
                "label": "Tracking Information",
                "fieldtype": "Code",
                "options": "JSON",
                "insert_after": "referrer"
            }
        ]
    }
    
    for doctype, fields in custom_fields.items():
        for field in fields:
            if not frappe.db.exists("Custom Field", {"dt": doctype, "fieldname": field["fieldname"]}):
                custom_field = frappe.get_doc({
                    "doctype": "Custom Field",
                    "dt": doctype,
                    **field
                })
                custom_field.insert(ignore_permissions=True)
                print(f"✅ Added field: {field['fieldname']}")
            else:
                print(f"⏭️  Field already exists: {field['fieldname']}")
                
    frappe.db.commit()
    print("✅ Custom fields setup complete")
