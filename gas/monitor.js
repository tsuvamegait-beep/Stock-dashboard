const markets = {
  hh: {name: '헨리허브', unit: '$/MMBtu', link: 'https://www.ice.com/products/6590258/Henry-LD1-Fixed-Price-Future/data'},
  ttf: {name: 'TTF', unit: '€/MWh', link: 'https://www.ice.com/products/27996665/Dutch-TTF-Gas-Futures/data'},
  jkm: {name: 'JKM', unit: '$/MMBtu', link: 'https://www.ice.com/products/6753280/JKM-LNG-PLATTS-Future/data'}
};
const keys = Object.keys(markets);
const month = document.getElementById('month');
const refresh = document.getElementById('refresh');
const status = document.getElementById('status');
const number = new Intl.NumberFormat('ko-KR', {minimumFractionDigits: 2, maximumFractionDigits: 3});
const time = new Intl.DateTimeFormat('ko-KR', {timeZone: 'Asia/Seoul', dateStyle: 'short', timeStyle: 'short'});
const cacheKey = 'gas-monitor-quotes-v1';
const fourDays = 4 * 86400000;
let state = {feeds: {}};

function syncConfig() {
  try {
    const cfg = JSON.parse(localStorage.getItem('portfolio-sync'));
    const url = new URL(cfg.url);
    if (url.origin === 'https://script.google.com' && cfg.key) return {url, key: cfg.key};
  } catch (_) {}
  return null;
}

function add(parent, tag, text, className) {
  const element = document.createElement(tag);
  if (text != null) element.textContent = text;
  if (className) element.className = className;
  parent.append(element);
  return element;
}

function recent(quote) {
  const age = Date.now() - Date.parse(quote?.time);
  return age >= 0 && age <= fourDays;
}

function comparable(a, b) {
  return recent(a) && recent(b) && a.time.slice(0, 10) === b.time.slice(0, 10);
}

function convert(quote) {
  if (!quote) return null;
  const date = quote.time.slice(0, 10);
  const fx = state.feeds.fx || {};
  const day = Object.keys(fx).sort().reverse().find(d => d <= date);
  if (!day || Date.parse(date) - Date.parse(day) > fourDays) return null;
  return {price: quote.price * fx[day] / 3.412141633, day, rate: fx[day]};
}

function render() {
  const oldMonth = month.value;
  const byMarket = Object.fromEntries(keys.map(key => [
    key, new Map((state.feeds[key] || []).map(q => [q.month, q]))
  ]));
  const months = [...new Set(keys.flatMap(key => [...byMarket[key].keys()]))].sort();
  const q = (key, delivery) => byMarket[key].get(delivery);
  month.replaceChildren();
  for (const delivery of months) {
    const option = add(month, 'option', delivery);
    option.value = delivery;
  }
  if (!months.length) add(month, 'option', '—');
  month.disabled = !months.length;
  const common = months.find(m => {
    const hh = q('hh', m), ttf = q('ttf', m), jkm = q('jkm', m);
    return comparable(hh, ttf) && comparable(hh, jkm) && convert(ttf);
  });
  month.value = months.includes(oldMonth) ? oldMonth : (common || months[0] || '—');

  const quotes = document.getElementById('quotes');
  quotes.replaceChildren();
  for (const key of keys) {
    const market = markets[key], row = q(key, month.value);
    const card = add(quotes, 'article', null, 'card');
    add(card, 'h3', market.name);
    add(card, 'p', row ? number.format(row.price) : '—', 'price');
    add(card, 'p', row && row.change != null
      ? market.unit + ' · ICE 등락 ' + (row.change > 0 ? '+' : '') + number.format(row.change) + '%'
      : market.unit, 'muted');
    add(card, 'p', row ? time.format(new Date(row.time)) + ' KST' + (recent(row) ? '' : ' · 오래된 체결') : '해당 월물 체결가 없음', 'muted');
    const converted = key === 'ttf' ? convert(row) : null;
    if (converted) add(card, 'p', number.format(converted.price) + ' $/MMBtu · ECB ' + converted.day + ' (' + converted.rate + ' USD/EUR)', 'muted');
    add(card, 'a', 'ICE 원본').href = market.link;
  }

  const spreads = document.getElementById('spreads');
  spreads.replaceChildren();
  for (const [left, right] of [['ttf','hh'], ['jkm','hh'], ['jkm','ttf']]) {
    const a = q(left, month.value), b = q(right, month.value);
    const price = (key, row) => key === 'ttf' ? convert(row)?.price : row?.price;
    const x = price(left, a), y = price(right, b);
    const valid = comparable(a, b) && Number.isFinite(x) && Number.isFinite(y);
    const tr = add(spreads, 'tr');
    add(tr, 'th', markets[left].name + ' − ' + markets[right].name).scope = 'row';
    add(tr, 'td', valid ? number.format(x - y) : '—');
    add(tr, 'td', valid ? a.time.slice(0, 10) : '같은 날짜의 시세·환율 부족');
  }

  const curve = document.getElementById('curve');
  curve.replaceChildren();
  for (const delivery of months.slice(0, 12)) {
    const tr = add(curve, 'tr', null, delivery === month.value ? 'selected' : '');
    add(tr, 'th', delivery).scope = 'row';
    for (const key of keys) {
      const row = q(key, delivery);
      add(tr, 'td', recent(row) ? number.format(row.price) : '—');
    }
  }
}

async function loadQuotes() {
  if (refresh.disabled) return;
  refresh.disabled = true;
  const cfg = syncConfig();
  try {
    let url = 'quotes.local.json';
    if (cfg) {
      cfg.url.searchParams.set('key', cfg.key);
      cfg.url.searchParams.set('gas', 'quotes');
      url = cfg.url;
    }
    const response = await fetch(url, {cache: 'no-store', signal: AbortSignal.timeout(25000)});
    if (!response.ok) throw new Error();
    const incoming = await response.json();
    if (!incoming.ok || !incoming.checkedAt || !incoming.feeds) throw new Error();
    state = {...incoming, feeds: {...state.feeds, ...incoming.feeds}};
    try { localStorage.setItem(cacheKey, JSON.stringify(state)); } catch (_) {}
    const failures = incoming.errors?.map(k => markets[k]?.name || 'ECB 환율') || [];
    status.textContent = (cfg ? 'ICE·ECB 확인 ' : '로컬 시세 스냅샷 ')
      + time.format(new Date(state.checkedAt)) + ' KST'
      + (failures.length ? ' · 갱신 실패, 저장값 사용 가능 (' + failures.join(', ') + ')' : '');
  } catch (_) {
    const saved = state.checkedAt ? ' · 마지막 확인 ' + time.format(new Date(state.checkedAt)) + ' KST' : '';
    status.textContent = (cfg
      ? '시세 갱신 실패. Apps Script 최신 배포와 동기화 설정을 확인하세요.'
      : '자동 조회를 시작하려면 대시보드의 계좌 관리에서 기기 간 동기화를 설정하세요.') + saved;
  } finally {
    refresh.disabled = false;
    render();
  }
}

try { state = JSON.parse(localStorage.getItem(cacheKey)) || state; } catch (_) {}
month.addEventListener('change', render);
refresh.addEventListener('click', loadQuotes);
render();
loadQuotes();
setInterval(() => { if (!document.hidden) loadQuotes(); }, 300000);
