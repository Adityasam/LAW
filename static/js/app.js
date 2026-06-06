/* -------------------------------------------------------------------------
   LegalMind — shared front-end helpers.
   Loaded on every page; defines a small global API used by the page
   modules (dashboard.js, case.js).
   ------------------------------------------------------------------------- */
(function(){
  'use strict';

  const App = window.App = window.App || {};

  // ---- DOM helpers ----------------------------------------------------- //
  App.$  = (s, r=document) => r.querySelector(s);
  App.$$ = (s, r=document) => Array.from(r.querySelectorAll(s));

  // ---- String / data helpers ------------------------------------------ //
  App.escapeHTML = function(s){
    return String(s ?? '').replace(/[&<>"']/g, c => ({
      '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
    }[c]));
  };

  App.initialsOf = function(name){
    return String(name||'').split(/\s+/).filter(Boolean)
      .slice(0,2).map(w=>w[0].toUpperCase()).join('');
  };

  App.fmtDate = function(iso){
    if(!iso || iso === '—') return '—';
    const d = new Date(iso);
    if(isNaN(d)) return iso;
    return d.toLocaleDateString('en-IN', { day:'2-digit', month:'long', year:'numeric' });
  };

  App.fmtDateShort = function(iso){
    if(!iso || iso === '—') return '—';
    const d = new Date(iso);
    if(isNaN(d)) return iso;
    return d.toLocaleDateString('en-IN', { day:'2-digit', month:'short', year:'numeric' });
  };

  // ---- Case status helpers -------------------------------------------- //
  App.normalizeStatus = function(s){
    const v = (s || '').toString().trim();
    if(['Active','Hearing','Closed'].includes(v)) return v;
    return 'Active';
  };

  // ---- Toast notifications -------------------------------------------- //
  App.toast = function(message, kind='info', timeout=3500){
    let host = document.getElementById('toast-host');
    if(!host){
      host = document.createElement('div');
      host.id = 'toast-host';
      host.style.cssText = 'position:fixed;bottom:24px;right:24px;display:flex;flex-direction:column;gap:8px;z-index:200;pointer-events:none;';
      document.body.appendChild(host);
    }
    const el = document.createElement('div');
    const colors = {
      info:    { bg:'#1B1B28', fg:'#E8E6DC', br:'#262636' },
      success: { bg:'rgba(42,107,78,0.18)', fg:'#3E9C6E', br:'#2A6B4E' },
      error:   { bg:'rgba(122,41,41,0.18)', fg:'#D07070', br:'#7A2929' }
    };
    const c = colors[kind] || colors.info;
    el.style.cssText = `
      pointer-events:auto;
      padding:11px 16px;
      background:${c.bg};
      color:${c.fg};
      border:1px solid ${c.br};
      border-radius:6px;
      font-size:13px;
      box-shadow:0 4px 20px rgba(0,0,0,0.4);
      animation: slideUpFade .3s ease;
      max-width:340px;
    `;
    el.textContent = message;
    host.appendChild(el);
    setTimeout(() => {
      el.style.transition = 'opacity .3s, transform .3s';
      el.style.opacity = '0';
      el.style.transform = 'translateY(8px)';
      setTimeout(() => el.remove(), 300);
    }, timeout);
  };

  // ---- Fetch helper ---------------------------------------------------- //
  App.api = {
    async get(url){
      const r = await fetch(url, { headers:{ 'Accept':'application/json' } });
      return r.json();
    },
    async post(url, body){
      const r = await fetch(url, {
        method:'POST',
        headers:{ 'Content-Type':'application/json', 'Accept':'application/json' },
        body: JSON.stringify(body || {})
      });
      return r.json();
    },
    async postForm(url, formData){
      const r = await fetch(url, { method:'POST', body: formData });
      return r.json();
    },
    async put(url, body){
      const r = await fetch(url, {
        method:'PUT',
        headers:{ 'Content-Type':'application/json', 'Accept':'application/json' },
        body: JSON.stringify(body || {})
      });
      return r.json();
    },
    async del(url){
      const r = await fetch(url, { method:'DELETE', headers:{ 'Accept':'application/json' } });
      return r.json();
    }
  };

  // ---- User object populated by the server (see base.html) ------------- //
  // Fallback so other scripts can always read App.user.* safely.
  App.user = window.__USER__ || { name:'Advocate', avatar_initials:'AC' };
})();
