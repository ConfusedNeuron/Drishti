(function() {
  let glossary = null;
  let popover = null;

  function createPopover() {
    const div = document.createElement('div');
    div.id = 'tip-popover';
    div.style.cssText = 'display:none;position:fixed;z-index:1000;pointer-events:none';
    document.body.appendChild(div);
    return div;
  }

  function showTip(el, key) {
    if (!glossary || !glossary[key]) return;
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

  function hideTip() { if (popover) popover.style.display = 'none'; }

  function attachTips() {
    document.querySelectorAll('[data-tip]').forEach(el => {
      el.addEventListener('mouseenter', () => showTip(el, el.dataset.tip));
      el.addEventListener('mouseleave', hideTip);
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
