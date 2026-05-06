(function () {
  const lang = window.APP_LANG || 'th';
  const translations = window.APP_TEXT_TRANSLATIONS || {};
  const dict = translations[lang] || {};
  if (!dict || lang === 'th') return;

  const skipTags = new Set(['SCRIPT', 'STYLE', 'TEXTAREA', 'CODE', 'PRE', 'CANVAS', 'SVG']);
  const attrs = ['placeholder', 'title', 'aria-label', 'alt', 'data-confirm'];

  function normalize(s) {
    return String(s || '').replace(/\s+/g, ' ').trim();
  }

  function translateString(value) {
    if (!value) return value;
    const original = String(value);
    const compact = normalize(original);
    if (!compact) return value;
    if (dict[compact]) {
      return original.replace(compact, dict[compact]);
    }
    let out = original;
    // Replace longer phrases first so full labels win over small words.
    Object.keys(dict).sort((a, b) => b.length - a.length).forEach((th) => {
      if (th && out.includes(th)) out = out.split(th).join(dict[th]);
    });
    return out;
  }

  function translateNode(root) {
    if (!root || (root.nodeType === 1 && skipTags.has(root.tagName))) return;

    if (root.nodeType === Node.TEXT_NODE) {
      const translated = translateString(root.nodeValue);
      if (translated !== root.nodeValue) root.nodeValue = translated;
      return;
    }

    if (root.nodeType !== Node.ELEMENT_NODE && root.nodeType !== Node.DOCUMENT_NODE && root.nodeType !== Node.DOCUMENT_FRAGMENT_NODE) return;

    if (root.nodeType === Node.ELEMENT_NODE) {
      attrs.forEach((attr) => {
        if (root.hasAttribute && root.hasAttribute(attr)) {
          const oldValue = root.getAttribute(attr);
          const newValue = translateString(oldValue);
          if (newValue !== oldValue) root.setAttribute(attr, newValue);
        }
      });

      // Translate visible labels for buttons/options without changing submitted form values.
      if ((root.tagName === 'INPUT' && ['button', 'submit', 'reset'].includes((root.type || '').toLowerCase()))) {
        const oldValue = root.value;
        const newValue = translateString(oldValue);
        if (newValue !== oldValue) root.value = newValue;
      }
    }

    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
      acceptNode(node) {
        const p = node.parentElement;
        if (!p || skipTags.has(p.tagName)) return NodeFilter.FILTER_REJECT;
        if (!node.nodeValue || !/[\u0E00-\u0E7F]/.test(node.nodeValue)) return NodeFilter.FILTER_REJECT;
        return NodeFilter.FILTER_ACCEPT;
      }
    });

    const textNodes = [];
    while (walker.nextNode()) textNodes.push(walker.currentNode);
    textNodes.forEach(translateNode);

    if (root.querySelectorAll) {
      root.querySelectorAll('input,button,option,img,a,[title],[aria-label],[placeholder],[alt],[data-confirm]').forEach((el) => {
        attrs.forEach((attr) => {
          if (el.hasAttribute && el.hasAttribute(attr)) {
            const oldValue = el.getAttribute(attr);
            const newValue = translateString(oldValue);
            if (newValue !== oldValue) el.setAttribute(attr, newValue);
          }
        });
        if (el.tagName === 'INPUT' && ['button', 'submit', 'reset'].includes((el.type || '').toLowerCase())) {
          const oldValue = el.value;
          const newValue = translateString(oldValue);
          if (newValue !== oldValue) el.value = newValue;
        }
      });
    }
  }

  function run() { translateNode(document.body); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', run); else run();

  const observer = new MutationObserver((mutations) => {
    mutations.forEach((m) => {
      m.addedNodes.forEach(translateNode);
      if (m.type === 'characterData') translateNode(m.target);
    });
  });
  document.addEventListener('DOMContentLoaded', () => {
    if (document.body) observer.observe(document.body, { childList: true, subtree: true, characterData: true });
  });
})();
