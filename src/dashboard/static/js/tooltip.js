(function() {
  let glossary = null;
  let popover = null;
  let hideTimer = null;

  function scheduleHide() { hideTimer = setTimeout(hideTip, 180); }
  function hideTip() { if (popover) popover.style.display = 'none'; }

  function createPopover() {
    const div = document.createElement('div');
    div.id = 'tip-popover';
    div.style.cssText = 'display:none;position:fixed;z-index:1000';
    // keep the popover open while the cursor is over it (lets the user reach "Read more")
    div.addEventListener('mouseenter', () => clearTimeout(hideTimer));
    div.addEventListener('mouseleave', scheduleHide);
    document.body.appendChild(div);
    return div;
  }

  function showTip(el, key) {
    if (!glossary || !glossary[key]) return;
    clearTimeout(hideTimer);
    const entry = glossary[key];
    popover.innerHTML = `<div class="tip-popover">
      <div class="tip-title">${entry.title}</div>
      <div class="tip-summary">${entry.summary}</div>
      <a class="tip-link" href="${entry.learn}">Read more →</a>
    </div>`;
    popover.style.display = 'block';
    const rect = el.getBoundingClientRect();
    popover.style.left = Math.min(rect.left, window.innerWidth - 260) + 'px';
    popover.style.top  = (rect.bottom + 8) + 'px';
  }

  function attachTips() {
    document.querySelectorAll('[data-tip]').forEach(el => {
      el.addEventListener('mouseenter', () => { clearTimeout(hideTimer); showTip(el, el.dataset.tip); });
      el.addEventListener('mouseleave', scheduleHide);
    });
  }

  document.addEventListener('DOMContentLoaded', () => {
    popover = createPopover();
    fetch('/static/data/glossary.json')
      .then(r => r.json())
      .then(data => { glossary = data; attachTips(); })
      .catch(() => {});
  });
})();
