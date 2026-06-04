/* -------------------------------------------------------------------------
   Dashboard page logic.
     * Renders the stat strip and the recent-cases table from the
       `__CASES__` payload injected by the server.
     * Wires up the "New Case" modal — multi-file upload + textarea
       for case facts.
     * On submit, POSTs a JSON case payload to /cases/, then uploads
       each chosen document to /cases/<id>/documents. Finally
       redirects to the case details page so the user can start
       chatting straight away.
   ------------------------------------------------------------------------- */
(function(){
  'use strict';
  const { $, $$, escapeHTML, initialsOf, fmtDateShort, api, toast, user } = App;

  // -- Payload injected by the server ----------------------------------- //
  const data = window.__DASH__ || { cases: [], lawyers: [], stats: {} };
  const userLawyer = data.lawyers && data.lawyers[0];

  // ---------- Stat strip ---------- //
  function renderStats(){
    const wrap = $('#stats');
    if(!wrap) return;
    const s = data.stats || {};
    const items = [
      { num: s.total ?? data.cases.length, lbl: 'Total Cases', icon: 'briefcase' },
      { num: s.active ?? 0,                 lbl: 'Active',      icon: 'dot' },
      { num: s.hearing ?? 0,                lbl: 'Hearings',    icon: 'gavel' },
      { num: s.closed ?? 0,                 lbl: 'Closed',      icon: 'check' }
    ];
    wrap.innerHTML = items.map(it => `
      <div class="stat">
        <div class="ic">${statIcon(it.icon)}</div>
        <div>
          <div class="num">${it.num}</div>
          <div class="lbl">${escapeHTML(it.lbl)}</div>
        </div>
      </div>`).join('');
  }

  function statIcon(name){
    const icons = {
      briefcase: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="3" y="7" width="18" height="13" rx="2"/><path d="M9 7V4h6v3"/></svg>',
      dot:       '<svg viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="12" r="5"/></svg>',
      gavel:     '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M14 3l7 7-3 3-7-7 3-3zM9 14l-6 6 1 1 6-6"/></svg>',
      check:     '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M5 12l5 5L20 7"/></svg>'
    };
    return icons[name] || '';
  }

  // ---------- Recent cases table ---------- //
  function renderTable(){
    const tbody = $('#case-rows');
    const empty = $('#empty-state');
    if(!tbody) return;

    if(!data.cases.length){
      tbody.closest('.case-table').style.display = 'none';
      if(empty) empty.style.display = 'block';
      return;
    }
    if(empty) empty.style.display = 'none';

    tbody.innerHTML = data.cases.map(c => {
      const status = c.status || 'Active';
      const hearing = c.hearing_date || c.next_hearing || '—';
      return `
        <div class="case-row" data-id="${c.id}">
          <div class="ctitle">
            ${escapeHTML(c.title || c.name)}
            <span class="cid">${escapeHTML(c.id_display || ('CASE-' + c.id))} · ${escapeHTML(c.case_type || c.type || '')}</span>
          </div>
          <div class="cell">${escapeHTML(c.client_name || c.client || '—')}</div>
          <div class="cell">${escapeHTML(c.court || '—')}</div>
          <div class="cell">${escapeHTML(fmtDateShort(hearing))}</div>
          <div class="cell"><span class="badge ${status.toLowerCase()}">${escapeHTML(status)}</span></div>
          <div class="open">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 5l7 7-7 7"/></svg>
          </div>
        </div>`;
    }).join('');

    $$('.case-row', tbody).forEach(row => {
      row.addEventListener('click', () => {
        const id = row.dataset.id;
        window.location.href = `/case/${id}`;
      });
    });
  }

  // ---------- Init ---------- //
  document.addEventListener('DOMContentLoaded', () => {
    renderStats();
    renderTable();
  });
})();
