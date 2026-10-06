/* Owner-only helper for post-ads.html.
   Two jobs: copy a ready-made caption, and share it.
   No network calls, no tracking, no third-party code. */
(function () {
  'use strict';

  function flash(btn, text) {
    var original = btn.textContent;
    btn.textContent = text;
    btn.classList.add('done');
    setTimeout(function () {
      btn.textContent = original;
      btn.classList.remove('done');
    }, 1800);
  }

  function copyText(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      return navigator.clipboard.writeText(text);
    }
    // Fallback for older mobile browsers / non-secure contexts.
    return new Promise(function (resolve, reject) {
      var ta = document.createElement('textarea');
      ta.value = text;
      ta.setAttribute('readonly', '');
      ta.style.position = 'fixed';
      ta.style.top = '-1000px';
      document.body.appendChild(ta);
      ta.select();
      ta.setSelectionRange(0, ta.value.length);
      try {
        document.execCommand('copy') ? resolve() : reject();
      } catch (e) {
        reject(e);
      }
      document.body.removeChild(ta);
    });
  }

  function captionFor(el) {
    var box = el.closest('.ad__body');
    var cap = box && box.querySelector('.ad__caption');
    if (!cap) return '';
    return (cap.dataset.caption || cap.textContent || '').trim();
  }

  document.querySelectorAll('.b--cp').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var text = captionFor(btn);
      copyText(text).then(
        function () { flash(btn, '✓ Copied'); },
        function () { flash(btn, 'Select & copy'); }
      );
    });
  });

  document.querySelectorAll('[data-share="wa"]').forEach(function (link) {
    link.addEventListener('click', function (ev) {
      var text = captionFor(link);
      if (!text) return;
      if (navigator.share) {
        // Best on phones: lets the owner choose WhatsApp, Facebook, anything installed.
        ev.preventDefault();
        navigator.share({ text: text }).catch(function () { /* user cancelled */ });
        return;
      }
      ev.preventDefault();
      window.open('https://wa.me/?text=' + encodeURIComponent(text), '_blank', 'noopener');
    });
  });
})();
