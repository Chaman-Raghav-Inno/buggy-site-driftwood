(function () {
  'use strict';

  const D = window.Driftwood;
  const { $, esc } = D;

  D.pages['host-listing'] = async function () {
    const id = Number(D.params.get('id'));
    const r = await D.api(`/api/host/listings/${id}`);
    if (!r.ok) {
      $('#l-name').textContent = r.data.error || 'We couldn\'t open that listing.';
      return;
    }
    const listing = r.data;
    $('#l-name').textContent = `Edit ${listing.name}`;
    $('#l-base').value = listing.base;
    $('#l-weekend').value = listing.weekend;
    $('#l-cleaning').value = listing.cleaning;
    $('#l-min').value = listing.min_nights;
    $('#l-guests').value = listing.max_guests;

    function drawBlocked(days) {
      $('#blocked').innerHTML = days.length
        ? days.map((d) => `<li>${D.fmtDay(d)}</li>`).join('')
        : '<li class="muted">No blocked nights.</li>';
    }
    drawBlocked(listing.blocked);

    $('#price-form').addEventListener('submit', async (e) => {
      e.preventDefault();
      const body = {
        ...listing,
        base: parseFloat($('#l-base').value),
        weekend: parseFloat($('#l-weekend').value),
        cleaning: parseFloat($('#l-cleaning').value),
        min_nights: Number($('#l-min').value),
        max_guests: Number($('#l-guests').value),
      };
      const msg = $('#price-msg');
      if ([body.base, body.weekend, body.cleaning].some((n) => Number.isNaN(n))) return D.say(msg, 'Enter prices as numbers.', 'error');
      const res = await D.api(`/api/host/listings/${id}`, body);
      if (!res.ok) return D.say(msg, res.data.error || 'Could not save.', 'error');
      D.say(msg, `Saved. Weekdays ${D.money(res.data.base)}, weekends ${D.money(res.data.weekend)}.`, 'success');
    });

    $('#block-form').addEventListener('submit', async (e) => {
      e.preventDefault();
      const from = $('#b-from').value;
      const to = $('#b-to').value;
      const msg = $('#block-msg');
      if (!from || !to || to < from) return D.say(msg, 'Choose a start date and an end date on or after it.', 'error');
      const days = [];
      for (let d = from; d < to; d = D.addDays(d, 1)) days.push(d);
      listing.blocked = [...new Set([...listing.blocked, ...days])].sort();
      const res = await D.api(`/api/host/listings/${id}`, listing);
      if (!res.ok) return D.say(msg, res.data.error || 'Could not block those nights.', 'error');
      drawBlocked(res.data.blocked);
      D.say(msg, `Blocked ${esc(D.fmtDay(from))} through ${esc(D.fmtDay(to))}.`, 'success');
    });
  };
})();
