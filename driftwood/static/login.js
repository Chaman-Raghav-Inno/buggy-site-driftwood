(function () {
  'use strict';

  const D = window.Driftwood;
  const { $ } = D;

  D.pages.login = function () {
    $('#login-form').addEventListener('submit', async (e) => {
      e.preventDefault();
      const email = $('#l-email').value.trim();
      const password = $('#l-password').value;
      const msg = $('#login-msg');
      if (!D.EMAIL.test(email)) return D.say(msg, 'Enter your email address.', 'error');
      if (!password) return D.say(msg, 'Enter your password.', 'error');
      const r = await D.api('/api/login', { email, password });
      if (!r.ok) return D.say(msg, r.data.error || 'Could not log you in.', 'error');
      const next = D.params.get('next') || '';
      const home = r.data.user.role === 'host' ? '/host' : '/trips';
      location.href = next.startsWith('/') && !next.startsWith('//') ? next : home;
    });
  };
})();
