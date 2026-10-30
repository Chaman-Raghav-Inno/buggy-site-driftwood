(function () {
  'use strict';

  const D = window.Driftwood;
  const { $, $$, esc } = D;
  const NAME = /^[A-Za-z ]+$/;
  const ARRIVALS = ['3:00 PM', '4:00 PM', '5:00 PM', '6:00 PM', '7:00 PM', '8:00 PM', '9:00 PM', '10:00 PM', '11:00 PM'];

  D.pages.book = async function () {
    const p = D.params;
    const trip = {
      listing: Number(p.get('listing')),
      check_in: p.get('check_in') || '',
      check_out: p.get('check_out') || '',
      adults: Number(p.get('adults')) || 2,
      ages: (p.get('ages') || '').split(',').filter((x) => x !== '').map(Number),
      pets: Number(p.get('pets')) || 0,
    };
    const state = { payment: 'property', promo: '', promoAmount: 0 };
    const [me, stay] = await Promise.all([D.api('/api/me'), D.api(`/api/listings/${trip.listing}`)]);
    if (!stay.ok || !trip.check_in || !trip.check_out) {
      $('#step').innerHTML = '<p>We couldn\'t find that stay or those dates. <a href="/search">Search again</a></p>';
      return;
    }
    const s = stay.data;
    const guests = trip.adults + trip.ages.length;
    $('#summary').innerHTML = `<img src="${s.image}" alt="" width="320" height="180">
      <h2>${esc(s.name)}</h2>
      <p class="muted">${esc(D.CITY[s.city])} · ${esc(s.type)}</p>
      <dl class="facts">
        <div><dt>Dates</dt><dd>${D.fmtRange(trip.check_in, trip.check_out)}</dd></div>
        <div><dt>Guests</dt><dd>${D.plural(guests, 'guest')}${trip.pets ? ', ' + D.plural(trip.pets, 'pet') : ''}</dd></div>
      </dl>
      <p><a href="/listing?id=${s.id}">Change trip</a></p>`;

    function markStep(n) {
      $$('.steps li').forEach((li) => li.classList.toggle('current', Number(li.dataset.step) === n));
    }

    function stepDetails() {
      markStep(1);
      $('#step').innerHTML = `<form id="details" class="form" novalidate>
        <h2>Your details</h2>
        <div class="field"><label for="g-name">Full name</label><input id="g-name" autocomplete="name" maxlength="80"></div>
        <div class="field-row">
          <div class="field"><label for="g-email">Email</label><input id="g-email" type="email" autocomplete="email" value="${esc(me.data.user ? me.data.user.email : '')}"></div>
          <div class="field"><label for="g-phone">Phone</label><input id="g-phone" type="tel" autocomplete="tel"></div>
        </div>
        <div class="field"><label for="g-arrival">Arrival time</label>
          <select id="g-arrival"><option value="">I don't know yet</option>${ARRIVALS.map((a) => `<option>${a}</option>`).join('')}</select></div>
        <div class="field"><label for="g-requests">Special requests (optional)</label>
          <textarea id="g-requests" rows="4" maxlength="500" aria-describedby="g-count"></textarea>
          <p id="g-count" class="hint">0 / 500 characters</p></div>
        <p id="g-msg" class="msg error" role="alert"></p>
        <div class="actions"><button type="submit" class="btn">Continue to payment</button></div>
      </form>`;
      $('#g-requests').addEventListener('input', (e) => { $('#g-count').textContent = `${e.target.value.length} / 500 characters`; });
      $('#details').addEventListener('submit', (e) => {
        e.preventDefault();
        const name = $('#g-name').value.trim();
        const email = $('#g-email').value.trim();
        const phone = $('#g-phone').value.trim();
        const msg = $('#g-msg');
        if (!NAME.test(name)) return D.say(msg, 'Enter your full name using letters only.', 'error');
        if (!D.EMAIL.test(email)) return D.say(msg, 'Enter a valid email address.', 'error');
        if (phone.replace(/\D/g, '').length < 6) return D.say(msg, 'Enter a phone number we can reach you on.', 'error');
        Object.assign(state, { name, email, phone, arrival: $('#g-arrival').value, requests: $('#g-requests').value });
        stepPayment();
      });
    }

    function stepPayment() {
      markStep(2);
      $('#step').innerHTML = `<form id="payment" class="form" novalidate>
        <h2>Payment</h2>
        <fieldset><legend>How would you like to pay?</legend>
          <label class="check"><input type="radio" name="pay" value="property"${state.payment === 'property' ? ' checked' : ''}> Pay at the property</label>
          <label class="check"><input type="radio" name="pay" value="bank"${state.payment === 'bank' ? ' checked' : ''}> Bank transfer (details by email)</label>
        </fieldset>
        <div class="field"><label for="promo">Promo code</label>
          <div class="row"><input id="promo" autocomplete="off" value="${esc(state.promo)}"><button type="button" id="apply" class="btn btn-ghost">Apply</button></div>
          <p id="promo-msg" class="msg" role="status"></p></div>
        <div class="actions"><button type="button" id="back" class="btn btn-ghost">Back</button><button type="submit" class="btn">Review booking</button></div>
      </form>`;
      $('#apply').addEventListener('click', async () => {
        const code = $('#promo').value.trim();
        const msg = $('#promo-msg');
        if (!code) return D.say(msg, 'Enter a code.', 'error');
        const res = await D.api('/api/quote?' + quoteQuery(code).toString());
        if (!res.ok) {
          state.promo = '';
          return D.say(msg, res.data.error || 'That promo code isn\'t valid.', 'error');
        }
        state.promo = code;
        state.promoAmount = res.data.promo;
        D.say(msg, `${code.toUpperCase()} applied: −${D.money(res.data.promo)}`, 'success');
      });
      $('#back').addEventListener('click', stepDetails);
      $('#payment').addEventListener('submit', (e) => {
        e.preventDefault();
        state.payment = $('input[name="pay"]:checked').value;
        stepReview();
      });
    }

    function quoteQuery(code) {
      const q = new URLSearchParams({ listing: trip.listing, check_in: trip.check_in, check_out: trip.check_out, adults: trip.adults, pets: trip.pets });
      if (trip.ages.length) q.set('ages', trip.ages.join(','));
      if (code) q.set('promo', code);
      return q;
    }

    async function stepReview() {
      markStep(3);
      $('#step').innerHTML = '<p class="muted">Checking your dates…</p>';
      const res = await D.api('/api/holds', {
        ...trip,
        promo: state.promo,
        name: state.name,
        email: state.email,
        phone: state.phone,
        arrival: state.arrival,
        requests: state.requests,
        payment: state.payment,
      });
      if (!res.ok) {
        $('#step').innerHTML = `<p class="msg error" role="alert">${esc(res.data.error || 'We couldn\'t hold these dates.')}</p>
          <div class="actions"><button type="button" id="back" class="btn btn-ghost">Back</button></div>`;
        $('#back').addEventListener('click', stepPayment);
        return;
      }
      const q = res.data.quote;
      const sym = D.SYMBOLS[D.currency];
      const amount = (usd) => sym + usd.toFixed(2);
      const row = (label, usd, cls) => `<div class="${cls || ''}"><dt>${label}</dt><dd>${usd < 0 ? '−' + amount(-usd) : amount(usd)}</dd></div>`;
      let lines = row(`${D.plural(q.nights, 'night')}`, q.subtotal);
      if (q.discount) lines += row(`Stay discount (${Math.round(q.discount_rate * 100)}%)`, -q.discount, 'discount');
      if (q.extra) lines += row(`Extra guests (${q.extra_guests})`, q.extra);
      if (q.pets) lines += row('Pet fee', q.pets);
      lines += row('Cleaning fee', q.cleaning) + row('Service fee', q.service) + row('Taxes', q.tax);
      if (q.promo) lines += row(`Promo ${esc(q.promo_code)}`, -q.promo, 'discount');
      lines += row('Total', q.total, 'grand');
      $('#step').innerHTML = `<h2>Review and confirm</h2>
        <dl class="totals">${lines}</dl>
        <h3>Cancellation</h3>
        <p>${esc(res.data.policy)}</p>
        ${res.data.free_until ? `<p class="deadline">Free cancellation until ${esc(res.data.free_until)}.</p>` : ''}
        <h3>Guest</h3>
        <p>${esc(state.name)} · ${esc(state.email)} · ${esc(state.phone)}<br>${state.payment === 'bank' ? 'Bank transfer' : 'Pay at the property'}</p>
        <form method="post" action="/book/confirm" data-native class="actions">
          <input type="hidden" name="hold" value="${esc(res.data.hold)}">
          <button type="button" id="back" class="btn btn-ghost">Back</button>
          <button type="submit" class="btn" id="confirm">Confirm booking</button>
        </form>`;
      $('#back').addEventListener('click', stepPayment);
    }

    stepDetails();
  };
})();
