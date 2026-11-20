const token = document.querySelector('meta[name="local-token"]').content;
const form = document.querySelector('#settings');
const start = document.querySelector('#start');
const restore = document.querySelector('#restore');
const check = document.querySelector('#check');
const state = document.querySelector('#state');
const clock = document.querySelector('#clock');
const point = document.querySelector('#point');
const message = document.querySelector('#message');
const confirm = document.querySelector('#confirm');
const review = document.querySelector('#review');
const searchForm = document.querySelector('#place-search');
const searchButton = document.querySelector('#search');
const queryInput = document.querySelector('#query');
const searchMessage = document.querySelector('#search-message');
const searchResults = document.querySelector('#search-results');

const labels = {
  idle: '待机',
  starting: '正在设置',
  active: '模拟中',
  restoring: '正在恢复',
  checking: '正在检查',
  error: '需要检查',
};

let pending = false;
let selectedPoint;
let selectedPlace;
let statusVersion = 0;

function text(element, value) {
  if (element.textContent !== value) element.textContent = value;
}

async function request(path, payload) {
  const options = { headers: { 'X-Local-Token': token } };
  if (payload !== undefined) {
    options.method = 'POST';
    options.headers['Content-Type'] = 'application/json';
    options.body = JSON.stringify(payload);
  }
  const response = await fetch(`/api/${path}`, options);
  const result = await response.json();
  if (!response.ok) throw new Error(result.error);
  return result;
}

function paint(status) {
  const { phase, remaining } = status;
  const busy = ['starting', 'active', 'checking', 'restoring'].includes(phase);
  start.disabled = check.disabled = pending || busy;
  restore.disabled = pending || phase === 'checking' || phase === 'restoring';
  state.dataset.phase = phase;
  const label = status.ios && phase === 'idle' ? `iOS ${status.ios} · 已检查` : labels[phase];
  text(state, label);
  text(message, status.message);
  text(clock, remaining === null ? '—' : `${String(Math.floor(remaining / 60)).padStart(2, '0')}:${String(remaining % 60).padStart(2, '0')}`);
  point.hidden = !status.point;
  text(point, status.point ? `${status.point.latitude}, ${status.point.longitude}` : '');
}

function disconnected() {
  start.disabled = check.disabled = restore.disabled = true;
  state.dataset.phase = 'error';
  text(state, '页面连接中断');
  text(message, '请从 Finder 重新打开工具。若定位仍在模拟，请重新连接 iPhone 后恢复。');
  text(clock, '—');
  point.hidden = true;
}

async function refresh() {
  if (pending) return;
  const version = ++statusVersion;
  try {
    const status = await request('status');
    if (version === statusVersion) paint(status);
  } catch (_) {
    if (version === statusVersion) disconnected();
  }
}

async function operate(action, payload = {}) {
  if (pending) return;
  pending = true;
  statusVersion += 1;
  start.disabled = check.disabled = restore.disabled = true;
  try {
    const status = await request(action, payload);
    pending = false;
    paint(status);
  } catch (error) {
    pending = false;
    if (error instanceof TypeError) {
      disconnected();
    } else {
      await refresh();
      text(message, error.message || '操作未完成。');
    }
  }
}

form.addEventListener('submit', (event) => {
  event.preventDefault();
  selectedPoint = Object.fromEntries(['latitude', 'longitude', 'seconds'].map((name) => [name, form.elements[name].valueAsNumber]));
  const place = selectedPlace ? `${selectedPlace} · ` : '';
  text(review, `${place}坐标 ${selectedPoint.latitude}, ${selectedPoint.longitude}。最长 ${selectedPoint.seconds} 秒。`);
  confirm.returnValue = 'cancel';
  confirm.showModal();
});

function selectPlace(place) {
  selectedPlace = place.name;
  form.elements.latitude.value = place.latitude;
  form.elements.longitude.value = place.longitude;
  searchResults.hidden = true;
  searchResults.replaceChildren();
  text(searchMessage, `已填入「${place.name}」的经纬度，请核对。`);
  form.elements.latitude.focus();
}

for (const name of ['latitude', 'longitude']) {
  form.elements[name].addEventListener('input', () => {
    if (selectedPlace) text(searchMessage, '正在使用手动输入的经纬度。');
    selectedPlace = undefined;
  });
}

searchForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const query = queryInput.value.trim();
  if (!query || searchButton.disabled) return;
  searchButton.disabled = true;
  queryInput.readOnly = true;
  searchResults.hidden = true;
  searchResults.replaceChildren();
  text(searchMessage, '正在搜索 Apple 地图…');
  try {
    const { places } = await request('search', { query });
    for (const place of places) {
      const item = document.createElement('li');
      const button = document.createElement('button');
      const address = document.createElement('span');
      button.type = 'button';
      button.textContent = place.name || place.address;
      address.className = 'result-address';
      address.textContent = [place.address, `${place.latitude.toFixed(5)}, ${place.longitude.toFixed(5)}`].filter(Boolean).join(' · ');
      button.append(address);
      button.addEventListener('click', () => selectPlace(place));
      item.append(button);
      searchResults.append(item);
    }
    searchResults.hidden = places.length === 0;
    text(searchMessage, places.length ? '请选择与测试地点匹配的结果。' : '没有找到匹配地点。可以加上城市、区或门牌号再试。');
  } catch (error) {
    text(searchMessage, error instanceof TypeError ? '搜索暂不可用。可以手动输入经纬度。' : error.message);
  } finally {
    queryInput.readOnly = false;
    searchButton.disabled = false;
  }
});

confirm.addEventListener('close', () => {
  if (confirm.returnValue === 'start') operate('start', selectedPoint);
});
restore.addEventListener('click', () => operate('restore'));
check.addEventListener('click', () => operate('check'));
refresh();
setInterval(refresh, 1000);
