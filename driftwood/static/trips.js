(function () {
  'use strict';

  const D = window.Driftwood;
  const { $, $$, esc } = D;

  D.pages.trips = async function () {
    const tabs = $$('[role="tab"]');
    tabs.forEach((tab) => tab.addEventListener('click', () => {
      tabs.forEach((t) => {
        const on = t === tab;
        t.setAttribute('aria-selected', String(on));
        $('#' + t.getAttribute('aria-controls')).hidden = !on;
      });
    }));
    const r = await D.api('/api/trips');
    if (!r.ok) return D.toast(r.data.error || 'Could not load your trips.', 'error');
    const card = (t) => `<a class="card trip-card" href="/trip?ref=${t.ref}">
        <img src="${t.image}" alt="" width="160" height="100">
        <div>
          <p class="eyebrow">${t.status === 'cancelled' ? 'Cancelled' : esc(D.CITY[t.city])}</p>
          <h2>${esc(t.name)}</h2>
          <p class="muted">${D.fmtRange(t.check_in, t.check_out)} · ${D.plural(t.nights, 'night')}</p>
          <p class="muted small">${t.ref}</p>
        </div>
      </a>`;
    $('#upcoming').innerHTML = r.data.upcoming.length ? r.data.upcoming.map(card).join('') : '<p class="muted">No upcoming trips. <a href="/search">Find a stay</a></p>';
    $('#past').innerHTML = r.data.past.length ? r.data.past.map(card).join('') : '<p class="muted">No past trips yet.</p>';
  };
})();
