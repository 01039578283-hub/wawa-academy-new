(() => {
 'use strict';
 const form = document.querySelector('[data-teacher-filter-form]');
 if (!form) return;
 const search = form.querySelector('[name="q"]');
 const region = form.querySelector('[name="region"]');
 const items = [...document.querySelectorAll('[data-teacher-result]')];
 const status = document.querySelector('[data-teacher-status]');
 const empty = document.querySelector('[data-teacher-empty]');
 const storageKey = `wawa-teachers-20261003:${location.pathname}`;
 const normalize = text => text.normalize('NFC').toLocaleLowerCase('ko-KR').replace(/\s+/g,'');
 const indexed = items.map(el => ({el,text:normalize(el.dataset.search || '')}));
 const update = () => {
   const words = search.value.trim().split(/\s+/).filter(Boolean).map(normalize);
   let branches = 0, introductions = 0;
   for (const {el,text} of indexed) {
     const matches = (!region || !region.value || el.dataset.region === region.value) && words.every(word => text.includes(word));
     el.hidden = !matches;
     if (matches) { branches++; introductions += Number(el.dataset.count || 1); }
   }
   status.textContent = region ? `${branches}개 지점 · 소개 ${introductions.toLocaleString('ko-KR')}건` : `소개글 ${introductions}건`;
   empty.hidden = branches > 0;
   try { sessionStorage.setItem(storageKey,JSON.stringify({q:search.value,region:region?.value || ''})); } catch {}
 };
 const restore = () => {
   try {
     const saved = JSON.parse(sessionStorage.getItem(storageKey) || 'null');
     if (saved && typeof saved.q === 'string') search.value = saved.q;
     if (region && saved && [...region.options].some(o => o.value === saved.region)) region.value = saved.region;
   } catch {}
   update();
 };
 form.addEventListener('submit',event => { event.preventDefault(); update(); });
 search.addEventListener('input',update);
 region?.addEventListener('change',update);
 form.addEventListener('reset',() => { search.value = ''; if(region) region.value = ''; update(); });
 document.querySelector('[data-teacher-clear]')?.addEventListener('click',() => { form.reset(); search.focus(); });
 search.addEventListener('keydown',event => { if (event.key === 'Escape') { event.preventDefault(); search.value = ''; update(); } });
 window.addEventListener('pageshow',restore);
 restore();
})();
