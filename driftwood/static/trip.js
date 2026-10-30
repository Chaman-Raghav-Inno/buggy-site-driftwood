(function () {
  'use strict';

  const D = window.Driftwood;
  const { $, $$, esc } = D;
  const POLICY_NAME = { flexible: 'Flexible', moderate: 'Moderate', strict: 'Strict' };

  D.pages.trip = async function () {
    const ref = D.params.get('ref') || '';
    let t;

    function draw() {
      document.title = `${t.name} · Driftwood Stays`;
      $('#t-image').src = t.image;
      $('#t-status').textContent = t.status === 'cancelled' ? 'Cancelled' : `${D.CITY[t.city]} · Confirmed`;
      $('#t-name').textContent = t.name;
      $('#t-dates').textContent = `${D.fmtRange(t.check_in, t.check_out)} · ${D.plural(t.nights, 'night')} · ${D.plural(t.adults + t.ages.length, 'guest')}`;
      $('#t-ref').textContent = `Reference ${t.ref}`;
      const p = t.price;
      const row = (label, usd, cls) => `<div class="${cls || ''}"><dt>${label}</dt><dd>${usd < 0 ? '−' + D.money(-usd) : D.money(usd)}</dd></div>`;
      let html = row(D.plural(p.nights, 'night'), p.subtotal);
      if (p.discount) html += row(`Stay discount (${Math.round(p.discount_rate * 100)}%)`, -p.discount, 'discount');
      if (p.extra) html += row(`Extra guests (${p.extra_guests})`, p.extra);
      if (p.pets) html += row('Pet fee', p.pets);
      html += row('Cleaning fee', p.cleaning) + row('Service fee', p.service) + row('Taxes', p.tax);
      if (p.promo) html += row(`Promo ${esc(p.promo_code)}`, -p.promo, 'discount');
      html += row('Total paid', p.total, 'grand');
      if (t.refunded != null) html += row('Refunded', t.refunded, 'discount');
      $('#t-price').innerHTML = html;
      $('#t-receipt').href = `/receipt?ref=${t.ref}`;
      $('#t-policy').innerHTML = `<strong>${POLICY_NAME[t.policy]}.</strong> ${esc(t.policy_text)}`;
      const r = t.refund;
      $('#t-deadline').textContent = !r ? ''
        : r.until ? `If you cancel now: ${r.label.toLowerCase()} (${D.money(r.amount)}), until ${r.until}.`
          : 'If you cancel now, you won\'t get a refund.';
      const active = t.status === 'confirmed';
      $('#t-change').hidden = !active;
      $('#t-cancel').hidden = !active;
      $('#t-review').hidden = !active || t.reviewed;
      $('#t-guest').innerHTML = [
        ['Name', t.guest_name], ['Email', t.email], ['Phone', t.phone || '—'], ['Arrival', t.arrival || 'Not sure yet'],
        ['Payment', t.payment || 'Pay at the property'], ['Special requests', t.requests || '—'],
      ].map(([k, v]) => `<div><dt>${k}</dt><dd>${esc(v)}</dd></div>`).join('');
    }

    async function load() {
      const r = await D.api(`/api/trips/${encodeURIComponent(ref)}`);
      if (!r.ok) {
        $('#loading').textContent = r.data.error || 'We couldn\'t find that trip.';
        return false;
      }
      t = r.data;
      draw();
      $('#loading').hidden = true;
      $('#trip').hidden = false;
      return true;
    }

    const cancelDialog = $('#cancel-dialog');
    $$('button', cancelDialog).forEach((b) => b.addEventListener('click', () => cancelDialog.close(b.dataset.value)));
    $('#t-cancel').addEventListener('click', () => {
      const r = t.refund;
      $('#cancel-text').textContent = r && r.amount
        ? `You'll get back ${D.money(r.amount)} (${r.label.toLowerCase()}).`
        : 'You won\'t get a refund for this trip.';
      cancelDialog.returnValue = '';
      cancelDialog.showModal();
    });
    cancelDialog.addEventListener('close', async () => {
      if (cancelDialog.returnValue !== 'cancel') return;
      const r = await D.api(`/api/trips/${encodeURIComponent(ref)}/cancel`, {});
      if (!r.ok) return D.say($('#t-msg'), r.data.error || 'Could not cancel the trip.', 'error');
      t = r.data;
      draw();
      D.say($('#t-msg'), `Trip cancelled. ${D.money(t.refunded)} is on its way back to you.`, 'success');
    });

    const changeDialog = $('#change-dialog');
    $('#t-change').addEventListener('click', () => {
      $('#c-in').value = t.check_in;
      $('#c-out').value = t.check_out;
      D.say($('#c-msg'), '');
      changeDialog.showModal();
    });
    $('#c-close').addEventListener('click', () => changeDialog.close());
    $('#change-form').addEventListener('submit', async (e) => {
      e.preventDefault();
      const r = await D.api(`/api/trips/${encodeURIComponent(ref)}/change`, { check_in: $('#c-in').value, check_out: $('#c-out').value });
      if (!r.ok) return D.say($('#c-msg'), r.data.error || 'Could not change the dates.', 'error');
      changeDialog.close();
      t = r.data;
      draw();
      D.say($('#t-msg'), 'Your dates have changed.', 'success');
    });

    const reviewDialog = $('#review-dialog');
    $('#t-review').addEventListener('click', () => { D.say($('#r-msg'), ''); reviewDialog.showModal(); });
    $('#r-close').addEventListener('click', () => reviewDialog.close());
    $('#review-form').addEventListener('submit', async (e) => {
      e.preventDefault();
      const text = $('#r-text').value.trim();
      if (text.length < 10) return D.say($('#r-msg'), 'Write at least 10 characters.', 'error');
      const r = await D.api(`/api/trips/${encodeURIComponent(ref)}/review`, { stars: Number($('#r-stars').value), text });
      if (!r.ok) return D.say($('#r-msg'), r.data.error || 'Could not post your review.', 'error');
      reviewDialog.close();
      t = r.data;
      draw();
      D.say($('#t-msg'), 'Thanks! Your review is live on the listing.', 'success');
    });

    await load();
  };
})();
