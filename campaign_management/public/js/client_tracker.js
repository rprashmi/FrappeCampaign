/**
 * Universal Client Tracker v4.0 - DataLayer Only
 * Purpose: Collect events → Push to GTM Web Container → Let GTM handle the rest
 * Architecture: Website → GTM Web → GTM Server → Frappe + GA4
 */

(function () {
  'use strict';

  // Prevent double loading
  if (window.__CLIENT_TRACKER__) return;
  window.__CLIENT_TRACKER__ = true;

  
  // CONFIGURATION
  
  const script = document.currentScript;
  const CONFIG = {
    org: script?.dataset.org || 'unknown',
    env: script?.dataset.env || 'prod',
    debug: script?.dataset.debug === 'true'
  };

  function log(...args) {
    if (CONFIG.debug) {
      console.log('[Client Tracker]', ...args);
    }
  }

  // Initialize dataLayer for GTM
  window.dataLayer = window.dataLayer || [];

  log('Initializing Client Tracker', CONFIG);

  
  // CLIENT ID MANAGEMENT
  function getGAClientId() {
    // Try GA4 cookie first (_ga cookie format: GA1.2.123456789.987654321)
    const match = document.cookie.match(/_ga=(.+?);/);
    if (match && match[1]) {
      const parts = match[1].split('.');
      if (parts.length >= 4) {
        return parts[2] + '.' + parts[3];
      }
    }

    // Fallback to localStorage
    let cid = localStorage.getItem('ga_client_id');
    if (!cid) {
      cid = 'cid_' + Math.random().toString(36).slice(2) + Date.now();
      localStorage.setItem('ga_client_id', cid);
    }
    return cid;
  }

  const GA_CLIENT_ID = getGAClientId();
  log('GA Client ID:', GA_CLIENT_ID);

  // TRACKING PARAMS MANAGEMENT (UTMs & Ad Clicks)
  
  function readParams() {
    const p = new URLSearchParams(location.search);
    return {
      utm_source: p.get('utm_source') || '',
      utm_medium: p.get('utm_medium') || '',
      utm_campaign: p.get('utm_campaign') || '',
      utm_term: p.get('utm_term') || '',
      utm_content: p.get('utm_content') || '',
      utm_campaign_id: p.get('utm_id') || '',
      fbclid: p.get('fbclid') || '',
      gclid: p.get('gclid') || '',
      msclkid: p.get('msclkid') || '',
      li_fat_id: p.get('li_fat_id') || ''
    };
  }

  let tracking = readParams();
  const hasAny = Object.values(tracking).some(Boolean);

  // Store tracking params in session for persistence across pages
  if (hasAny) {
    sessionStorage.setItem('tracking_params', JSON.stringify(tracking));
    log('Tracking params stored:', tracking);
  } else {
    const stored = sessionStorage.getItem('tracking_params');
    if (stored) {
      tracking = JSON.parse(stored);
      log('Tracking params retrieved from session:', tracking);
    }
  }

  // Detect ad platform from click IDs
  function detectAds(data) {
    if (data.fbclid) {
      return {
        ad_platform: 'Facebook/Instagram',
        ad_click_id_type: 'fbclid',
        ad_click_id_value: data.fbclid
      };
    }
    if (data.gclid) {
      return {
        ad_platform: 'Google Ads',
        ad_click_id_type: 'gclid',
        ad_click_id_value: data.gclid
      };
    }
    if (data.msclkid) {
      return {
        ad_platform: 'Microsoft Ads',
        ad_click_id_type: 'msclkid',
        ad_click_id_value: data.msclkid
      };
    }
    if (data.li_fat_id) {
      return {
        ad_platform: 'LinkedIn Ads',
        ad_click_id_type: 'li_fat_id',
        ad_click_id_value: data.li_fat_id
      };
    }
    return { ad_platform: '', ad_click_id_type: '', ad_click_id_value: '' };
  }

  const adInfo = detectAds(tracking);
  log('Ad Info:', adInfo);

  
  // PUSH TO DATALAYER (GTM will handle the rest)
  function pushToDataLayer(eventName, eventData = {}) {
    const payload = {
      event: eventName,
      activity_type: eventName,
      organization: CONFIG.org,
      environment: CONFIG.env,
      ga_client_id: GA_CLIENT_ID,
      client_id: GA_CLIENT_ID,
      page_url: location.href,
      page_title: document.title,
      page_referrer: document.referrer || 'direct',
      timestamp: new Date().toISOString(),
      ...tracking,
      ...adInfo,
      ...eventData
    };

    window.dataLayer.push(payload);
    log('→ DataLayer Push:', eventName, payload);
  }

  
  // SESSION START
  
  if (!sessionStorage.getItem('session_started')) {
    sessionStorage.setItem('session_started', '1');
    pushToDataLayer('session_start');
  }


  // PAGE VIEW TRACKING
  pushToDataLayer('page_view');

  // SCROLL DEPTH TRACKING
  const scrollMarks = [25, 50, 75, 90];
  const seenScroll = new Set();
  let scrollTimeout;

  window.addEventListener('scroll', () => {
    clearTimeout(scrollTimeout);
    scrollTimeout = setTimeout(() => {
      const percent = Math.round(
        (window.scrollY / (document.body.scrollHeight - window.innerHeight)) * 100
      );

      scrollMarks.forEach(mark => {
        if (percent >= mark && !seenScroll.has(mark)) {
          seenScroll.add(mark);
          pushToDataLayer('scroll_depth', { 
            percent_scrolled: mark 
          });
          log('Scroll:', mark + '%');
        }
      });
    }, 100);
  });

  // CLICK TRACKING
  document.addEventListener('click', e => {
    const el = e.target.closest('[data-nav-item], [data-cta-name], [data-footer-link], [data-tab], a, button');
    if (!el) return;

    let eventName = 'click';
    let eventData = {
      element_type: el.tagName.toLowerCase(),
      element_text: (el.innerText || el.textContent || '').trim().slice(0, 100),
      element_href: el.getAttribute('href') || '',
      element_id: el.id || '',
      element_class: el.className || ''
    };

    // Navigation click
    if (el.hasAttribute('data-nav-item')) {
      eventName = 'nav_click';
      eventData.nav_item = el.getAttribute('data-nav-item');
      log('Nav Click:', eventData.nav_item);
    }
    // CTA click
    else if (el.hasAttribute('data-cta-name')) {
      eventName = 'cta_click';
      eventData.cta_name = el.getAttribute('data-cta-name');
      eventData.cta_location = el.getAttribute('data-cta-location') || '';
      log('CTA Click:', eventData.cta_name);
    }
    // Footer click
    else if (el.hasAttribute('data-footer-link')) {
      eventName = 'footer_click';
      eventData.link_name = el.getAttribute('data-footer-link');
      log('Footer Click:', eventData.link_name);
    }
    // Tab click
    else if (el.hasAttribute('data-tab')) {
      eventName = 'tab_click';
      eventData.tab_name = el.getAttribute('data-tab');
      log('Tab Click:', eventData.tab_name);
    }

    pushToDataLayer(eventName, eventData);
  });

  // FORM TRACKING

  let formStarted = false;

  // Track first interaction with any form field
  document.addEventListener('focusin', e => {
    const input = e.target.closest('input, select, textarea');
    if (!input) return;

    const form = input.closest('form');
    if (!form || formStarted) return;

    formStarted = true;
    const formName = form.getAttribute('name') || form.getAttribute('id') || 'unknown_form';
    
    pushToDataLayer('form_start', { 
      form_name: formName,
      form_id: form.id || '',
      form_action: form.action || ''
    });
    log('Form Start:', formName);
  }, true);

  // Track form submission
  document.addEventListener('submit', e => {
    const form = e.target;
    if (!form || form.tagName !== 'FORM') return;

    const formData = new FormData(form);
    const data = {
      form_name: form.getAttribute('name') || form.getAttribute('id') || 'unknown_form',
      form_id: form.id || '',
      form_action: form.action || ''
    };

    // Extract form fields (exclude sensitive data like passwords)
    for (let [key, value] of formData.entries()) {
      const lowerKey = key.toLowerCase();
      if (!lowerKey.includes('password') && 
          !lowerKey.includes('pass') && 
          !lowerKey.includes('pwd') &&
          !lowerKey.includes('credit') &&
          !lowerKey.includes('card')) {
        data[key] = value;
      }
    }

    pushToDataLayer('form_submit', data);
    log('Form Submit:', data.form_name);
  });

  // IFRAME FORM SUPPORT (Frappe Web Forms)
  
  window.addEventListener('message', e => {
    if (!e.data || !e.data.event) return;

    if (e.data.event === 'form_submit') {
      pushToDataLayer('form_submit', {
        form_name: e.data.form_name || 'frappe_form',
        form_type: 'iframe',
        source: 'frappe_webform',
        ...e.data
      });
      log('Iframe Form Submit:', e.data.form_name);
    }
  });

  // EXIT INTENT TRACKING

  let exitTracked = false;

  document.addEventListener('mouseleave', e => {
    if (e.clientY <= 0 && !exitTracked) {
      exitTracked = true;
      pushToDataLayer('exit_intent', {
        time_on_page: Math.round((Date.now() - performance.timing.navigationStart) / 1000)
      });
      log('Exit Intent Detected');
    }
  });

  // VISIBILITY CHANGE (Tab switching)

  document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
      pushToDataLayer('page_hide');
      log('Page Hidden');
    } else {
      pushToDataLayer('page_show');
      log('Page Visible');
    }
  });

  // PUBLIC API

  window.ClientTracker = {
    push: pushToDataLayer,
    getClientId: () => GA_CLIENT_ID,
    getTracking: () => tracking,
    getAdInfo: () => adInfo,
    config: CONFIG
  };

  log('✓ Client Tracker Initialized');

})();