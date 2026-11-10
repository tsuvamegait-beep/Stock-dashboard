const markets = {
  hh: {name: '헨리허브', unit: '$/MMBtu', symbol: 'commodity:NYMEX:NG=F',
       label: 'NYMEX 근월 연속선물', link: 'https://www.cmegroup.com/markets/energy/natural-gas/natural-gas.html'},
  ttf: {name: 'TTF', unit: '€/MWh', symbol: 'commodity:ICEENDEX:TFM',
        label: 'ICE Endex 선물', link: 'https://www.ice.com/products/27996665/Dutch-TTF-Gas-Futures/data'},
  jkm: {name: 'JKM', unit: '$/MMBtu', symbol: 'commodity:ICEEUR:JKM',
        label: 'ICE JKM (Platts) 선물', link: 'https://www.ice.com/products/6753280/JKM-LNG-PLATTS-Future/data'}
};
const entries = Object.entries(markets);
const quoteDay = document.getElementById('quote-day');
const refresh = document.getElementById('refresh');
const status = document.getElementById('status');
const number = new Intl.NumberFormat('ko-KR', {minimumFractionDigits: 2, maximumFractionDigits: 3});
const time = new Intl.DateTimeFormat('ko-KR', {timeZone: 'Asia/Seoul', dateStyle: 'short', timeStyle: 'short'});
const cacheKey = 'gas-monitor-browser-v1';
const dayMs = 86400000;
let state = {feeds: {}, fx: {}};
let selectedDay = '';
try { state = JSON.parse(localStorage.getItem(cacheKey)) || state; } catch (_) {}

function add(parent, tag, text, className) {
  const element = document.createElement(tag);
  if (text != null) element.textContent = text;
  if (className) element.className = className;
  parent.append(element);
  return element;
}

function isoDay(ms) {
  return new Date(ms).toISOString().slice(0, 10);
}

function convert(value, date) {
  const day = Object.keys(state.fx).sort().reverse().find(d => d <= date);
  if (!Number.isFinite(value) || !day || Date.parse(date) - Date.parse(day) > 4 * dayMs) return null;
  return {price: value * state.fx[day] / 3.412141633, day, rate: state.fx[day]};
}

function render() {
  const quotes = document.getElementById('quotes');
  quotes.replaceChildren();
  for (const [key, market] of entries) {
    const feed = state.feeds[key];
    const last = feed?.rows[0], previous = feed?.rows[1];
    const card = add(quotes, 'article', null, 'card');
    add(card, 'h3', market.name);
    add(card, 'p', last ? number.format(last.price) : '—', 'price');
    const delta = last && previous && previous.price > 0 ? (last.price / previous.price - 1) * 100 : null;
    add(card, 'p', market.unit + (delta == null ? '' : ' · 전 관측일 대비 ' + (delta > 0 ? '+' : '') + number.format(delta) + '%'), 'muted');
    add(card, 'p', market.label + (feed?.contract ? ' · ' + feed.contract : ''), 'muted');
    add(card, 'p', last
      ? '관측일 ' + last.day + ' UTC' + (Date.now() - Date.parse(last.day) > 5 * dayMs ? ' · 지연 또는 갱신 대기' : '')
      : '조회된 가격 없음', 'muted');
    const converted = key === 'ttf' && last ? convert(last.price, last.day) : null;
    if (converted) add(card, 'p', number.format(converted.price) + ' $/MMBtu · ECB ' + converted.day + ' (' + converted.rate + ' USD/EUR)', 'muted');
    add(card, 'a', '거래소 원본').href = market.link;
  }

  const byDate = {};
  for (const [key] of entries) {
    for (const row of state.feeds[key]?.rows || []) {
      (byDate[row.day] ||= {})[key] = row.price;
    }
  }
  const days = Object.keys(byDate).sort().reverse();
  const common = days.filter(day => entries.every(([key]) => Number.isFinite(byDate[day][key])));
  quoteDay.replaceChildren();
  for (const day of common.slice(0, 14)) add(quoteDay, 'option', day);
  if (!common.length) add(quoteDay, 'option', '—');
  quoteDay.disabled = !common.length;
  if (common.slice(0, 14).includes(selectedDay)) quoteDay.value = selectedDay;

  const day = quoteDay.value, values = byDate[day] || {};
  const usd = {...values, ttf: convert(values.ttf, day)?.price};
  const spreads = document.getElementById('spreads');
  spreads.replaceChildren();
  for (const [left, right] of [['ttf','hh'], ['jkm','hh'], ['jkm','ttf']]) {
    const valid = Number.isFinite(usd[left]) && Number.isFinite(usd[right]);
    const tr = add(spreads, 'tr');
    add(tr, 'th', markets[left].name + ' − ' + markets[right].name).scope = 'row';
    add(tr, 'td', valid ? number.format(usd[left] - usd[right]) : '—');
    add(tr, 'td', valid ? day : '공통 관측일 시세·환율 부족');
  }

  const history = document.getElementById('curve');
  history.replaceChildren();
  for (const date of days.slice(0, 14)) {
    const tr = add(history, 'tr', null, date === day ? 'selected' : '');
    add(tr, 'th', date).scope = 'row';
    for (const [key] of entries) {
      const value = byDate[date][key];
      add(tr, 'td', Number.isFinite(value) ? number.format(value) : '—');
    }
  }
}

async function fetchJson(url) {
  const response = await fetch(url, {cache: 'no-store', signal: AbortSignal.timeout(20000)});
  if (!response.ok) throw new Error('HTTP ' + response.status);
  return response.json();
}

async function loadMarket(key, {symbol}) {
  const query = new URLSearchParams({sym: symbol, tf: '1d', limit: '50'});
  const feed = await fetchJson('https://www.owlchart.com/api/v1/md/ohlcv?' + query);
  if (feed.sym !== symbol || !Array.isArray(feed.k)) throw new Error('Invalid market');
  const source = feed.meta?.source || '';
  if (key === 'ttf' && !source.includes('EUR per MWh')) throw new Error('Invalid TTF unit');
  if (key === 'jkm' && !source.includes('USD per MMBtu')) throw new Error('Invalid JKM unit');
  const rows = feed.k
    .filter(row => Number.isFinite(row[0]) && row[0] > 0 && row[0] <= Date.now() && Number.isFinite(row[4]))
    .map(row => ({day: isoDay(row[0]), price: row[4]}))
    .sort((a, b) => b.day.localeCompare(a.day));
  if (!rows.length) throw new Error('No market data');
  const contract = /\b(?:TFM|JKM) ([A-Z][a-z]{2}\d{2})\b/.exec(source)?.[1] || '';
  return {rows, contract};
}

async function loadFx() {
  const from = isoDay(Date.now() - 65 * dayMs);
  const rows = await fetchJson('https://api.frankfurter.dev/v2/rates?base=EUR&quotes=USD&providers=ecb&from=' + from);
  const rates = Object.fromEntries(rows
    .filter(r => r.base === 'EUR' && r.quote === 'USD' && r.rate > 0)
    .map(r => [r.date, r.rate]));
  if (!Object.keys(rates).length) throw new Error('No exchange rates');
  return rates;
}

async function loadQuotes() {
  if (refresh.disabled) return;
  refresh.disabled = true;
  status.textContent = '시세와 환율을 확인하는 중…';
  try {
    const requests = [...entries.map(([key, market]) => loadMarket(key, market)), loadFx()];
    const results = await Promise.allSettled(requests);
    const failures = [];
    results.forEach((result, i) => {
      const market = entries[i];
      if (result.status === 'rejected') failures.push(market?.[1].name || 'ECB 환율');
      else if (market) state.feeds[market[0]] = result.value;
      else state.fx = result.value;
    });
    if (failures.length < results.length) state.checkedAt = Date.now();
    try { localStorage.setItem(cacheKey, JSON.stringify(state)); } catch (_) {}
    const checked = state.checkedAt ? ' · 최근 조회 ' + time.format(state.checkedAt) + ' KST' : '';
    status.textContent = failures.length
      ? '조회 실패 (' + failures.join(', ') + ')' + (Object.keys(state.feeds).length ? ' · 저장된 값이 있으면 표시' : '') + checked
      : '시세·환율 조회 완료' + checked;
    render();
  } finally {
    refresh.disabled = false;
  }
}

quoteDay.addEventListener('change', () => {
  selectedDay = quoteDay.value;
  render();
});
refresh.addEventListener('click', loadQuotes);
render();
loadQuotes();
setInterval(() => { if (!document.hidden) loadQuotes(); }, 300000);
