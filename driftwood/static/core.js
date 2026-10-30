(function () {
  'use strict';

  const D = (window.Driftwood = window.Driftwood || {});
  D.pages = D.pages || {};

  const $ = (sel, root) => (root || document).querySelector(sel);
  const $$ = (sel, root) => Array.from((root || document).querySelectorAll(sel));
  const ENTITIES = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
  D.$ = $;
  D.$$ = $$;
  D.esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ENTITIES[c]);
  D.params = new URLSearchParams(location.search);
  D.role = document.body.dataset.role || '';
  D.currency = document.body.dataset.currency || 'USD';
  D.EMAIL = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
  D.RATES = { USD: 1, EUR: 0.9187, JPY: 151.37 };
  D.SYMBOLS = { USD: '$', EUR: '€', JPY: '¥' };
  D.CITY = { Honolulu: 'Honolulu', Tokyo: 'Tokyo', Reykjavik: 'Reykjavík' };

  // Forms are handled by scripts; only forms marked data-native submit to the server.
  document.addEventListener('submit', (e) => {
    if (!e.target.matches('[data-native]')) e.preventDefault();
  }, true);

  D.api = async function (path, body) {
    const opts = body === undefined
      ? { credentials: 'same-origin' }
      : { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) };
    let res;
    try {
      res = await fetch(path, opts);
    } catch (e) {
      return { ok: false, status: 0, data: { error: 'You appear to be offline. Try again.' } };
    }
    let data = {};
    try {
      data = await res.json();
    } catch (e) {
      data = {};
    }
    return { ok: res.ok, status: res.status, data };
  };

  // Money: prices are in USD; other currencies are converted for display.
  D.convert = function (usd, currency) {
    const cur = currency || D.currency;
    const value = usd * D.RATES[cur];
    return cur === 'JPY' ? Math.floor(value) : Math.floor(value * 100) / 100;
  };
  D.money = function (usd, currency) {
    const cur = currency || D.currency;
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: cur }).format(D.convert(usd, cur));
  };

  let toastTimer;
  D.toast = function (text, kind) {
    const el = $('#toast');
    el.textContent = text;
    el.className = 'toast' + (kind ? ' toast-' + kind : '');
    el.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { el.hidden = true; }, 3500);
  };
  D.say = function (el, text, kind) {
    el.textContent = text || '';
    el.classList.toggle('error', kind === 'error');
    el.classList.toggle('success', kind === 'success');
  };

  D.addDays = function (iso, n) {
    const d = new Date(iso + 'T00:00:00Z');
    d.setUTCDate(d.getUTCDate() + n);
    return d.toISOString().slice(0, 10);
  };
  D.nightsBetween = (a, b) => Math.round((Date.parse(b + 'T00:00:00Z') - Date.parse(a + 'T00:00:00Z')) / 86400000);
  D.fmtDay = function (iso) {
    const d = new Date(iso + 'T00:00:00Z');
    return d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric', timeZone: 'UTC' });
  };
  D.fmtRange = (a, b) => `${D.fmtDay(a)} – ${D.fmtDay(b)}`;
  D.plural = (n, word) => `${n} ${word}${n === 1 ? '' : 's'}`;

  // Guests: adults plus each child's age. Children under 2 are infants.
  D.guestsPicker = function (root, initial) {
    const start = initial || { adults: 2, ages: [] };
    const id = root.id;
    root.innerHTML = `<span class="label">Guests</span>
      <div class="guests">
        <label for="${id}-adults">Adults</label>
        <select id="${id}-adults">${[1, 2, 3, 4, 5, 6, 7, 8].map((n) => `<option value="${n}"${n === start.adults ? ' selected' : ''}>${n}</option>`).join('')}</select>
        <label for="${id}-children">Children</label>
        <select id="${id}-children">${[0, 1, 2, 3, 4].map((n) => `<option value="${n}"${n === start.ages.length ? ' selected' : ''}>${n}</option>`).join('')}</select>
      </div>
      <div class="ages" id="${id}-ages"></div>`;
    const ages = $(`#${id}-ages`, root);
    function drawAges(values) {
      const n = Number($(`#${id}-children`, root).value);
      ages.innerHTML = Array.from({ length: n }, (_, i) => {
        const v = values[i] != null ? values[i] : 8;
        return `<label class="age"><span>Child ${i + 1} age</span><select data-age="${i}">${Array.from({ length: 18 }, (_, a) => `<option value="${a}"${a === v ? ' selected' : ''}>${a === 0 ? 'Under 1' : a}</option>`).join('')}</select></label>`;
      }).join('');
    }
    drawAges(start.ages);
    $(`#${id}-children`, root).addEventListener('change', () => {
      drawAges($$('select[data-age]', ages).map((s) => Number(s.value)));
      root.dispatchEvent(new Event('change', { bubbles: true }));
    });
    return {
      value() {
        return {
          adults: Number($(`#${id}-adults`, root).value),
          ages: $$('select[data-age]', ages).map((s) => Number(s.value)),
        };
      },
    };
  };

  D.stars = (r) => (r == null ? 'New' : `★ ${r.toFixed(1)}`);

  D.card = function (s, link) {
    const rating = s.rating == null ? 'New' : `★ ${(Math.floor(s.rating * 10) / 10).toFixed(1)} (${s.reviews})`;
    const price = s.nights != null
      ? `<p class="price"><strong>${D.money(s.avg)}</strong> a night · ${D.money(s.total)} total (${D.plural(s.nights, 'night')})</p>`
      : `<p class="price">From <strong>${D.money(s.base)}</strong> a night</p>`;
    return `<article class="card stay-card">
      <a href="${link}" class="stay-link" aria-label="${D.esc(s.name)}"><img src="${s.image}" alt="" width="400" height="260" loading="lazy"></a>
      <button type="button" class="heart" data-id="${s.id}" aria-pressed="${s.saved}" aria-label="${s.saved ? 'Remove from' : 'Save to'} wishlist">${s.saved ? '♥' : '♡'}</button>
      <div class="stay-body">
        <p class="stay-meta"><span>${D.esc(s.type)} · ${D.esc(D.CITY[s.city] || s.city)}</span><span class="rating">${rating}</span></p>
        <h3><a href="${link}">${D.esc(s.name)}</a></h3>
        ${price}
      </div>
    </article>`;
  };

  D.hearts = function (root, refresh) {
    root.addEventListener('click', async (e) => {
      const btn = e.target.closest('.heart');
      if (!btn) return;
      if (!D.role) {
        location.href = '/login?next=' + encodeURIComponent(location.pathname + location.search);
        return;
      }
      const saved = btn.getAttribute('aria-pressed') === 'true';
      const r = await D.api(saved ? '/api/wishlist/remove' : '/api/wishlist/add', { listing: btn.dataset.id });
      if (!r.ok) return D.toast(r.data.error || 'Could not update your wishlist.', 'error');
      btn.setAttribute('aria-pressed', String(!saved));
      btn.textContent = saved ? '♡' : '♥';
      btn.setAttribute('aria-label', `${saved ? 'Save to' : 'Remove from'} wishlist`);
      D.toast(saved ? 'Removed from your wishlist.' : 'Saved to your wishlist.');
      if (refresh) refresh();
    });
  };

  function setupChrome() {
    const page = document.body.dataset.page;
    $$('.nav a').forEach((a) => { if (a.dataset.nav === page) a.setAttribute('aria-current', 'page'); });
    $('#currency').addEventListener('change', async (e) => {
      const r = await D.api('/api/prefs', { currency: e.target.value });
      if (r.ok) location.reload();
    });
    const logout = $('#logout');
    if (logout) {
      logout.addEventListener('click', async () => {
        await D.api('/api/logout', {});
        location.href = '/';
      });
    }
  }

  document.addEventListener('DOMContentLoaded', async () => {
    setupChrome();
    const run = D.pages[document.body.dataset.page];
    if (!run) return;
    document.body.classList.add('is-loading');
    try {
      await run();
    } finally {
      document.body.classList.remove('is-loading');
    }
  });
})();
