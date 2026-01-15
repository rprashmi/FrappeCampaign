from frappe import _

def get_data():
    return {
        "Campaign Management": {
            "color": "orange",
            "icon": "fa fa-bullhorn",
            "label": _("Campaign Management"),
            "type": "module",
            "items": [
                {
                    "type": "page",
                    "name": "campaign-management-home",
                    "label": _("Campaign Workspace"),
                    "icon": "fa fa-window-maximize"
                }
            ]
        }
    }
