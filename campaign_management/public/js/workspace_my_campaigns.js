frappe.ready(function() {
    console.log('Workspace JS loaded');
    
    // Wait for workspace to fully load
    setTimeout(function() {
        addCampaignButton();
    }, 500);
});

function addCampaignButton() {
    // Check if we're on My Campaigns workspace
    if (!window.location.hash.includes('my-campaigns')) {
        return;
    }
    
    console.log('Adding campaign button');
    
    // Find the workspace container
    const workspace = document.querySelector('.workspace');
    if (!workspace) {
        console.log('Workspace not found, retrying...');
        setTimeout(addCampaignButton, 500);
        return;
    }
    
    // Check if button already exists
    if (document.getElementById('campaignCreateBtn')) {
        return;
    }
    
    // Create button container
    const btnContainer = document.createElement('div');
    btnContainer.style.cssText = 'position: fixed; top: 80px; right: 20px; z-index: 999;';
    
    // Create button
    const btn = document.createElement('button');
    btn.id = 'campaignCreateBtn';
    btn.className = 'btn btn-primary btn-sm';
    btn.textContent = '+ Create Campaign';
    btn.style.cssText = 'background-color: #1d7bec; border: none; padding: 6px 16px; font-size: 14px; border-radius: 10px; box-shadow: 0 1px 2px rgba(0,0,0,0.1);';
    
    btn.onclick = function() {
        console.log('Button clicked');
        showCampaignTypeDialog();
    };
    
    btnContainer.appendChild(btn);
    document.body.appendChild(btnContainer);
    
    console.log('Button added successfully');
}

function showCampaignTypeDialog() {
    const d = new frappe.ui.Dialog({
        title: 'Create New Campaign',
        fields: [
            {
                label: 'Campaign Type',
                fieldname: 'campaign_type',
                fieldtype: 'Select',
                options: 'Landing Page\nForms',
                reqd: 1,
                default: 'Landing Page'
            }
        ],
        primary_action_label: 'Next',
        primary_action(values) {
            d.hide();
            
            if (values.campaign_type === 'Landing Page') {
                showLandingPageDialog();
            } else {
                frappe.msgprint({
                    title: 'Coming Soon',
                    message: 'Forms integration will be available soon!',
                    indicator: 'blue'
                });
            }
        }
    });
    
    d.show();
}

function showLandingPageDialog() {
    const d = new frappe.ui.Dialog({
        title: 'Select Landing Page',
        size: 'large',
        fields: [
            {
                label: 'Select a Published Landing Page',
                fieldname: 'landing_page',
                fieldtype: 'Link',
                options: 'Landing Page',
                reqd: 1,
                get_query: function() {
                    return {
                        filters: {
                            'status': 'Published'
                        }
                    };
                },
                description: 'Only published landing pages are shown'
            }
        ],
        primary_action_label: 'Create Campaign',
        primary_action(values) {
            d.hide();
            
            frappe.route_options = {
                'target_type': 'Landing Page',
                'target': values.landing_page
            };
            
            frappe.set_route('Form', 'Campaigns', 'new-campaigns-1');
        }
    });
    
    d.show();
}

// Re-add button when navigating within the app
$(document).on('page-change', function() {
    if (window.location.hash.includes('my-campaigns')) {
        setTimeout(addCampaignButton, 500);
    }
});
