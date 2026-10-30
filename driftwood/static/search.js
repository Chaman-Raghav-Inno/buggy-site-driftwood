(function () {
  'use strict';

  const D = window.Driftwood;
  const { $, $$ } = D;

  D.pages.search = async function () {
    const p = D.params;
    const initialAges = (p.get('ages') || '').split(',').filter((x) => x !== '').map(Number);
    const guests = D.guestsPicker($('#f-guests'), { adults: Number(p.get('adults')) || 2, ages: initialAges });
    $('#f-location').value = p.get('location') || '';
    $('#f-in').value = p.get('check_in') || '';
    $('#f-out').value = p.get('check_out') || '';
    $('#f-price').value = p.get('max_price') || '';
    $('#f-sort').value = p.get('sort') || '';
    $('#f-pets').checked = p.get('pets') === '1';
    const types = (p.get('types') || '').split(',');
    $$('input[name="type"]').forEach((c) => { c.checked = types.includes(c.value); });

    function query() {
      const q = new URLSearchParams();
      const g = guests.value();
      if ($('#f-location').value) q.set('location', $('#f-location').value);
      if ($('#f-in').value && $('#f-out').value) {
        q.set('check_in', $('#f-in').value);
        q.set('check_out', $('#f-out').value);
      }
      q.set('adults', g.adults);
      if (g.ages.length) q.set('ages', g.ages.join(','));
      if ($('#f-price').value) q.set('max_price', $('#f-price').value);
      const picked = $$('input[name="type"]:checked').map((c) => c.value);
      if (picked.length) q.set('types', picked.join(','));
      if ($('#f-pets').checked) q.set('pets', '1');
      if ($('#f-sort').value) q.set('sort', $('#f-sort').value);
      return q;
    }

    async function load() {
      const ci = $('#f-in').value;
      const co = $('#f-out').value;
      if (ci && co && co < ci) return D.say($('#f-msg'), 'Check-out must be after check-in.', 'error');
      D.say($('#f-msg'), '');
      const q = query();
      history.replaceState(null, '', '/search?' + q.toString());
      const r = await D.api('/api/search?' + q.toString());
      if (!r.ok) return D.say($('#f-msg'), r.data.error || 'Could not search right now.', 'error');
      const list = r.data.results;
      const link = (s) => {
        const l = new URLSearchParams({ id: s.id });
        if (q.get('check_in')) { l.set('check_in', q.get('check_in')); l.set('check_out', q.get('check_out')); }
        l.set('adults', q.get('adults'));
        if (q.get('ages')) l.set('ages', q.get('ages'));
        return '/listing?' + l.toString();
      };
      $('#result-count').textContent = list.length
        ? `${D.plural(list.length, 'stay')}${r.data.nights != null ? ` for ${D.plural(r.data.nights, 'night')}` : ''}`
        : 'No stays match. Try other dates or fewer filters.';
      $('#results').innerHTML = list.map((s) => D.card(s, link(s))).join('');
    }

    $('#filters').addEventListener('change', load);
    D.hearts($('#results'));
    await load();
  };
})();
