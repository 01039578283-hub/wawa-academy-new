import { spawn } from 'node:child_process';
import { createServer } from 'node:http';
import { existsSync, readFileSync, rmSync, statSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { extname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';


const root = resolve(fileURLToPath(new URL('..', import.meta.url)));
const chromeCandidates = [
  'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
];
const chromePath = chromeCandidates.find(existsSync);
if (!chromePath) throw new Error('Chrome 또는 Edge 실행 파일을 찾을 수 없습니다.');

const mime = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.webp': 'image/webp',
  '.svg': 'image/svg+xml',
};

const server = createServer((request, response) => {
  try {
    const pathname = decodeURIComponent(new URL(request.url, 'http://localhost').pathname);
    let file = resolve(root, `.${pathname}`);
    if (!file.startsWith(root)) throw new Error('invalid path');
    if (existsSync(file) && statSync(file).isDirectory()) file = join(file, 'index.html');
    if (!existsSync(file)) {
      response.writeHead(404).end('not found');
      return;
    }
    response.writeHead(200, { 'content-type': mime[extname(file).toLowerCase()] || 'application/octet-stream' });
    response.end(readFileSync(file));
  } catch (error) {
    response.writeHead(400).end(String(error));
  }
});

await new Promise((resolveListen) => server.listen(0, '127.0.0.1', resolveListen));
const base = `http://127.0.0.1:${server.address().port}`;
const debugPort = 9337;
const profile = join(tmpdir(), `site4-chrome-${process.pid}`);
const chrome = spawn(chromePath, [
  '--headless=new',
  '--disable-gpu',
  '--no-sandbox',
  `--remote-debugging-port=${debugPort}`,
  `--user-data-dir=${profile}`,
  'about:blank',
], { stdio: 'ignore' });

async function waitForTarget() {
  for (let attempt = 0; attempt < 50; attempt += 1) {
    try {
      const targets = await fetch(`http://127.0.0.1:${debugPort}/json/list`).then((response) => response.json());
      const page = targets.find((target) => target.type === 'page');
      if (page) return page.webSocketDebuggerUrl;
    } catch {}
    await new Promise((resolveWait) => setTimeout(resolveWait, 100));
  }
  throw new Error('브라우저 디버깅 대상 연결 실패');
}

const socket = new WebSocket(await waitForTarget());
await new Promise((resolveOpen, rejectOpen) => {
  socket.addEventListener('open', resolveOpen, { once: true });
  socket.addEventListener('error', rejectOpen, { once: true });
});
let nextId = 1;
const pending = new Map();
const events = new Map();
socket.addEventListener('message', ({ data }) => {
  const message = JSON.parse(data);
  if (message.id && pending.has(message.id)) {
    const { resolve: resolvePending, reject } = pending.get(message.id);
    pending.delete(message.id);
    if (message.error) reject(new Error(message.error.message));
    else resolvePending(message.result);
  } else if (message.method && events.has(message.method)) {
    for (const callback of events.get(message.method)) callback(message.params);
  }
});

function command(method, params = {}) {
  const id = nextId++;
  socket.send(JSON.stringify({ id, method, params }));
  return new Promise((resolvePending, reject) => pending.set(id, { resolve: resolvePending, reject }));
}

function once(method) {
  return new Promise((resolveEvent) => {
    const callback = (params) => {
      events.get(method).delete(callback);
      resolveEvent(params);
    };
    if (!events.has(method)) events.set(method, new Set());
    events.get(method).add(callback);
  });
}

async function navigate(pathname, width, height, mobile) {
  await command('Emulation.setDeviceMetricsOverride', { width, height, deviceScaleFactor: 1, mobile });
  const loaded = once('Page.loadEventFired');
  await command('Page.navigate', { url: new URL(pathname, base).href });
  await loaded;
  await new Promise((resolveWait) => setTimeout(resolveWait, 350));
}

async function evaluate(expression) {
  const result = await command('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
  if (result.exceptionDetails) throw new Error(result.exceptionDetails.text);
  return result.result.value;
}

await command('Page.enable');
await command('Runtime.enable');

const tests = [];
for (const viewport of [
  { name: 'mobile', width: 390, height: 844, mobile: true },
  { name: 'desktop', width: 1440, height: 900, mobile: false },
]) {
  await navigate('/전국센터/수학학원/', viewport.width, viewport.height, viewport.mobile);
  const initial = await evaluate(`(() => ({
    overflow: document.documentElement.scrollWidth <= window.innerWidth,
    finder: document.querySelectorAll('[data-hub-tools="true"]').length,
    items: document.querySelectorAll('[data-hub-item="true"]').length,
    visibleItems: [...document.querySelectorAll('[data-hub-item="true"]')].filter((item) => !item.hidden).length,
    openDetails: document.querySelectorAll('[data-hub-directory="true"] details[open]').length,
    searchHeight: document.querySelector('#hub-local-search').getBoundingClientRect().height,
    chipMinHeight: Math.min(...[...document.querySelectorAll('.hub-region-chip')].map((item) => item.getBoundingClientRect().height))
  }))()`);
  const search = await evaluate(`(async () => {
    const input = document.querySelector('#hub-local-search');
    input.value = '명일동';
    input.dispatchEvent(new Event('input', { bubbles: true }));
    await new Promise((resolve) => setTimeout(resolve, 40));
    const visible = [...document.querySelectorAll('[data-hub-item="true"]')].filter((item) => !item.hidden);
    return {
      visible: visible.length,
      allMatch: visible.every((item) => item.dataset.search.includes('명일동')),
      linkMinHeight: Math.min(...visible.map((item) => item.getBoundingClientRect().height)),
      status: document.querySelector('.hub-search-status').textContent,
      overflow: document.documentElement.scrollWidth <= window.innerWidth
    };
  })()`);
  const region = await evaluate(`(async () => {
    document.querySelector('[data-hub-clear="true"]').click();
    document.querySelector('[data-hub-region="서울"]').click();
    await new Promise((resolve) => setTimeout(resolve, 40));
    const visible = [...document.querySelectorAll('[data-hub-item="true"]')].filter((item) => !item.hidden);
    return { visible: visible.length, allSeoul: visible.every((item) => item.dataset.region === '서울') };
  })()`);
  tests.push({ page: 'hub', viewport: viewport.name, initial, search, region });

  await navigate('/학습가이드/시험기간-학습계획/', viewport.width, viewport.height, viewport.mobile);
  const article = await evaluate(`(() => {
    const cta = document.querySelector('.header-cta');
    const main = document.querySelector('.article-main');
    const paragraph = main.querySelector(':scope > p');
    const rgb = (value) => value.match(/\\d+(?:\\.\\d+)?/g).slice(0, 3).map(Number);
    const luminance = (color) => {
      const values = rgb(color).map((value) => value / 255).map((value) => value <= .03928 ? value / 12.92 : ((value + .055) / 1.055) ** 2.4);
      return .2126 * values[0] + .7152 * values[1] + .0722 * values[2];
    };
    const ctaStyle = getComputedStyle(cta);
    const ratio = (Math.max(luminance(ctaStyle.backgroundColor), luminance(ctaStyle.color)) + .05) /
      (Math.min(luminance(ctaStyle.backgroundColor), luminance(ctaStyle.color)) + .05);
    return {
      overflow: document.documentElement.scrollWidth <= window.innerWidth,
      mainWithinViewport: main.getBoundingClientRect().width <= window.innerWidth,
      paragraphFontSize: parseFloat(getComputedStyle(paragraph).fontSize),
      paragraphLineHeight: parseFloat(getComputedStyle(paragraph).lineHeight),
      ctaVisible: cta.getBoundingClientRect().width > 0,
      ctaContrast: Number(ratio.toFixed(2))
    };
  })()`);
  tests.push({ page: 'article', viewport: viewport.name, article });
}

const failures = [];
for (const test of tests) {
  if (test.page === 'hub') {
    if (!test.initial.overflow || test.initial.finder !== 1 || test.initial.items !== 1484 || test.initial.visibleItems !== 1484) failures.push(`${test.viewport}:hub-initial`);
    if (test.initial.searchHeight < 44 || test.initial.chipMinHeight < 44) failures.push(`${test.viewport}:hub-target-size`);
    if (test.search.visible !== 4 || !test.search.allMatch || !test.search.overflow || test.search.linkMinHeight < 44) failures.push(`${test.viewport}:hub-search`);
    if (test.region.visible !== 168 || !test.region.allSeoul) failures.push(`${test.viewport}:hub-region`);
  } else {
    if (!test.article.overflow || !test.article.mainWithinViewport || test.article.paragraphFontSize < 16 || test.article.paragraphLineHeight < 27) failures.push(`${test.viewport}:article-layout`);
    if (test.viewport === 'desktop' && (!test.article.ctaVisible || test.article.ctaContrast < 4.5)) failures.push('desktop:cta-contrast');
  }
}

console.log(JSON.stringify({ tests, failures }, null, 2));
socket.close();
chrome.kill();
server.close();
try { rmSync(profile, { recursive: true, force: true }); } catch {}
if (failures.length) process.exitCode = 1;
