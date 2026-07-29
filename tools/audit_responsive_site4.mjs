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
  if (result.exceptionDetails) {
    const detail = result.exceptionDetails.exception?.description || result.exceptionDetails.text;
    throw new Error(detail);
  }
  return result.result.value;
}

await command('Page.enable');
await command('Runtime.enable');

const hubPages = [
  { name: 'math', path: '/전국센터/수학학원/', expectedLinks: 1 },
  { name: 'high-math', path: '/전국센터/고등수학학원/', expectedLinks: 1 },
];
const tests = [];
for (const viewport of [
  { name: 'mobile', width: 390, height: 844, mobile: true },
  { name: 'desktop', width: 1440, height: 900, mobile: false },
]) {
  await navigate('/전국센터/', viewport.width, viewport.height, viewport.mobile);
  const centerRoot = await evaluate(`(() => {
    const structuredNodes = [...document.querySelectorAll('script[type="application/ld+json"]')]
      .flatMap((script) => {
        try {
          const data = JSON.parse(script.textContent);
          const roots = Array.isArray(data) ? data : [data];
          return roots.flatMap((root) => Array.isArray(root?.['@graph']) ? root['@graph'] : [root]);
        } catch {
          return [];
        }
      });
    const categoryItemList = structuredNodes.find((node) =>
      (Array.isArray(node?.['@type']) ? node['@type'] : [node?.['@type']]).includes('ItemList') &&
      String(node?.['@id'] || '').endsWith('#category-list'));
    return {
      overflow: document.documentElement.scrollWidth <= window.innerWidth,
      h1Count: document.querySelectorAll('h1').length,
      cards: document.querySelectorAll('.center-card').length,
      itemListItems: categoryItemList?.itemListElement?.length || 0,
      itemListNumber: Number(categoryItemList?.numberOfItems || 0),
      gridColumns: [...document.querySelectorAll('.center-card-grid')].map((grid) =>
        getComputedStyle(grid).gridTemplateColumns.split(' ').filter(Boolean).length)
    };
  })()`);
  tests.push({ page: 'center-root', viewport: viewport.name, expectedColumns: viewport.mobile ? 1 : 3, centerRoot });

  for (const hubPage of hubPages) {
    await navigate(hubPage.path, viewport.width, viewport.height, viewport.mobile);
    const categoryHub = await evaluate(`(() => ({
      overflow: document.documentElement.scrollWidth <= window.innerWidth,
      h1Count: document.querySelectorAll('h1').length,
      regionCards: document.querySelectorAll('.split-region-card').length,
      cardMinHeight: Math.min(...[...document.querySelectorAll('.split-region-card')].map((item) => item.getBoundingClientRect().height)),
      validRegionTargets: [...document.querySelectorAll('.split-region-card')].every((item) =>
        ['서울', '경기', '인천', '충청', '대전', '대구', '울산', '부산', '경상', '광주', '전라', '강원', '제주']
          .includes(decodeURIComponent(item.pathname).split('/').filter(Boolean).at(-1)))
    }))()`);
    tests.push({ page: 'category-hub', hubPage, viewport: viewport.name, categoryHub });

    await navigate(`${hubPage.path}서울/`, viewport.width, viewport.height, viewport.mobile);
    const regionInitial = await evaluate(`(() => ({
      overflow: document.documentElement.scrollWidth <= window.innerWidth,
      h1Count: document.querySelectorAll('h1').length,
      directory: document.querySelectorAll('[data-split-directory="true"]').length,
      items: document.querySelectorAll('[data-split-item="true"]').length,
      searchHeight: document.querySelector('[data-split-search="true"]').getBoundingClientRect().height,
      buttonMinHeight: Math.min(...[...document.querySelectorAll('.split-directory-tools button')].map((item) => item.getBoundingClientRect().height))
    }))()`);
    const regionSearch = await evaluate(`(async () => {
      const input = document.querySelector('[data-split-search="true"]');
      input.value = '명일동';
      input.dispatchEvent(new Event('input', { bubbles: true }));
      await new Promise((resolve) => setTimeout(resolve, 40));
      const visible = [...document.querySelectorAll('[data-split-item="true"]')].filter((item) => !item.hidden);
      return {
        visible: visible.length,
        allMatch: visible.every((item) => item.dataset.search.includes('명일동')),
        links: visible.reduce((sum, item) => sum + item.querySelectorAll('a').length, 0),
        linkMinHeight: Math.min(...visible.flatMap((item) => [...item.querySelectorAll('a')]).map((item) => item.getBoundingClientRect().height)),
        status: document.querySelector('[data-split-status="true"]').textContent,
        overflow: document.documentElement.scrollWidth <= window.innerWidth
      };
    })()`);
    tests.push({ page: 'region-hub', hubPage, viewport: viewport.name, regionInitial, regionSearch });

    await navigate(`${hubPage.path}경기/`, viewport.width, viewport.height, viewport.mobile);
    const gyeonggiHub = await evaluate(`(() => ({
      overflow: document.documentElement.scrollWidth <= window.innerWidth,
      h1Count: document.querySelectorAll('h1').length,
      districtCards: document.querySelectorAll('.split-district-card').length,
      itemDirectories: document.querySelectorAll('[data-split-directory="true"]').length,
      cardMinHeight: Math.min(...[...document.querySelectorAll('.split-district-card')].map((item) => item.getBoundingClientRect().height))
    }))()`);
    tests.push({ page: 'gyeonggi-hub', hubPage, viewport: viewport.name, gyeonggiHub });

    await navigate(`${hubPage.path}경기/고양시/`, viewport.width, viewport.height, viewport.mobile);
    const districtHub = await evaluate(`(() => ({
      overflow: document.documentElement.scrollWidth <= window.innerWidth,
      h1Count: document.querySelectorAll('h1').length,
      directory: document.querySelectorAll('[data-split-directory="true"]').length,
      items: document.querySelectorAll('[data-split-item="true"]').length,
      linkCounts: [...document.querySelectorAll('[data-split-item="true"]')].map((item) => item.querySelectorAll('a').length)
    }))()`);
    tests.push({ page: 'district-hub', hubPage, viewport: viewport.name, districtHub });
  }

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

  for (const detailPage of [
    {
      name: 'subject-high-math',
      path: '/전국센터/수학학원/명일동고등수학학원/',
      role: 'subject-high-math',
      breadcrumbParents: ['/전국센터/고등수학학원/', '/전국센터/고등수학학원/서울/'],
    },
    { name: 'grade-high-math', path: '/전국센터/고등학생학원/명일동고등학생수학학원/', role: 'grade-high-math' },
  ]) {
    await navigate(detailPage.path, viewport.width, viewport.height, viewport.mobile);
    const detail = await evaluate(`(() => {
      const section = document.querySelector('[data-intent-role]');
      const heading = section.querySelector('#intent-role-title');
      const paragraph = section.querySelector('.geo-summary-panel > p:not(.eyebrow)');
      const counterpart = section.querySelector('.intent-counterpart a');
      const breadcrumbPaths = [...document.querySelectorAll('.seo-breadcrumb a')]
        .map((link) => decodeURIComponent(link.pathname));
      const structuredBreadcrumbPaths = [...document.querySelectorAll('script[type="application/ld+json"]')]
        .flatMap((script) => {
          try {
            const data = JSON.parse(script.textContent);
            const roots = Array.isArray(data) ? data : [data];
            const nodes = roots.flatMap((root) => Array.isArray(root?.['@graph']) ? root['@graph'] : [root]);
            return nodes
              .filter((node) => (Array.isArray(node?.['@type']) ? node['@type'] : [node?.['@type']]).includes('BreadcrumbList'))
              .flatMap((node) => node.itemListElement || [])
              .map((item) => item.item || item.url)
              .filter(Boolean)
              .map((url) => decodeURIComponent(new URL(url, location.href).pathname));
          } catch {
            return [];
          }
        });
      return {
        overflow: document.documentElement.scrollWidth <= window.innerWidth,
        h1Count: document.querySelectorAll('h1').length,
        role: section.dataset.intentRole,
        sectionWithinViewport: section.getBoundingClientRect().width <= window.innerWidth,
        heading: heading.textContent.trim(),
        paragraphFontSize: parseFloat(getComputedStyle(paragraph).fontSize),
        paragraphLineHeight: parseFloat(getComputedStyle(paragraph).lineHeight),
        answerCards: section.querySelectorAll('.geo-answer-card').length,
        checklistCards: section.querySelectorAll('.geo-check-card').length,
        counterpart: counterpart ? counterpart.href : '',
        breadcrumbPaths,
        structuredBreadcrumbPaths
      };
    })()`);
    tests.push({ page: 'detail', detailPage, viewport: viewport.name, detail });
  }
}

const samePaths = (actual, expected) =>
  actual.length === expected.length && actual.every((path, index) => path === expected[index]);
const failures = [];
for (const test of tests) {
  if (test.page === 'center-root') {
    if (!test.centerRoot.overflow || test.centerRoot.h1Count !== 1 || test.centerRoot.cards !== 15 || test.centerRoot.itemListItems !== 15 || test.centerRoot.itemListNumber !== 15) failures.push(`${test.viewport}:center-root`);
    if (test.centerRoot.gridColumns.length !== 3 || !test.centerRoot.gridColumns.every((columns) => columns === test.expectedColumns)) failures.push(`${test.viewport}:center-root-grid`);
  } else if (test.page === 'category-hub') {
    if (!test.categoryHub.overflow || test.categoryHub.h1Count !== 1 || test.categoryHub.regionCards !== 13 || !test.categoryHub.validRegionTargets) failures.push(`${test.viewport}:${test.hubPage.name}:category-hub`);
    if (test.categoryHub.cardMinHeight < 44) failures.push(`${test.viewport}:${test.hubPage.name}:category-target-size`);
  } else if (test.page === 'region-hub') {
    if (!test.regionInitial.overflow || test.regionInitial.h1Count !== 1 || test.regionInitial.directory !== 1 || test.regionInitial.items !== 42) failures.push(`${test.viewport}:${test.hubPage.name}:region-hub`);
    if (test.regionInitial.searchHeight < 44 || test.regionInitial.buttonMinHeight < 44) failures.push(`${test.viewport}:${test.hubPage.name}:region-target-size`);
    if (test.regionSearch.visible !== 1 || test.regionSearch.links !== test.hubPage.expectedLinks || !test.regionSearch.allMatch || !test.regionSearch.overflow || test.regionSearch.linkMinHeight < 44) failures.push(`${test.viewport}:${test.hubPage.name}:region-search`);
  } else if (test.page === 'gyeonggi-hub') {
    if (!test.gyeonggiHub.overflow || test.gyeonggiHub.h1Count !== 1 || test.gyeonggiHub.districtCards !== 22 || test.gyeonggiHub.itemDirectories !== 0 || test.gyeonggiHub.cardMinHeight < 44) failures.push(`${test.viewport}:${test.hubPage.name}:gyeonggi-hub`);
  } else if (test.page === 'district-hub') {
    if (!test.districtHub.overflow || test.districtHub.h1Count !== 1 || test.districtHub.directory !== 1 || test.districtHub.items < 1 || !test.districtHub.linkCounts.every((count) => count === test.hubPage.expectedLinks)) failures.push(`${test.viewport}:${test.hubPage.name}:district-hub`);
  } else if (test.page === 'article') {
    if (!test.article.overflow || !test.article.mainWithinViewport || test.article.paragraphFontSize < 16 || test.article.paragraphLineHeight < 27) failures.push(`${test.viewport}:article-layout`);
    if (test.viewport === 'desktop' && (!test.article.ctaVisible || test.article.ctaContrast < 4.5)) failures.push('desktop:cta-contrast');
  } else {
    if (!test.detail.overflow || !test.detail.sectionWithinViewport || test.detail.h1Count !== 1) failures.push(`${test.viewport}:${test.detailPage.name}:layout`);
    if (test.detail.role !== test.detailPage.role || test.detail.answerCards !== 4 || test.detail.checklistCards !== 4) failures.push(`${test.viewport}:${test.detailPage.name}:role`);
    if (test.detail.paragraphFontSize < 16 || test.detail.paragraphLineHeight < 27 || !test.detail.counterpart) failures.push(`${test.viewport}:${test.detailPage.name}:readability`);
    if (test.detailPage.breadcrumbParents) {
      const expected = test.detailPage.breadcrumbParents;
      const visibleParents = test.detail.breadcrumbPaths.slice(-expected.length);
      const structuredPaths = test.detail.structuredBreadcrumbPaths;
      const hasCurrentItem = structuredPaths[structuredPaths.length - 1] === test.detailPage.path;
      const structuredParents = structuredPaths.slice(
        -(expected.length + Number(hasCurrentItem)),
        hasCurrentItem ? -1 : undefined,
      );
      if (!samePaths(visibleParents, expected) || !samePaths(structuredParents, expected)) failures.push(`${test.viewport}:${test.detailPage.name}:breadcrumb-hub`);
    }
  }
}

console.log(JSON.stringify({ tests, failures }, null, 2));
socket.close();
chrome.kill();
server.close();
try { rmSync(profile, { recursive: true, force: true }); } catch {}
if (failures.length) process.exitCode = 1;
