(() => {
  'use strict';
  const normalize = text => String(text || '').normalize('NFKC').toLocaleLowerCase('ko-KR').replace(/\s+/g, ' ').trim();
  const finder = document.querySelector('[data-education-finder]');
  if (finder) {
    const search = finder.querySelector('#education-search');
    const stage = finder.querySelector('#education-stage');
    const cards = Array.from(document.querySelectorAll('[data-education-card]'));
    const buttons = Array.from(finder.querySelectorAll('[data-education-category]'));
    const count = finder.querySelector('[data-education-count]');
    const empty = document.querySelector('[data-education-empty]');
    let category = 'all';
    const update = () => {
      const words = normalize(search.value).split(' ').filter(Boolean);
      let visible = 0;
      cards.forEach(card => {
        const haystack = normalize(card.textContent);
        const stageMatch = stage.value === 'all' || (stage.value === '학부모' ? ['parent', 'health'].includes(card.dataset.category) : card.dataset.stages.split(' ').includes(stage.value));
        const show = (category === 'all' || card.dataset.category === category) && stageMatch && words.every(word => haystack.includes(word));
        card.hidden = !show;
        if (show) visible += 1;
      });
      buttons.forEach(button => button.setAttribute('aria-pressed', String(button.dataset.educationCategory === category)));
      count.textContent = `교육정보 ${visible}편 / 전체 ${cards.length}편`;
      empty.hidden = visible > 0;
      try { sessionStorage.setItem('site4-education-finder', JSON.stringify({q: search.value, stage: stage.value, category})); } catch (_) { /* Filtering remains available when storage is disabled. */ }
    };
    const reset = () => { search.value = ''; stage.value = 'all'; category = 'all'; update(); search.focus(); };
    search.addEventListener('input', update);
    search.addEventListener('keydown', event => { if (event.key === 'Escape') reset(); });
    stage.addEventListener('change', update);
    buttons.forEach(button => button.addEventListener('click', () => { category = button.dataset.educationCategory; update(); }));
    document.querySelectorAll('[data-education-reset]').forEach(button => button.addEventListener('click', reset));
    try {
      const previous = JSON.parse(sessionStorage.getItem('site4-education-finder') || 'null');
      if (previous) {
        search.value = typeof previous.q === 'string' ? previous.q.slice(0, 160) : '';
        if (Array.from(stage.options).some(option => option.value === previous.stage)) stage.value = previous.stage;
        if (buttons.some(button => button.dataset.educationCategory === previous.category)) category = previous.category;
      }
    } catch (_) { /* Invalid saved filters are ignored. */ }
    finder.hidden = false;
    update();
  }
  const local = document.querySelector('[data-education-local]');
  if (!local) return;
  const fields = local.querySelector('.ei-local-fields');
  const region = local.querySelector('#education-region');
  const center = local.querySelector('#education-center');
  const results = local.querySelector('[data-education-local-results]');
  const status = local.querySelector('[data-education-local-status]');
  const safePath = path => typeof path === 'string' && path.startsWith('/') && !path.startsWith('//') && !/[\u0000-\u001f]/.test(path);
  const anchor = (path, label, className) => {
    const element = document.createElement('a');
    element.href = encodeURI(path);
    element.textContent = label;
    if (className) element.className = className;
    return element;
  };
  fetch('/assets/education-centers-site4.json?v=20261003-1', {credentials: 'omit'})
    .then(response => { if (!response.ok) throw new Error('directory'); return response.json(); })
    .then(data => {
      if (!Array.isArray(data.centers)) throw new Error('directory');
      const centers = data.centers.filter(item => safePath(item.path) && Array.isArray(item.courses));
      const stageMap = {elementary: '초등', elem: '초등', primary: '초등', middle: '중등', high: '고등', '초등학생': '초등', '중학생': '중등', '고등학생': '고등'};
      const subjectMap = {english: '영어', math: '수학', combined: '영수', science: '과학'};
      const articleStages = local.dataset.stages.split(' ').filter(Boolean);
      const articleSubject = local.dataset.subject;
      const render = () => {
        results.replaceChildren();
        const branch = centers.find(item => item.path === center.value && item.region === region.value);
        if (!branch) { status.textContent = region.value ? '지점을 선택하면 실제 지점·동네 안내가 표시됩니다.' : '지역과 지점을 선택해 가까운 안내를 찾아보세요.'; return; }
        const heading = document.createElement('h3'); heading.textContent = `${branch.name}과 동네 안내`; results.append(heading);
        results.append(anchor(branch.path, `${branch.name} 지점 안내 보기`, 'ei-button ei-primary'));
        const relevant = branch.courses.filter(course => safePath(course.path) && (!articleStages.length || articleStages.includes(stageMap[course.stage] || course.stage)) && (!articleSubject || articleSubject === (subjectMap[course.subject] || course.subject)));
        const courses = relevant.length ? relevant : branch.courses.filter(course => safePath(course.path));
        const group = document.createElement('div'); group.className = 'ei-local-course-links';
        courses.forEach(course => group.append(anchor(course.path, course.label)));
        results.append(group);
        status.textContent = relevant.length ? `${branch.name}의 관련 동네 안내 ${courses.length}개입니다.` : `${branch.name}에 연결된 기존 동네 안내 ${courses.length}개입니다. 실제 대상과 과목은 지점에서 확인하세요.`;
      };
      const populate = () => {
        results.replaceChildren(); center.replaceChildren();
        const placeholder = document.createElement('option'); placeholder.value = ''; placeholder.textContent = region.value ? '지점을 선택하세요' : '지역을 먼저 선택하세요'; center.append(placeholder);
        centers.filter(item => item.region === region.value).sort((a,b) => a.name.localeCompare(b.name, 'ko')).forEach(item => { const option = document.createElement('option'); option.value = item.path; option.textContent = `${item.name}${item.localities.length ? ' · '+item.localities.join('·') : ''}`; center.append(option); });
        center.disabled = !region.value;
        render();
      };
      region.addEventListener('change', populate); center.addEventListener('change', render);
      fields.hidden = false; populate();
    })
    .catch(() => { status.textContent = '지역 선택 목록을 불러오지 못했습니다. 아래 전체 지점 안내에서 찾아보세요.'; });
})();
