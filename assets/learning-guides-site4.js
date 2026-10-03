(() => {
 'use strict';
 document.documentElement.classList.add('lg-ready');
 const header = document.querySelector('.site-header');
 if (header) {
  const alignAnchors = () => document.documentElement.style.setProperty('--lg-scroll-offset', `${Math.ceil(header.getBoundingClientRect().height) + 20}px`);
  alignAnchors();
  if (typeof ResizeObserver === 'function') new ResizeObserver(alignAnchors).observe(header);
  else window.addEventListener('resize', alignAnchors);
 }
 const finder = document.querySelector('[data-guide-finder]');
 if (finder) {
  const input = finder.querySelector('#guide-search');
  const stage = finder.querySelector('#guide-stage');
  const buttons = [...finder.querySelectorAll('[data-guide-category]')];
  const cards = [...document.querySelectorAll('[data-guide-card]')];
  const groups = [...document.querySelectorAll('[data-guide-group]')];
  const empty = document.querySelector('[data-guide-empty]');
  const status = finder.querySelector('#guide-count');
  const historyKey = 'wawaLearningGuides';
  let category = 'all';
  const normalize = value => String(value).normalize('NFKC').toLocaleLowerCase('ko-KR').replace(/\s+/g, ' ').trim();
  const validCategories = new Set(buttons.map(button => button.dataset.guideCategory));
  const validStages = new Set([...stage.options].map(option => option.value));
  const save = () => {
   try { history.replaceState({...history.state, [historyKey]: {query: input.value, stage: stage.value, category}}, '', location.href); } catch { /* Filtering still works if visit state cannot be stored. */ }
  };
  const apply = (remember = true) => {
   const words = normalize(input.value).split(' ').filter(Boolean);
   let count = 0;
   for (const card of cards) {
    const match = (category === 'all' || card.dataset.category === category) &&
     (stage.value === 'all' || card.dataset.stages.split(' ').includes(stage.value)) &&
     words.every(word => normalize(card.textContent).includes(word));
    card.hidden = !match;
    if (match) count++;
   }
   for (const group of groups) group.hidden = !group.querySelector('[data-guide-card]:not([hidden])');
   for (const button of buttons) button.setAttribute('aria-pressed', String(button.dataset.guideCategory === category));
   empty.hidden = count !== 0;
   status.textContent = `${cards.length}편 중 ${count}편을 표시합니다.`;
   if (remember) save();
  };
  const restore = () => {
   const state = history.state?.[historyKey];
   if (state && typeof state === 'object') {
    input.value = typeof state.query === 'string' ? state.query : '';
    stage.value = validStages.has(state.stage) ? state.stage : 'all';
    category = validCategories.has(state.category) ? state.category : 'all';
   }
   apply(false);
  };
  const reset = () => { input.value = ''; stage.value = 'all'; category = 'all'; apply(); input.focus(); };
  input.addEventListener('input', event => { if (!event.isComposing) apply(); });
  input.addEventListener('compositionend', () => apply());
  input.addEventListener('keydown', event => { if (event.key === 'Escape' && !event.isComposing) { event.preventDefault(); reset(); } });
  stage.addEventListener('change', () => apply());
  buttons.forEach(button => button.addEventListener('click', () => { category = button.dataset.guideCategory; apply(); }));
  document.querySelectorAll('[data-guide-reset]').forEach(button => button.addEventListener('click', reset));
  window.addEventListener('pageshow', restore);
  window.addEventListener('popstate', restore);
  restore();
 }
 for (const form of document.querySelectorAll('[data-guide-worksheet]')) {
  const fields = [...form.querySelectorAll('textarea[data-field-label]')];
  const status = form.querySelector('[data-worksheet-status]');
  const record = form.closest('.lg-worksheet').querySelector('[data-print-record]');
  const checks = [...document.querySelectorAll('.lg-checks input')];
  const lines = () => [form.dataset.guideTitle, '가이드: ' + form.dataset.guideUrl, '본문 확인: ' + form.dataset.guideDate, '', ...fields.flatMap((field, index) => [`${index + 1}. ${field.dataset.fieldLabel}`, field.value || '(작성하지 않음)', '']), '오늘의 점검', ...checks.map(check => `${check.checked ? '[v]' : '[ ]'} ${check.value}`), ''];
  const updatePrint = () => { record.textContent = lines().join('\n'); };
  let printDetails = null;
  const preparePrint = () => {
   updatePrint();
   if (printDetails) return;
   printDetails = [...document.querySelectorAll('.lg-article details')].map(detail => ({detail, open: detail.open}));
   printDetails.forEach(({detail}) => { detail.open = true; });
  };
  const restorePrint = () => {
   if (!printDetails) return;
   printDetails.forEach(({detail, open}) => { detail.open = open; });
   printDetails = null;
  };
  form.addEventListener('submit', event => event.preventDefault());
  form.addEventListener('input', () => { status.textContent = '입력 내용은 자동 저장되지 않습니다. 보관하려면 TXT로 내려받아 주세요.'; updatePrint(); });
  checks.forEach(check => check.addEventListener('change', updatePrint));
  form.querySelector('[data-worksheet-download]').addEventListener('click', () => {
   const text = lines().join('\n').replace(/\r\n?|\n/g, '\r\n');
   const blob = new Blob(['\ufeff', text], {type: 'text/plain;charset=utf-8'});
   const url = URL.createObjectURL(blob);
   const link = document.createElement('a');
   link.href = url; link.download = form.dataset.guideSlug + '-학습기록.txt';
   document.body.append(link); link.click(); link.remove();
   setTimeout(() => URL.revokeObjectURL(url), 30000);
   status.textContent = 'TXT 내려받기를 요청했습니다. 내 기기의 다운로드 목록에서 저장 결과를 확인하세요.';
  });
  form.querySelector('[data-worksheet-clear]').addEventListener('click', () => {
   fields.forEach(field => { field.value = ''; });
   updatePrint(); status.textContent = '이 양식의 입력 내용을 지웠습니다. 내려받은 파일과 점검 표시는 유지됩니다.';
   fields[0]?.focus();
  });
  form.querySelector('[data-worksheet-print]').addEventListener('click', () => { preparePrint(); try { window.print(); } finally { restorePrint(); } });
  window.addEventListener('beforeprint', preparePrint);
  window.addEventListener('afterprint', restorePrint);
  updatePrint();
 }
})();
