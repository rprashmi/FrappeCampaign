frappe.ready && console.log("workspace page detected");

document.addEventListener("DOMContentLoaded", function () {
    console.log("Workspace campaign JS loaded");

    // wait for workspace to load
    let interval = setInterval(() => {
        const btn = document.querySelector('.btn-new-campaign');

        if (btn) {
            console.log("Found btn-new-campaign");
            clearInterval(interval);

            btn.addEventListener("click", () => {
                console.log("Button clicked");

                const dialog = new frappe.ui.Dialog({
                    title: 'Create New Campaign',
                    fields: [
                        {
                            label: 'Campaign Type',
                            fieldname: 'campaign_type',
                            fieldtype: 'Select',
                            options: ['Landing Page', 'Form'],
                            reqd: 1
                        }
                    ],
                    primary_action_label: 'Next',
                    primary_action(values) {
                        frappe.new_doc("Campaigns");
                        dialog.hide();
                    }
                });

                dialog.show();
            });
        }
    }, 500);
});
