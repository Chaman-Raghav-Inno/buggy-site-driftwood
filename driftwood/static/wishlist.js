(function () {
  'use strict';

  const D = window.Driftwood;
  const { $ } = D;

  D.pages.wishlist = async function () {
    async function load() {
      const r = await D.api('/api/wishlist');
      if (!r.ok) return D.toast(r.data.error || 'Could not load your wishlist.', 'error');
      const list = r.data.results;
      $('#w-count').textContent = list.length ? `${D.plural(list.length, 'saved stay')}` : 'Nothing saved yet. Tap ♡ on a stay to save it here.';
      $('#results').innerHTML = list.map((s) => D.card({ ...s, saved: true }, `/listing?id=${s.id}`)).join('');
    }
    D.hearts($('#results'), load);
    await load();
  };
})();
