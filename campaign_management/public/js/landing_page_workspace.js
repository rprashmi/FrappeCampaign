frappe.pages['Workspaces'].on_page_load = function(wrapper) {
    // Check if we're on Landing Page workspace
    frappe.router.on('change', () => {
        const current_route = frappe.get_route();
        
        if (current_route[0] === 'Workspaces' && current_route[1] === 'My Landing Page') {
            add_landing_page_actions();
        }
    });
}

function add_landing_page_actions() {
    setTimeout(() => {
        const page = cur_page;
        if (!page) return;
        
        // Clear existing actions
        page.clear_primary_action();
        page.clear_secondary_action();
        
        // Add Create button
        page.set_primary_action(__('Create Landing Page'), function() {
            show_template_selector_dialog();
        }, 'add');
        
        // Add refresh button
        page.add_menu_item(__('Refresh'), function() {
            location.reload();
        }, true);
        
    }, 500);
}

function show_template_selector_dialog() {
    frappe.call({
        method: 'frappe.client.get_list',
        args: {
            doctype: 'Landing Page Template',
            filters: { is_active: 1 },
            fields: ['name', 'template_name', 'preview_image'],
            order_by: 'creation desc'
        },
        callback: function(r) {
            if (r.message && r.message.length > 0) {
                show_template_dialog(r.message);
            } else {
                frappe.msgprint({
                    title: __('No Templates Available'),
                    message: __('Please create landing page templates first.'),
                    primary_action: {
                        label: __('Create Template'),
                        action: function() {
                            frappe.new_doc('Landing Page Template');
                        }
                    }
                });
            }
        }
    });
}

function show_template_dialog(templates) {
    let d = new frappe.ui.Dialog({
        title: __('Choose a Template'),
        size: 'extra-large',
        fields: [{
            fieldtype: 'HTML',
            fieldname: 'template_selector'
        }],
        primary_action_label: __('Skip & Create Blank'),
        primary_action: function() {
            frappe.new_doc('Landing Page');
            d.hide();
        }
    });
    
    // Build template gallery
    let html = '<div class="template-gallery">';
    
    templates.forEach(template => {
        html += `
            <div class="template-card" data-template="${template.name}">
                <div class="template-preview">
                    ${template.preview_image ? 
                        `<img src="${template.preview_image}" alt="${template.template_name}">` :
                        '<div class="no-preview"><svg class="icon icon-xxl"><use href="#icon-image"></use></svg></div>'
                    }
                </div>
                <div class="template-info">
                    <h4>${template.template_name}</h4>
                    <button class="btn btn-primary btn-sm select-template" 
                            data-template="${template.name}"
                            data-template-name="${template.template_name}">
                        <svg class="icon icon-xs"><use href="#icon-check"></use></svg>
                        Use This Template
                    </button>
                </div>
            </div>
        `;
    });
    
    html += '</div>';
    
    // Add CSS
    html += `
        <style>
            .template-gallery {
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
                gap: 20px;
                padding: 20px 0;
                max-height: 60vh;
                overflow-y: auto;
            }
            
            .template-card {
                border: 2px solid #e2e8f0;
                border-radius: 12px;
                overflow: hidden;
                transition: all 0.3s ease;
                cursor: pointer;
                background: white;
            }
            
            .template-card:hover {
                border-color: #667eea;
                transform: translateY(-5px);
                box-shadow: 0 10px 30px rgba(102, 126, 234, 0.2);
            }
            
            .template-preview {
                height: 200px;
                background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
                display: flex;
                align-items: center;
                justify-content: center;
                overflow: hidden;
            }
            
            .template-preview img {
                width: 100%;
                height: 100%;
                object-fit: cover;
            }
            
            .no-preview {
                color: #cbd5e0;
            }
            
            .template-info {
                padding: 16px;
                text-align: center;
            }
            
            .template-info h4 {
                margin: 0 0 12px 0;
                font-size: 16px;
                font-weight: 600;
                color: #2d3748;
            }
            
            .select-template {
                width: 100%;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                border: none;
                color: white;
            }
            
            .select-template:hover {
                opacity: 0.9;
            }
        </style>
    `;
    
    d.fields_dict.template_selector.$wrapper.html(html);
    
    // Bind click events
    d.$wrapper.on('click', '.select-template', function(e) {
        e.stopPropagation();
        const template_name = $(this).data('template');
        const template_display_name = $(this).data('template-name');
        
        d.hide();
        
        // Create new Landing Page with template pre-selected
        frappe.new_doc('Landing Page', {
            template: template_name
        });
        
        frappe.show_alert({
            message: __('Template "{0}" selected', [template_display_name]),
            indicator: 'green'
        }, 3);
    });
    
    d.show();
}
