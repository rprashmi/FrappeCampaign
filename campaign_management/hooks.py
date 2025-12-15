app_name = "campaign_management"
app_title = "Campaign Management"
app_publisher = "Rashmi"
app_description = "Landing Page & Campaign Builder"
app_email = "rashmi@walue.biz"
app_license = "MIT"

# JavaScript includes (for Desk)
app_include_js = [
    "/assets/campaign_management/js/workspace_my_campaigns.js",
    "/assets/campaign_management/js/gtm_body.js"
]

# Head includes for website (GTM head script)
app_include_head = [
    "/assets/campaign_management/js/gtm_head.html"
]

# DocType specific JS
doctype_js = {
    "Landing Page Template": "public/js/landing_page_template_list.js",
    "Form Template": "public/js/form_template_list.js",
    "Campaigns": "public/js/campaigns_list.js"
}

# Website route rules
website_route_rules = [
    {"from_route": "/lp/<path:slug>", "to_route": "lp"},
    {"from_route": "/forms/<path:slug>", "to_route": "forms"},
]

# Uncomment if you have public APIs that need CSRF ignore
# after_request = [
#     "campaign_management.api.submit_landing_page_lead",
#     "campaign_management.api.submit_form_response",
#     "campaign_management.api.track_page_visit"
# ]

# Fixtures - Remove or fix this part (see explanation below)
fixtures = []  # Temporarily empty - we'll move to code-based fields

# Add this line for code-based custom fields (permanent fix)
after_migrate = ["campaign_management.custom_fields.execute"]
