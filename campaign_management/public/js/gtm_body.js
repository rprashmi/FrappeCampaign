document.addEventListener('DOMContentLoaded', function() {
    var tag = document.createElement('div');
    tag.innerHTML = `
     <!-- Google Tag Manager (noscript) -->
     <noscript><iframe src="https://www.googletagmanager.com/ns.html?id=GTM-K95CHCLH"
     height="0" width="0" style="display:none;visibility:hidden"></iframe></noscript>
     <!-- End Google Tag Manager (noscript) -->
    `;
    document.body.prepend(tag);
});
