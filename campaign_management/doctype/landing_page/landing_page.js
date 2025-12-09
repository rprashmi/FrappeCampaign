frappe.ui.form.on('Landing Page', {
    refresh: function(frm) {
        add_custom_buttons(frm);
        show_published_url(frm);
        hide_irrelevant_fields(frm);
    },

    template: function(frm) {
        if (frm.doc.template) {
            hide_irrelevant_fields(frm);
            load_template_preview_image(frm);
        }
    }
});

function add_custom_buttons(frm) {
    frm.clear_custom_buttons();

    if (frm.doc.status === 'Draft' && !frm.is_new()) {
        frm.add_custom_button(__('Preview'), () => preview_landing_page(frm), __('Actions')).addClass('btn-primary');
        frm.add_custom_button(__('Publish'), () => publish_landing_page(frm), __('Actions')).addClass('btn-success');
    }

    if (frm.doc.status === 'Published') {
        frm.add_custom_button(__('View Live'), () => window.open(frm.doc.published_url, '_blank'), __('Actions')).addClass('btn-info');
        frm.add_custom_button(__('Copy URL'), () => {
            navigator.clipboard?.writeText(frm.doc.published_url);
            frappe.show_alert({message: __('URL copied!'), indicator: 'green'});
        }, __('Actions'));
        frm.add_custom_button(__('Unpublish'), () => unpublish_landing_page(frm), __('Actions'));
    }
}

function show_published_url(frm) {
    if (frm.doc.published_url) {
        frm.dashboard.clear_comment();
        frm.dashboard.add_comment(`
            <div style="padding: 12px; background: #d4edda; border-left: 4px solid #28a745; border-radius: 4px; margin: 10px 0;">
                <strong>Live URL:</strong><br>
                <a href="${frm.doc.published_url}" target="_blank">${frm.doc.published_url}</a>
            </div>
        `, null, true);
    }
}

function hide_irrelevant_fields(frm) {
    if (!frm.doc.template) return;

    frappe.db.get_doc('Landing Page Template', frm.doc.template).then(template_doc => {
        if (!template_doc.template_html) return;

        // Extract all {{ field }} from template
        const used_fields = [...new Set(
            (template_doc.template_html.match(/\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}/g) || [])
                .map(m => m.match(/\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}/)[1])
        )];

        // Always show these fields
        const always_visible = ['title', 'slug', 'template', 'status', 'published_url', 'meta_title', 'meta_description', 'views'];

        // Combine
        const visible_fields = [...new Set([...used_fields, ...always_visible])];

        // Hide all fields except visible ones
        frm.fields.forEach(field => {
            if (field.df) {
                const fieldname = field.df.fieldname;
                const should_show = visible_fields.includes(fieldname);
                frm.set_df_property(fieldname, 'hidden', should_show ? 0 : 1);
            }
        });

        frm.refresh_fields();
    });
}

function load_template_preview_image(frm) {
    frappe.db.get_value('Landing Page Template', frm.doc.template, 'preview_image', (r) => {
        if (r && r.preview_image) {
            frm.set_value('hero_image', r.preview_image); // optional: prefill hero image
        }
    });
}

function preview_landing_page(frm) {
    frm.save().then(() => {
        window.open(`/api/method/campaign_management.campaign_management.api.preview_landing_page?name=${frm.doc.name}`, '_blank');
    });
}

function publish_landing_page(frm) {
    frappe.confirm(__('Publish this landing page?'), () => {
        frm.set_value('status', 'Published');
        frm.save().then(() => {
            frappe.show_alert({message: __('Published successfully!'), indicator: 'green'});
        });
    });
}

function unpublish_landing_page(frm) {
    frappe.confirm(__('Unpublish this page?'), () => {
        frm.set_value('status', 'Draft');
        frm.save();
    });
}
