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
const trendMode = document.getElementById('trend-mode');
const trendChart = document.getElementById('trend-chart');
const trendDay = document.getElementById('trend-day');
const trendValues = document.getElementById('trend-values');
const spreadPairs = [['ttf','hh'], ['jkm','hh'], ['jkm','ttf']];
let observations = {};
let trendSelection = '';
let updateCursor = () => {};
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
  if (!Number.isFinite(value)) return null;
  const timestamp = Date.parse(date);
  for (let offset = 0; offset <= 4; offset++) {
    const day = isoDay(timestamp - offset * dayMs);
    const rate = state.fx[day];
    if (rate > 0) return {price: value * rate / 3.412141633, day, rate};
  }
  return null;
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
  observations = byDate;
  renderTrend();
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
  for (const [left, right] of spreadPairs) {
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
  const query = new URLSearchParams({sym: symbol, tf: '1d', limit: '400'});
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
  const from = isoDay(Date.now() - 372 * dayMs);
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

function chartMark(tag, attributes, text) {
  const element = document.createElementNS('http://www.w3.org/2000/svg', tag);
  for (const [name, value] of Object.entries(attributes)) element.setAttribute(name, value);
  if (text !== undefined) element.textContent = text;
  trendChart.append(element);
  return element;
}

function renderTrend() {
  const period = document.getElementById('trend-period');
  const legend = document.getElementById('trend-legend');
  const width = trendChart.clientWidth, height = 250;
  if (!width) return;
  trendChart.replaceChildren();
  legend.replaceChildren();
  trendChart.setAttribute('viewBox', '0 0 ' + width + ' ' + height);
  const dates = Object.keys(observations).sort();
  const last = Date.parse(dates.at(-1));
  const start = new Date(last);
  start.setUTCFullYear(start.getUTCFullYear() - 1);
  const days = dates.filter(day => Date.parse(day) >= start.getTime());
  const price = (key, day) => {
    const value = observations[day][key];
    return key === 'ttf' ? convert(value, day)?.price : value;
  };
  const colors = ['#3885d2', '#c36c24', '#16846f'];
  const lines = trendMode.value === 'spreads'
    ? spreadPairs.map(([a, b], i) => ({
      name: markets[a].name + ' − ' + markets[b].name, color: colors[i],
      value: day => price(a, day) - price(b, day)
    }))
    : entries.filter(([key]) => trendMode.value !== 'henry' || key === 'hh')
      .map(([key, market], i) => ({name: market.name, color: colors[i], value: day => price(key, day)}));
  const values = days.map(day => ({day, prices: lines.map(line => line.value(day))}));
  const available = values.filter(row => row.prices.some(Number.isFinite));
  trendDay.disabled = available.length < 2;
  if (!available.length) {
    period.textContent = '이 보기에 표시할 시세를 기다리는 중입니다.';
    trendValues.textContent = '';
    updateCursor = () => {};
    return;
  }

  const firstDay = available[0].day;
  const lastDay = available.at(-1).day;
  period.textContent = firstDay + ' ~ ' + lastDay + ' UTC'
    + (Date.parse(firstDay) - start.getTime() > 10 * dayMs ? ' · 확보된 구간 표시' : '');
  const points = available.flatMap(row => row.prices.filter(Number.isFinite));
  if (trendMode.value === 'spreads') points.push(0);
  const bottom = height - 28, left = 42, right = width - 16, top = 14;
  const min = Math.min(...points), max = Math.max(...points);
  const padding = (max - min || 1) * .08;
  const low = min - padding, high = max + padding;
  const x = day => left + (Date.parse(day) - start.getTime()) / (last - start.getTime()) * (right - left);
  const y = value => bottom - (value - low) / (high - low) * (bottom - top);
  const axisNumber = new Intl.NumberFormat('ko-KR', {maximumFractionDigits: 1});
  for (let i = 0; i <= 4; i++) {
    const value = low + (high - low) * i / 4;
    const py = y(value);
    chartMark('line', {x1: left, y1: py, x2: right, y2: py});
    chartMark('text', {x: left - 5, y: py + 4, 'text-anchor': 'end'}, axisNumber.format(value));
  }
  const ticks = width < 480 ? 3 : 6;
  for (let i = 0; i <= ticks; i++) {
    const day = isoDay(start.getTime() + (last - start.getTime()) * i / ticks);
    const anchor = i === 0 ? 'start' : i === ticks ? 'end' : 'middle';
    chartMark('text', {x: x(day), y: height - 8, 'text-anchor': anchor}, day.slice(2, 7));
  }
  if (trendMode.value === 'spreads') {
    chartMark('line', {class: 'cursor', x1: left, y1: y(0), x2: right, y2: y(0)});
  }

  for (const [i, line] of lines.entries()) {
    let path = '', previous = null;
    for (const row of available) {
      const value = row.prices[i];
      if (!Number.isFinite(value)) continue;
      const command = previous && Date.parse(row.day) - Date.parse(previous) <= 7 * dayMs ? 'L' : 'M';
      path += command + x(row.day).toFixed(1) + ',' + y(value).toFixed(1);
      previous = row.day;
    }
    if (path) chartMark('path', {d: path, stroke: line.color, 'stroke-dasharray': i === 1 ? '5 3' : ''});
    add(legend, 'span', line.name + (path ? '' : ' (자료 없음)')).style.setProperty('--series', line.color);
  }
  const cursor = chartMark('line', {class: 'cursor', y1: top, y2: bottom});
  trendDay.max = available.length - 1;
  const selected = available.findIndex(row => row.day === trendSelection);
  trendDay.value = selected >= 0 ? selected : available.length - 1;

  updateCursor = () => {
    const row = available[Number(trendDay.value)];
    cursor.setAttribute('x1', x(row.day));
    cursor.setAttribute('x2', x(row.day));
    trendDay.setAttribute('aria-valuetext', row.day);
    trendValues.textContent = [row.day, ...lines.map((line, i) =>
      line.name + ' ' + (Number.isFinite(row.prices[i]) ? number.format(row.prices[i]) : '—')
    )].join(' · ');
  };
  updateCursor();
  trendChart.onclick = event => {
    const px = event.clientX - trendChart.getBoundingClientRect().left;
    const nearest = available.reduce((best, row, i) =>
      Math.abs(x(row.day) - px) < Math.abs(x(available[best].day) - px) ? i : best, 0);
    trendDay.value = nearest;
    trendDay.dispatchEvent(new Event('input'));
  };
}

trendMode.addEventListener('change', renderTrend);
trendDay.addEventListener('input', () => {
  updateCursor();
  trendSelection = trendDay.getAttribute('aria-valuetext') || '';
});
new ResizeObserver(renderTrend).observe(trendChart);
render();
loadQuotes();
setInterval(() => { if (!document.hidden) loadQuotes(); }, 300000);
