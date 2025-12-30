// Custom CRM Menu Items - Injects menu into Frappe CRM sidebar
(function() {
    if (typeof window.customCRMMenuInjected === 'undefined') {
        window.customCRMMenuInjected = false;
    }
 
    function addCustomMenuItems() {
        if (!window.location.pathname.startsWith('/crm')) return;
 
        const checkSidebar = setInterval(() => {
            const sidebar = document.querySelector('nav.flex.flex-col');
            if (sidebar && !window.customCRMMenuInjected) {
                const menuItems = sidebar.querySelectorAll('button');
                if (menuItems.length > 0) {
                    const lastMenuItem = menuItems[menuItems.length - 1];
                    // Create Custom Reports button
                    const customReportsBtn = document.createElement('button');
                    customReportsBtn.className = lastMenuItem.className;
                    customReportsBtn.innerHTML = `
<div class="flex w-full items-center px-2 py-1">
<span class="grid flex-shrink-0 place-items-center">
<svg class="size-4 text-ink-gray-7" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
<path d="M3 3v18h18"/><path d="M18 17V9"/><path d="M13 17V5"/><path d="M8 17v-3"/>
</svg>
</span>
<span class="ml-2 text-sm">GA4 Analytics Report</span>
</div>`;
                    customReportsBtn.onclick = () => {
                        window.location.href = 'https://campaignmanagement.m.frappe.cloud/analytics';
                    };
                    lastMenuItem.parentNode.appendChild(customReportsBtn);
                    window.customCRMMenuInjected = true;
                    clearInterval(checkSidebar);
                }
            }
        }, 500);
        setTimeout(() => clearInterval(checkSidebar), 30000);
    }
 
    document.readyState === 'loading' 
        ? document.addEventListener('DOMContentLoaded', addCustomMenuItems)
        : addCustomMenuItems();
})();
