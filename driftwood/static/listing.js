(function () {
  'use strict';

  const D = window.Driftwood;
  const { $, esc } = D;
  const POLICY_NAME = { flexible: 'Flexible', moderate: 'Moderate', strict: 'Strict' };

  D.pages.listing = async function () {
    const id = Number(D.params.get('id'));
    const r = await D.api(`/api/listings/${id}`);
    const s = r.data;
    document.title = `${s.name} · Driftwood Stays`;
    $('#s-name').textContent = s.name;
    $('#s-rating').textContent = s.rating == null ? 'New listing' : `★ ${s.rating.toFixed(1)} · ${D.plural(s.reviews, 'review')}`;
    $('#s-where').textContent = `${D.CITY[s.city]}, ${s.country}`;
    $('#s-type').textContent = s.type;
    $('#s-image').src = s.image;
    $('#s-image').alt = s.name;
    $('#s-about').textContent = s.about;
    $('#s-host').textContent = `Hosted by ${s.host}`;
    $('#s-amenities').innerHTML = s.amenities.map((a) => `<li>${esc(a)}</li>`).join('');
    $('#s-rules').innerHTML = [
      'Check-in from 3:00 PM, check-out by 11:00 AM (local time)',
      `Up to ${D.plural(s.max_guests, 'guest')} (infants under 2 don't count)`,
      s.max_pets ? `Pets allowed: up to ${s.max_pets}` : 'No pets',
      `Minimum stay: ${D.plural(s.min_nights, 'night')}`,
    ].map((x) => `<li>${esc(x)}</li>`).join('');
    $('#s-prices').innerHTML = [
      `Sunday to Thursday nights: ${D.money(s.base)}`,
      `Friday and Saturday nights: ${D.money(s.weekend)}`,
      `Cleaning fee: ${D.money(s.cleaning)} per stay`,
      `Includes 2 guests; ${D.money(25)} a night for each extra guest aged 13+`,
      s.max_pets ? `Pets: ${D.money(40)} per stay` : null,
      '10% off stays of 7+ nights, 20% off 28+ nights',
      `Service fee 12%; local tax ${(s.tax_rate * 100).toFixed(2)}%`,
    ].filter(Boolean).map((x) => `<li>${esc(x)}</li>`).join('');
    $('#s-policy').innerHTML = `<strong>${POLICY_NAME[s.policy]}.</strong> ${esc(s.policy_text)}`;
    $('#w-from').textContent = D.money(s.base);
    $('#s-review-title').textContent = s.reviews ? `Reviews (${s.reviews})` : 'Reviews';
    $('#s-reviews').innerHTML = s.review_list.length
      ? s.review_list.map((v) => `<li class="review"><p><strong>${esc(v.name)}</strong> <span class="muted">· ${'★'.repeat(v.stars)}${'☆'.repeat(5 - v.stars)} · ${D.fmtDay(v.date)}</span></p><p>${esc(v.text)}</p></li>`).join('')
      : '<li class="muted">No reviews yet. Be one of the first guests!</li>';
    const save = $('#s-save');
    function drawSave(saved) {
      save.setAttribute('aria-pressed', String(saved));
      save.textContent = saved ? '♥ Saved' : '♡ Save';
    }
    drawSave(s.saved);
    save.addEventListener('click', async () => {
      if (!D.role) {
        location.href = '/login?next=' + encodeURIComponent(location.pathname + location.search);
        return;
      }
      const saved = save.getAttribute('aria-pressed') === 'true';
      const res = await D.api(saved ? '/api/wishlist/remove' : '/api/wishlist/add', { listing: String(s.id) });
      if (res.ok) drawSave(!saved);
    });

    // Calendar: two months from the current one.
    const booked = new Set(s.booked);
    const today = new Date().toISOString().slice(0, 10);
    let view = today.slice(0, 7);
    function month(ym) {
      const [y, m] = ym.split('-').map(Number);
      const first = new Date(Date.UTC(y, m - 1, 1));
      const days = new Date(Date.UTC(y, m, 0)).getUTCDate();
      const lead = (first.getUTCDay() + 6) % 7;
      const name = first.toLocaleDateString('en-US', { month: 'long', year: 'numeric', timeZone: 'UTC' });
      let cells = '<span class="dow">Mo</span><span class="dow">Tu</span><span class="dow">We</span><span class="dow">Th</span><span class="dow">Fr</span><span class="dow">Sa</span><span class="dow">Su</span>';
      cells += '<span></span>'.repeat(lead);
      for (let d = 1; d <= days; d++) {
        const iso = `${ym}-${String(d).padStart(2, '0')}`;
        const cls = booked.has(iso) ? 'taken' : iso < today ? 'past' : 'free';
        cells += `<span class="day ${cls}" data-date="${iso}" title="${iso}${booked.has(iso) ? ': not available' : ''}">${d}</span>`;
      }
      return `<div class="month"><p class="month-name">${name}</p><div class="days">${cells}</div></div>`;
    }
    function nextMonth(ym, n) {
      const [y, m] = ym.split('-').map(Number);
      const d = new Date(Date.UTC(y, m - 1 + n, 1));
      return d.toISOString().slice(0, 7);
    }
    function drawCalendar() {
      $('#calendar').innerHTML = month(view) + month(nextMonth(view, 1));
      $('#cal-prev').disabled = view <= today.slice(0, 7);
    }
    $('#cal-prev').addEventListener('click', () => { view = nextMonth(view, -1); drawCalendar(); });
    $('#cal-next').addEventListener('click', () => { view = nextMonth(view, 1); drawCalendar(); });
    drawCalendar();

    // Booking widget.
    const p = D.params;
    $('#w-in').value = p.get('check_in') || '';
    $('#w-out').value = p.get('check_out') || '';
    $('#w-in').min = today;
    $('#w-out').min = today;
    const guests = D.guestsPicker($('#w-guests'), { adults: Number(p.get('adults')) || 2, ages: [] });
    if (s.max_pets) {
      $('#w-pets-field').hidden = false;
      $('#w-pets').innerHTML = [0, 1, 2, 3].map((n) => `<option value="${n}">${n === 0 ? 'No pets' : D.plural(n, 'pet')}</option>`).join('');
    }

    function trip() {
      const g = guests.value();
      return {
        check_in: $('#w-in').value,
        check_out: $('#w-out').value,
        adults: g.adults,
        ages: g.ages,
        pets: s.max_pets ? Number($('#w-pets').value) : 0,
      };
    }

    function problem(t) {
      if (!t.check_in || !t.check_out) return 'Add your dates to see the total.';
      if (t.check_out < t.check_in) return 'Check-out must be after check-in.';
      if (t.check_in < today) return 'Check-in can\'t be in the past.';
      for (let d = t.check_in; d < t.check_out; d = D.addDays(d, 1)) {
        if (booked.has(d)) return 'Those dates aren\'t available. Pick other dates.';
      }
      const counted = t.adults + t.ages.filter((a) => a >= 2).length;
      if (counted > s.max_guests) return `This stay sleeps up to ${D.plural(s.max_guests, 'guest')}.`;
      return '';
    }

    function line(label, usd, cls) {
      return `<div class="${cls || ''}"><dt>${label}</dt><dd>${usd < 0 ? '−' + D.money(-usd) : D.money(usd)}</dd></div>`;
    }

    async function estimate() {
      const t = trip();
      const issue = problem(t);
      $('#w-estimate').hidden = true;
      D.say($('#w-msg'), issue && t.check_in && t.check_out ? issue : '', 'error');
      if (issue) return null;
      const q = new URLSearchParams({ listing: s.id, check_in: t.check_in, check_out: t.check_out, adults: t.adults, pets: t.pets });
      if (t.ages.length) q.set('ages', t.ages.join(','));
      const res = await D.api('/api/quote?' + q.toString());
      if (!res.ok) {
        D.say($('#w-msg'), res.data.error || 'Could not price these dates.', 'error');
        return null;
      }
      const e = res.data;
      const weekday = e.nights - e.weekend_nights;
      let html = '<dl class="totals">';
      if (weekday) html += line(`${D.plural(weekday, 'weekday night')} × ${D.money(s.base)}`, weekday * s.base);
      if (e.weekend_nights) html += line(`${D.plural(e.weekend_nights, 'weekend night')} × ${D.money(s.weekend)}`, e.weekend_nights * s.weekend);
      if (e.discount) html += line(`Stay discount (${Math.round(e.discount_rate * 100)}%)`, -e.discount, 'discount');
      if (e.extra) html += line(`Extra guests (${e.extra_guests})`, e.extra);
      if (e.pets) html += line('Pet fee', e.pets);
      html += line('Cleaning fee', e.cleaning);
      html += line('Service fee', e.service);
      html += line('Taxes', e.tax);
      html += line('Total', e.total, 'grand');
      html += '</dl>';
      $('#w-estimate').innerHTML = html;
      $('#w-estimate').hidden = false;
      return t;
    }

    $('#w-form').addEventListener('change', estimate);
    $('#w-form').addEventListener('submit', async (e) => {
      e.preventDefault();
      const t = trip();
      const issue = problem(t);
      if (issue) return D.say($('#w-msg'), issue, 'error');
      if (D.role === 'host') return D.say($('#w-msg'), 'Log in as a guest to book.', 'error');
      const q = new URLSearchParams({ listing: s.id, check_in: t.check_in, check_out: t.check_out, adults: t.adults, pets: t.pets });
      if (t.ages.length) q.set('ages', t.ages.join(','));
      location.href = '/book?' + q.toString();
    });
    $('#loading').hidden = true;
    $('#stay').hidden = false;
    await estimate();
  };
})();
