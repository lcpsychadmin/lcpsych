(function () {
  'use strict';

  var ENDPOINT = '/api/analytics/';
  var SESSION_KEY = 'lcpsych_session_id';
  var CLICK_PATH_LIMIT = 5;
  var HOVER_THRESHOLD_MS = 700;
  var RAGE_WINDOW_MS = 1200;
  var DEAD_CLICK_DELAY_MS = 1800;
  var exitSent = false;
  var navigationStarted = false;
  var clickPath = [];
  var rageMap = new Map();

  function now() {
    return Date.now();
  }

  function uuid() {
    if (typeof crypto !== 'undefined' && crypto.randomUUID) return crypto.randomUUID();
    return 's-' + Math.random().toString(16).slice(2) + now().toString(16);
  }

  function sessionId() {
    try {
      var existing = sessionStorage.getItem(SESSION_KEY);
      if (existing) return existing;
      var id = uuid();
      sessionStorage.setItem(SESSION_KEY, id);
      return id;
    } catch (_) {
      return uuid();
    }
  }

  function safeLabel(el) {
    if (!el) return '';
    var attr = el.getAttribute('data-analytics-label') || el.getAttribute('aria-label') || el.title || '';
    var text = attr || (el.textContent || '');
    return text.replace(/\s+/g, ' ').trim().slice(0, 80);
  }

  function elementKey(el) {
    if (!el) return '';
    var tag = (el.tagName || '').toLowerCase();
    var id = el.id ? '#' + el.id : '';
    var cls = (el.className && typeof el.className === 'string') ? el.className.trim().split(/\s+/).slice(0, 2).join('.') : '';
    return [tag, id, cls ? '.' + cls : ''].join('');
  }

  function send(payload) {
    try {
      payload.session_id = sessionId();
      payload.path = (payload.path || location.pathname || '').split('?')[0].slice(0, 500);
      payload.referrer = (payload.referrer || document.referrer || '').slice(0, 500);
      payload.metadata = payload.metadata || {};
      var body = JSON.stringify(payload);
      if (navigator.sendBeacon) {
        var blob = new Blob([body], { type: 'application/json' });
        navigator.sendBeacon(ENDPOINT, blob);
        return;
      }
      fetch(ENDPOINT, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: body,
        keepalive: true,
      }).catch(function () {});
    } catch (_) {}
  }

  function recordClickPath(label) {
    if (!label) return;
    clickPath.push(label);
    if (clickPath.length > CLICK_PATH_LIMIT) clickPath.shift();
  }

  function currentScrollPercent() {
    var doc = document.documentElement;
    var body = document.body;
    var scrollTop = (window.pageYOffset || doc.scrollTop || body.scrollTop || 0);
    var height = (doc.scrollHeight || body.scrollHeight || 0) - (window.innerHeight || doc.clientHeight || body.clientHeight || 0);
    if (height <= 0) return 0;
    return Math.max(0, Math.min(100, Math.round((scrollTop / height) * 100)));
  }

  function sendExitEvent() {
    if (exitSent) return;
    exitSent = true;
    var scroll = currentScrollPercent();
    var pathSeq = clickPath.slice(-CLICK_PATH_LIMIT).join(' > ');
    send({
      event_type: 'session_exit',
      label: 'exit',
      scroll_percent: scroll,
      metadata: {
        exit_scroll: scroll,
        click_path: pathSeq,
      },
    });
  }

  function handleRageClick(el, label) {
    var key = elementKey(el) || label;
    var ts = now();
    var history = rageMap.get(key) || [];
    var recent = history.filter(function (t) { return ts - t < RAGE_WINDOW_MS; });
    recent.push(ts);
    rageMap.set(key, recent);
    if (recent.length >= 3) {
      send({
        event_type: 'rage_click',
        label: label,
        metadata: { target: key, clicks: recent.length },
      });
    }
  }

  function handleDeadClick(el, label) {
    var href = (el.getAttribute && el.getAttribute('href')) || '';
    var startPath = location.pathname;
    setTimeout(function () {
      if (navigationStarted) return;
      if (document.visibilityState === 'hidden') return;
      if (location.pathname !== startPath) return;
      send({
        event_type: 'dead_click',
        label: label,
        metadata: { target: elementKey(el) || label, href: href, path: startPath },
      });
    }, DEAD_CLICK_DELAY_MS);
  }

  function bindClicks() {
    document.addEventListener('click', function (evt) {
      var target = evt.target && evt.target.closest('a, button, [role="button"], [data-analytics-label]');
      if (!target) return;
      var label = safeLabel(target) || elementKey(target);
      recordClickPath(label);
      send({
        event_type: 'click',
        label: label,
        metadata: {
          kind: 'click',
          target: elementKey(target),
          href: (target.getAttribute && target.getAttribute('href')) || '',
        },
      });
      handleRageClick(target, label);
      handleDeadClick(target, label);
    });
  }

  function bindHoverIntent() {
    var selectors = [
      '[data-hover-intent]',
      '.therapist-card',
      '.service-card',
      '.faq-item',
      '.faq-question',
      '.cta',
      '.btn',
      'a.button',
    ];

    document.addEventListener('mouseenter', function (evt) {
      var target = evt.target && evt.target.closest(selectors.join(','));
      if (!target) return;
      var supportsPerf = typeof performance !== 'undefined' && typeof performance.now === 'function';
      target.__hoverStart = supportsPerf ? performance.now() : now();
      target.__hoverLabel = target.getAttribute('data-hover-intent') || safeLabel(target) || elementKey(target);
    }, true);

    document.addEventListener('mouseleave', function (evt) {
      var target = evt.target;
      if (!target || !target.__hoverStart) return;
      var start = target.__hoverStart;
      var supportsPerf = typeof performance !== 'undefined' && typeof performance.now === 'function';
      var elapsed = (supportsPerf ? performance.now() : now()) - start;
      target.__hoverStart = null;
      if (elapsed < HOVER_THRESHOLD_MS) return;
      var label = target.__hoverLabel || safeLabel(target) || elementKey(target);
      send({
        event_type: 'hover_intent',
        label: label,
        duration_ms: Math.round(elapsed),
        metadata: { target: elementKey(target) },
      });
    }, true);
  }

  function bindExit() {
    window.addEventListener('pagehide', sendExitEvent, { passive: true });
    document.addEventListener('visibilitychange', function () {
      if (document.visibilityState === 'hidden') sendExitEvent();
    });
    window.addEventListener('beforeunload', function () { navigationStarted = true; });
  }

  if (typeof window === 'undefined' || !window.addEventListener) return;
  bindClicks();
  bindHoverIntent();
  bindExit();
})();
