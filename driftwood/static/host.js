(function () {
  'use strict';

  const D = window.Driftwood;
  const { $, esc } = D;

  D.pages.host = async function () {
    const r = await D.api('/api/host');
    if (!r.ok) return D.toast(r.data.error || 'Could not load your dashboard.', 'error');
    const h = r.data;
    $('#h-payout').textContent = D.money(h.payout);
    $('#h-occupancy').textContent = `${h.occupancy}%`;
    $('#h-count').textContent = h.listings.length;
    $('#h-listings').innerHTML = h.listings.map((s) => `<article class="card stay-card">
        <img src="${s.image}" alt="" width="400" height="260">
        <div class="stay-body">
          <p class="stay-meta"><span>${esc(s.type)} · ${esc(D.CITY[s.city])}</span><span>${s.blocked ? D.plural(s.blocked, 'blocked night') : ''}</span></p>
          <h3>${esc(s.name)}</h3>
          <p class="price">${D.money(s.base)} weekdays · ${D.money(s.weekend)} weekends · min ${D.plural(s.min_nights, 'night')}</p>
          <p><a class="btn btn-small" href="/host/listing?id=${s.id}">Edit listing</a> <a href="/listing?id=${s.id}">View</a></p>
        </div>
      </article>`).join('');
    $('#h-reservations').innerHTML = h.reservations.length
      ? h.reservations.map((x) => `<tr><td>${x.ref}</td><td>${esc(x.listing)}</td><td>${esc(x.guest)}</td>
          <td>${D.fmtRange(x.check_in, x.check_out)}</td><td class="num">${x.nights}</td>
          <td class="num">${D.money(x.guest_paid)}</td><td class="num">${D.money(x.payout)}</td></tr>`).join('')
      : '<tr><td colspan="7" class="muted">No upcoming reservations.</td></tr>';
  };
})();
