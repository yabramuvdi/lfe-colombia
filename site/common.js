// Shared by every page: navigation, escaping, the author/paper picker, link helpers.

const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const fold = s => String(s).normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
const pct = (n, d) => (100 * n / d).toFixed(1) + '%';
const hashKey = () => decodeURIComponent(location.hash.slice(1));

(function nav() {
  const pages = [['index.html', 'Papers'], ['authors.html', 'Authors'], ['lineages.html', 'Lineages'],
                 ['citations.html', 'Cited authors'], ['network.html', 'Co-citation network']];
  const here = location.pathname.split('/').pop() || 'index.html';
  const el = document.createElement('nav');
  el.className = 'site';
  el.innerHTML = pages.map(([href, label]) => `<a href="${href}" class="${href === here ? 'here' : ''}">${label}</a>`).join('');
  document.body.prepend(el);
})();

// Core authors: profile name if we have one (keeps accents), else the corpus name.
// "Harrison, G" (how some cited authors are recorded) reads as "G Harrison".
const tidy = n => n.replace(/^([^,]+), ([^,]+)$/, '$2 $1');
const nameOf = id => (typeof PEOPLE !== 'undefined' && PEOPLE.people[id]?.core && PEOPLE.people[id].name)
  || (typeof CORPUS !== 'undefined' && CORPUS.names[id] && tidy(CORPUS.names[id])) || id;
const isCore = id => typeof PEOPLE !== 'undefined' && !!PEOPLE.people[id]?.core;
const authorLink = id => isCore(id) ? `<a class="core-link" href="authors.html#${id}">${esc(nameOf(id))}</a>` : esc(nameOf(id));
const byline = w => w.a ? w.a.map(authorLink).join(', ') : esc(w.ar || '');
const paperLink = (id, w) => `<a href="index.html#${id}">${esc(w.t || id)}</a>`;

// A searchable dropdown. items: [{key, label, sub}]; current(): selected key; choose(key).
function combo(root, { items, current, choose, placeholder = 'Type a name…', max = 200 }) {
  root.classList.add('combo');
  root.innerHTML = `<input role="combobox" aria-expanded="false" aria-autocomplete="list" autocomplete="off" spellcheck="false"
      placeholder="${esc(placeholder)}"><svg class="chev" viewBox="0 0 14 14" aria-hidden="true"><path d="M2.5 5l4.5 4.5L11.5 5"/></svg>
    <ul role="listbox" hidden></ul>`;
  const q = root.querySelector('input'), list = root.querySelector('ul');
  const byKey = Object.fromEntries(items.map(i => [i.key, i]));
  const folded = items.map(i => fold(i.label));
  let hits = [], active = 0;
  const show = () => { q.value = byKey[current()]?.label ?? ''; };
  function open(all) {
    const t = fold(q.value.trim());
    hits = (all || !t ? items : items.filter((_, i) => folded[i].includes(t))).slice(0, max);
    active = Math.max(0, hits.findIndex(i => i.key === current()));
    list.innerHTML = hits.length ? hits.map((it, i) =>
      `<li role="option" data-i="${i}" aria-selected="${i === active}" class="${it.key === current() ? 'current' : ''}">`
      + `${esc(it.label)}${it.sub ? `<small>${esc(it.sub)}</small>` : ''}</li>`).join('')
      : '<li class="empty">No match</li>';
    list.hidden = false; q.setAttribute('aria-expanded', 'true'); move(0);
  }
  function close() { list.hidden = true; q.setAttribute('aria-expanded', 'false'); show(); }
  function move(d) {
    if (!hits.length) return;
    active = (active + d + hits.length) % hits.length;
    const lis = list.querySelectorAll('li');
    lis.forEach((li, i) => li.setAttribute('aria-selected', i === active));
    lis[active]?.scrollIntoView({ block: 'nearest' });
  }
  const pick = it => { close(); q.blur(); choose(it.key); };
  q.addEventListener('focus', () => { q.value = ''; open(true); });
  q.addEventListener('input', () => open(false));
  q.addEventListener('keydown', e => {
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') { e.preventDefault(); list.hidden ? open(true) : move(e.key === 'ArrowDown' ? 1 : -1); }
    else if (e.key === 'Enter' && !list.hidden && hits[active]) { e.preventDefault(); pick(hits[active]); }
    else if (e.key === 'Escape') { close(); q.blur(); }
  });
  list.addEventListener('mousedown', e => { e.preventDefault(); const li = e.target.closest('li[data-i]'); if (li) pick(hits[+li.dataset.i]); });
  q.addEventListener('blur', () => setTimeout(close, 0));
  show();
  return { refresh: show };
}
