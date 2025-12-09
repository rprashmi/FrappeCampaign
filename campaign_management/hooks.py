app_name = "campaign_management"
app_title = "Campaign Management"
app_publisher = "Rashmi"
app_description = "Landing Page & Campaign Builder"
app_email = "rashmi@walue.biz"
app_license = "MIT"

# JavaScript includes
app_include_js = [
    "/assets/campaign_management/js/workspace_my_campaigns.js",
    "/assets/campaign_management/js/gtm_body.js"
]

# DocType JS
doctype_js = {
    "Landing Page Template": "public/js/landing_page_template_list.js",
    "Form Template": "public/js/form_template_list.js",
    "Campaigns": "public/js/campaigns_list.js"
}

# Website route rules for landing pages and forms
website_route_rules = [
    {"from_route": "/lp/<path:slug>", "to_route": "lp"},
    {"from_route": "/forms/<path:slug>", "to_route": "forms"},
]

# CRITICAL: Ignore CSRF for public submissions
#ignore_csrf = [
 #   "campaign_management.api.submit_landing_page_lead",
  #  "campaign_management.api.submit_form_response",
   # "campaign_management.api.track_page_visit"
#]

app_include_head = [
    "/assets/campaign_management/js/gtm_head.html"
]
# Web route handlers
website_generators = []


# Fixtures - Export on bench export-fixtures
fixtures = [
    {
        "dt": "Custom Field",
        "filters": [
            ["dt", "=", "CRM Lead"],
            ["fieldname", "in", [
                "campaign_section",
                "source_type", 
                "source_name",
                "campaign_lead_link",
                "campaign_column"
            ]]
        ]
    }
]
