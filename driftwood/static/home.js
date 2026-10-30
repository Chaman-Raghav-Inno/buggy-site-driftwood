(function () {
  'use strict';

  const D = window.Driftwood;
  const { $ } = D;

  D.pages.home = async function () {
    const guests = D.guestsPicker($('#h-guests'));
    $('#home-search').addEventListener('submit', (e) => {
      e.preventDefault();
      const ci = $('#h-in').value;
      const co = $('#h-out').value;
      if ((ci && !co) || (!ci && co)) return D.say($('#h-msg'), 'Choose both dates, or neither.', 'error');
      if (ci && co && co < ci) return D.say($('#h-msg'), 'Check-out must be after check-in.', 'error');
      const g = guests.value();
      const q = new URLSearchParams();
      if ($('#h-location').value) q.set('location', $('#h-location').value);
      if (ci) { q.set('check_in', ci); q.set('check_out', co); }
      q.set('adults', g.adults);
      if (g.ages.length) q.set('ages', g.ages.join(','));
      location.href = '/search?' + q.toString();
    });

    const r = await D.api('/api/search?sort=rating');
    if (!r.ok) return;
    $('#featured').innerHTML = r.data.results.filter((s) => s.rating != null).slice(0, 4)
      .map((s) => D.card(s, `/listing?id=${s.id}`)).join('');
    D.hearts($('#featured'));
  };
})();
