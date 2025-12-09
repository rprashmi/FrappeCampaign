frappe.pages['campaign-management-home'].on_page_load = function(wrapper) {
    let page = frappe.ui.make_app_page({
        parent: wrapper,
        title: 'Campaign Management',
        single_column: true
    });

    // Load HTML template into the page
    $(page.body).html(frappe.render_template("campaign_management_home", {}));

    // ----------- CREATE BUTTON LOGIC -----------
    const createBtn = $("#create-button");
    const dropdown = $("#create-dropdown");

    createBtn.on("click", function () {
        dropdown.toggle();
    });

    // Handle click on options
    $(".dropdown-item").on("click", function () {
        let action = $(this).data("action");

        if (action === "landing_page") {
            frappe.set_route("Form", "Landing Page");
        }
        if (action === "form") {
            frappe.set_route("Form", "Campaign Forms");
        }
        if (action === "campaign") {
            frappe.set_route("Form", "Campaigns");
        }
    });

    // ----------- LOAD THUMBNAILS (Coming next) -----------
    load_thumbnails();
};


// -------------------- FETCH & DISPLAY THUMBNAILS --------------------
function load_thumbnails() {
    load_docs("Landing Page", "#landing-thumbnails");
    load_docs("Campaign Forms", "#form-thumbnails");
    load_docs("Campaigns", "#campaign-thumbnails");
}


// Fetch list of documents for each doctype
function load_docs(doctype, container) {
    frappe.call({
        method: "frappe.client.get_list",
        args: {
            doctype: doctype,
            fields: ["name", "title", "creation", "published"],
            limit_page_length: 50
        },
        callback: function (res) {
            if (!res.message || res.message.length === 0) {
                $(container).html("<p class='no-data'>No items yet</p>");
                return;
            }

            let html = "";
            res.message.forEach(doc => {
                html += `
                    <div class="thumb-card" onclick="open_preview('${doctype}', '${doc.name}')">
                        <h5>${doc.title || doc.name}</h5>
                        <p>Status: ${doc.published ? "Published" : "Draft"}</p>
                        <p>Created: ${frappe.datetime.prettyDate(doc.creation)}</p>
                    </div>
                `;
            });

            $(container).html(html);
        }
    });
}


// Open preview page
function open_preview(doctype, name) {
    frappe.set_route("Form", doctype, name);
}
