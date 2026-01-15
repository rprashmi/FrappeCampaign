frappe.pages['campaign-dashboard'].on_page_load = function(wrapper) {
    var page = frappe.ui.make_app_page({
        parent: wrapper,
        title: 'Campaign Dashboard',
        single_column: true
    });
    
    // Remove default primary action button
    page.clear_primary_action();
    
    // Add custom Create button with dropdown
    page.set_primary_action(__('Create New'), function() {
        // This will be handled by the dropdown
    }, 'add');
    
    // Add dropdown menu items
    page.add_menu_item(__('Landing Page'), function() {
        frappe.new_doc('Landing Page Template');
    }, true);
    
    page.add_menu_item(__('Form'), function() {
        frappe.new_doc('Form Template');
    }, true);
    
    page.add_menu_item(__('Campaign'), function() {
        frappe.new_doc('Campaigns');
    }, true);
    
    // Initialize dashboard
    new CampaignDashboard(page);
}

class CampaignDashboard {
    constructor(page) {
        this.page = page;
        this.make();
    }
    
    make() {
        this.$container = $(this.page.body);
        this.$container.empty();
        this.render_header();
        this.render_cards();
    }
    
    render_header() {
        const header_html = `
            <div class="campaign-dashboard-header">
                <div class="campaign-hero">
                    <h1>🚀 Your Campaign Hub</h1>
                    <p>Create, manage, and track all your marketing campaigns, landing pages, and forms in one place.</p>
                </div>
                <div class="campaign-stats">
                    <div class="stat-card">
                        <div class="stat-number" data-stat="campaigns">0</div>
                        <div class="stat-label">Campaigns</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number" data-stat="landing-pages">0</div>
                        <div class="stat-label">Landing Pages</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number" data-stat="forms">0</div>
                        <div class="stat-label">Forms</div>
                    </div>
                </div>
            </div>
        `;
        
        this.$container.append(header_html);
        this.load_stats();
    }
    
    load_stats() {
        // Load campaigns count
        frappe.call({
            method: 'frappe.client.get_count',
            args: { doctype: 'Campaigns' },
            callback: (r) => {
                this.$container.find('[data-stat="campaigns"]').text(r.message || 0);
            }
        });
        
        // Load landing pages count
        frappe.call({
            method: 'frappe.client.get_count',
            args: { doctype: 'Landing Page Template' },
            callback: (r) => {
                this.$container.find('[data-stat="landing-pages"]').text(r.message || 0);
            }
        });
        
        // Load forms count
        frappe.call({
            method: 'frappe.client.get_count',
            args: { doctype: 'Form Template' },
            callback: (r) => {
                this.$container.find('[data-stat="forms"]').text(r.message || 0);
            }
        });
    }
    
    render_cards() {
        this.$container.append('<div class="campaign-sections"></div>');
        this.$sections = this.$container.find('.campaign-sections');
        
        this.render_section('Campaigns', 'Campaigns', 'mail', '#FF6B6B');
        this.render_section('Landing Pages', 'Landing Page Template', 'layout', '#4ECDC4');
        this.render_section('Forms', 'Form Template', 'file-text', '#45B7D1');
    }
    
    render_section(title, doctype, icon, color) {
        const $section = $(`
            <div class="campaign-section">
                <div class="section-header">
                    <h3>
                        <svg class="icon icon-sm" style="color: ${color}">
                            <use href="#icon-${icon}"></use>
                        </svg>
                        ${title}
                    </h3>
                    <button class="btn btn-sm btn-primary-light create-btn" data-doctype="${doctype}">
                        <svg class="icon icon-xs"><use href="#icon-add"></use></svg>
                        Create New
                    </button>
                </div>
                <div class="campaign-cards" data-section="${doctype}">
                    <div class="loading-state">
                        <div class="spinner"></div>
                        <p>Loading ${title}...</p>
                    </div>
                </div>
            </div>
        `);
        
        this.$sections.append($section);
        
        // Bind create button
        $section.find('.create-btn').on('click', (e) => {
            const dt = $(e.currentTarget).data('doctype');
            frappe.new_doc(dt);
        });
        
        // Load data
        this.load_cards(doctype, $section.find('.campaign-cards'));
    }
    
    load_cards(doctype, $container) {
        frappe.call({
            method: 'frappe.client.get_list',
            args: {
                doctype: doctype,
                fields: ['name', 'title', 'creation', 'modified', 'owner'],
                limit_page_length: 20,
                order_by: 'modified desc'
            },
            callback: (r) => {
                $container.empty();
                
                if (r.message && r.message.length > 0) {
                    r.message.forEach(doc => {
                        $container.append(this.make_card(doc, doctype));
                    });
                } else {
                    $container.append(this.make_empty_state(doctype));
                }
            }
        });
    }
    
    make_card(doc, doctype) {
        const date = frappe.datetime.str_to_user(doc.modified);
        const time_ago = frappe.datetime.comment_when(doc.modified);
        const avatar = frappe.avatar(doc.owner, 'avatar-small');
        
        return $(`
            <div class="campaign-card" data-name="${doc.name}" data-doctype="${doctype}">
                <div class="card-thumbnail">
                    <div class="thumbnail-placeholder">
                        <svg class="icon icon-xxl">
                            <use href="#icon-${this.get_icon(doctype)}"></use>
                        </svg>
                    </div>
                    <div class="card-overlay">
                        <button class="btn btn-sm btn-light view-btn">
                            <svg class="icon icon-xs"><use href="#icon-eye"></use></svg>
                            View
                        </button>
                        <button class="btn btn-sm btn-light edit-btn">
                            <svg class="icon icon-xs"><use href="#icon-edit"></use></svg>
                            Edit
                        </button>
                    </div>
                </div>
                <div class="card-content">
                    <h4 class="card-title">${doc.title || doc.name}</h4>
                    <div class="card-meta">
                        <span class="meta-date" title="${date}">
                            <svg class="icon icon-xs"><use href="#icon-clock"></use></svg>
                            ${time_ago}
                        </span>
                        <span class="meta-owner">${avatar}</span>
                    </div>
                </div>
            </div>
        `).on('click', '.view-btn', (e) => {
            e.stopPropagation();
            frappe.set_route('Form', doctype, doc.name);
        }).on('click', '.edit-btn', (e) => {
            e.stopPropagation();
            frappe.set_route('Form', doctype, doc.name);
        }).on('click', function(e) {
            if (!$(e.target).closest('.btn').length) {
                frappe.set_route('Form', doctype, doc.name);
            }
        });
    }
    
    get_icon(doctype) {
        const icon_map = {
            'Campaigns': 'mail',
            'Landing Page Template': 'layout',
            'Form Template': 'file-text'
        };
        return icon_map[doctype] || 'file';
    }
    
    make_empty_state(doctype) {
        return $(`
            <div class="campaign-empty-state">
                <svg class="icon icon-xxl empty-icon">
                    <use href="#icon-inbox"></use>
                </svg>
                <h4>No ${doctype} Yet</h4>
                <p>Click "Create New" to get started with your first ${doctype.toLowerCase()}</p>
                <button class="btn btn-primary btn-sm create-first-btn" data-doctype="${doctype}">
                    <svg class="icon icon-xs"><use href="#icon-add"></use></svg>
                    Create Your First ${doctype}
                </button>
            </div>
        `).on('click', '.create-first-btn', (e) => {
            const dt = $(e.currentTarget).data('doctype');
            frappe.new_doc(dt);
        });
    }
}
