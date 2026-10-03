(() => {
  'use strict';
  const finder = document.querySelector('[data-curriculum-finder]');
  if (finder) {
    const search = document.getElementById('curriculum-search');
    const stage = document.getElementById('curriculum-stage');
    const grade = document.getElementById('curriculum-grade');
    const subject = document.getElementById('curriculum-subject');
    const cards = Array.from(document.querySelectorAll('[data-curriculum-card]'));
    const count = finder.querySelector('[data-curriculum-count]');
    const empty = document.querySelector('[data-curriculum-empty]');
    const update = () => {
      const words = search.value.trim().toLocaleLowerCase('ko').split(/\s+/).filter(Boolean);
      let shown = 0;
      for (const card of cards) {
        const fits = (stage.value === 'all' || card.dataset.stage === stage.value) &&
          (grade.value === 'all' || card.dataset.grade === grade.value) &&
          (subject.value === 'all' || card.dataset.subject === subject.value) &&
          words.every(word => card.textContent.toLocaleLowerCase('ko').includes(word));
        card.hidden = !fits;
        if (fits) shown++;
      }
      count.textContent = `학년·과목 안내 ${shown}개 / 전체 ${cards.length}개`;
      empty.hidden = shown > 0;
    };
    stage.addEventListener('change', () => {
      if (grade.value !== 'all' && stage.value !== 'all' && grade.selectedOptions[0].dataset.stage !== stage.value) grade.value = 'all';
      for (const option of grade.options) option.disabled = option.value !== 'all' && stage.value !== 'all' && option.dataset.stage !== stage.value;
      update();
    });
    grade.addEventListener('change', update);
    subject.addEventListener('change', update);
    search.addEventListener('input', update);
    for (const reset of document.querySelectorAll('[data-curriculum-reset]')) reset.addEventListener('click', () => {
      search.value = ''; stage.value = 'all'; grade.value = 'all'; subject.value = 'all';
      for (const option of grade.options) option.disabled = false;
      update(); search.focus();
    });
    finder.hidden = false;
    update();
  }

  const local = document.querySelector('[data-curriculum-local]');
  if (!local) return;
  const region = document.getElementById('curriculum-region');
  const select = document.getElementById('curriculum-center');
  const status = local.querySelector('[data-curriculum-local-status]');
  const results = local.querySelector('[data-curriculum-local-results]');
  const stageNames = {elementary:'초등',middle:'중등',high:'고등'};
  const option = (label, value) => {const node=document.createElement('option');node.textContent=label;node.value=value;return node;};
  const addLink = (path, label) => {
    const node = document.createElement('a');
    node.href = path.split('/').map(encodeURIComponent).join('/');
    node.textContent = label; results.append(node);
  };
  fetch('/assets/curriculum-centers-site4.json', {credentials:'same-origin'})
    .then(response => {if (!response.ok) throw new Error('directory');return response.json();})
    .then(data => {
      const centers = data.centers;
      local.querySelector('[data-curriculum-enhanced]').hidden = false;
      region.addEventListener('change', () => {
        select.replaceChildren(option(region.value ? '지점을 선택하세요' : '지역을 먼저 선택하세요', ''));
        for (const center of centers.filter(center => center.region === region.value)) select.append(option(center.name, center.path));
        select.disabled = !region.value; results.replaceChildren();
        status.textContent = region.value ? `${region.value}의 지점을 선택하세요.` : '지역을 선택하면 지점과 동네별 안내를 볼 수 있습니다.';
      });
      select.addEventListener('change', () => {
        results.replaceChildren();
        const center = centers.find(center => center.path === select.value);
        if (!center) {status.textContent='지점을 선택하면 해당 지점과 동네별 안내를 볼 수 있습니다.';return;}
        addLink(center.path, `${center.name} 지점 안내 보기`);
        const matches = center.courses.filter(course =>
          (!local.dataset.grade || course.grades.includes(local.dataset.grade)) &&
          (!local.dataset.stage || stageNames[course.stage] === local.dataset.stage) &&
          (!local.dataset.subject || course.subject === local.dataset.subject));
        for (const course of matches.slice(0,8)) addLink(course.path, course.label);
        status.textContent = matches.length ? `${center.name}의 지점 안내와 관련 동네 안내 ${Math.min(matches.length,8)}개입니다.${matches.length>8?' 더 많은 안내는 지점 페이지에서 볼 수 있습니다.':''}` : `${center.name} 지점 안내를 살펴보세요. 이 학년·과목에 대응하는 별도 동네 안내 링크가 없어, 현재 개설 과목·학년은 지점에 확인해야 합니다.`;
      });
      status.textContent = '지역과 지점을 선택해 관련 안내를 찾아보세요.';
    }).catch(() => {status.textContent='전체 지점 안내에서 가까운 지점과 현재 개설 과목·학년을 확인하세요.';});
})();
