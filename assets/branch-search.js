/* Local progressive-enhancement search: source links remain in the HTML. */
(() => {
  const normalize = (value) => value.normalize('NFKC').toLocaleLowerCase('ko-KR');
  document.querySelectorAll('[data-branch-search-root]').forEach((root) => {
    const input = root.querySelector('[data-branch-search-input]');
    const reset = root.querySelector('[data-branch-search-reset]');
    const status = root.querySelector('[data-branch-search-status]');
    const empty = root.querySelector('[data-branch-search-empty]');
    const results = root.querySelector('[data-branch-search-results]');
    const courseControls = root.querySelector('[data-course-filters]');
    const subject = root.querySelector('[data-branch-subject]');
    const grade = root.querySelector('[data-branch-grade]');
    const review = root.querySelector('[data-branch-review]');
    let courseData = null;
    if (courseControls) {
      try {
        const data = JSON.parse(root.querySelector('#branch-course-data').textContent);
        const valid = Array.from(root.querySelectorAll('[data-branch-course-path]')).every((card) => {
          const record = data[card.dataset.branchCoursePath];
          return record && ['영어', '수학', '국어', '과학', '사회'].every((name) => {
            const facts = record.subjects[name];
            return facts && ['listed', 'review', 'none'].includes(facts.overall)
              && Array.from(grade.options).filter((option) => option.value).every((option) => ['listed', 'review', 'none'].includes(facts.states[option.value]))
              && ['초', '중', '고'].every((stage) => Array.isArray(facts.notes[stage]) && typeof facts.labels[stage] === 'string')
              && typeof facts.summary === 'string' && Array.isArray(facts.wholeNotes);
          });
        });
        if (valid) courseData = data;
      } catch { /* Keep the existing name/region search if course data is unavailable. */ }
      if (!courseData) root.querySelector('#branch-search-help').textContent = '지점명·지역명으로 검색할 수 있습니다. 과목·학년은 지점 상세 안내에서 확인해 주세요.';
    }
    const directory = root.dataset.searchMode === 'directory';
    const entries = Array.from(root.querySelectorAll('[data-branch-search]'), (card) => ({
      card,
      // Keep term boundaries: "마두동 백석동" must not match the query "동백".
      text: normalize(card.dataset.branchSearch).replace(/\s+/gu, ' '),
      course: courseData?.[card.dataset.branchCoursePath],
      detail: card.querySelector('[data-branch-course-match]'),
      wrapper: card.closest('[data-branch-result]'),
      links: card.closest('[data-branch-result]')?.querySelector('[data-branch-course-links]'),
      targets: Array.from(card.closest('[data-branch-result]')?.querySelectorAll('[data-course-subject]') ?? [], (item) => ({
        item, subject: item.dataset.courseSubject, stages: item.dataset.courseStages,
        kind: item.dataset.courseKind, anchor: item.querySelector('a'), label: item.querySelector('a').textContent,
      })),
    }));
    const groups = Array.from(root.querySelectorAll('[data-branch-search-group]'));
    const jumps = Array.from(root.querySelectorAll('[data-branch-search-jump]'));
    let composing = false;
    // Keep all controls together in this history entry. Some browsers restore
    // selects on Back but omit search inputs or unnamed checkboxes.
    const historyKey = 'wawaBranchSearch';
    const readSavedSearch = () => {
      try {
        const saved = window.history.state?.[historyKey];
        return saved?.path === window.location.pathname && typeof saved.query === 'string' ? saved : null;
      } catch { return null; }
    };
    const restoreSearch = (saved) => {
      if (!saved) return;
      input.value = saved.query;
      if (courseData) {
        subject.value = Array.from(subject.options).some((option) => option.value === saved.subject) ? saved.subject : '';
        grade.value = Array.from(grade.options).some((option) => option.value === saved.grade) ? saved.grade : '';
        review.checked = saved.review === true;
      }
    };
    const rememberSearch = () => {
      try {
        const current = window.history.state;
        const saved = { path: window.location.pathname, query: input.value,
          subject: courseData ? subject.value : '', grade: courseData ? grade.value : '',
          review: courseData ? review.checked : false };
        if (JSON.stringify(current?.[historyKey]) !== JSON.stringify(saved)) {
          window.history.replaceState({ ...(current && typeof current === 'object' ? current : {}), [historyKey]: saved }, '');
        }
      } catch { /* Filtering still works when the browser disallows history storage. */ }
    };

    const update = () => {
      const tokens = normalize(input.value.trim()).split(/\s+/u).filter(Boolean);
      const selectedSubject = courseData ? subject.value : '';
      const selectedGrade = courseData ? grade.value : '';
      const filtering = Boolean(selectedSubject || selectedGrade);
      const active = tokens.length > 0 || filtering;
      let matches = 0, listedMatches = 0, reviewMatches = 0, hiddenReviews = 0;
      entries.forEach(({ card, text, course, detail, wrapper, links, targets }) => {
        const textMatch = tokens.every((token) => text.includes(token));
        const choices = filtering ? Object.entries(course.subjects)
          .filter(([name]) => !selectedSubject || name === selectedSubject)
          .map(([name, facts]) => ({ name, facts, state: selectedGrade ? facts.states[selectedGrade] : facts.overall })) : [];
        const listed = choices.filter((choice) => choice.state === 'listed');
        const uncertain = choices.filter((choice) => choice.state === 'review');
        const match = textMatch && (!filtering || listed.length > 0 || (review.checked && uncertain.length > 0));
        if (textMatch && filtering && !listed.length && uncertain.length && !review.checked) hiddenReviews += 1;
        card.hidden = !match;
        if (wrapper) wrapper.hidden = !match;
        if (match) {
          matches += 1;
          if (listed.length) listedMatches += 1;
          else if (filtering) reviewMatches += 1;
        }
        if (detail) {
          detail.replaceChildren();
          detail.hidden = !filtering || !match;
          if (filtering && match) {
            const shown = review.checked ? [...listed, ...uncertain] : listed;
            shown.forEach(({ name, facts, state }) => {
              const group = document.createElement('div');
              const heading = document.createElement('strong');
              heading.className = state === 'review' ? 'branch-match-review' : '';
              heading.textContent = `${name} · ${selectedGrade ? selectedGrade + ' ' : ''}${state === 'review' ? '학년·범위 확인 필요' : selectedGrade ? '학년표에 기재' : '학년 안내 있음'}`;
              group.append(heading);
              const summary = document.createElement('p');
              summary.textContent = selectedGrade ? `해당 학교급 안내: ${facts.labels[selectedGrade[0]]}` : `과목별 안내: ${facts.summary}`;
              group.append(summary);
              const notes = selectedGrade ? facts.notes[selectedGrade[0]] : facts.wholeNotes;
              notes.forEach((note) => {
                const paragraph = document.createElement('p');
                paragraph.className = 'branch-match-note';
                paragraph.textContent = note;
                group.append(paragraph);
              });
              detail.append(group);
            });
          }
        }
        if (links) {
          const included = (state) => state === 'listed' || (review.checked && state === 'review');
          targets.forEach((target) => {
            target.anchor.textContent = target.label;
            const facts = course?.subjects[target.subject];
            target.item.hidden = !match || !filtering || !facts
              || Boolean(selectedSubject && target.subject !== selectedSubject)
              || (selectedGrade
                ? !target.stages.includes(selectedGrade[0]) || !included(facts.states[selectedGrade])
                : !Object.entries(facts.states).some(([g, state]) => target.stages.includes(g[0]) && included(state)));
          });
          // Several subjects can share the branch's course table; show one
          // clearly named link rather than repeating the same destination.
          const fallback = targets.filter((target) => !target.item.hidden && target.kind === 'branch');
          if (fallback.length > 1) {
            fallback[0].anchor.textContent = fallback.map((target) => target.subject).join('·') + ' 과목·학년 안내';
            fallback.slice(1).forEach((target) => { target.item.hidden = true; });
          }
          links.hidden = !targets.some((target) => !target.item.hidden);
        }
      });
      groups.forEach((group) => {
        group.hidden = !group.querySelector('[data-branch-search]:not([hidden])');
      });
      jumps.forEach((jump) => {
        const id = jump.getAttribute('href').slice(1);
        jump.hidden = groups.find((group) => group.id === id)?.hidden ?? false;
      });
      results.hidden = directory && (!active || matches === 0);
      empty.hidden = !active || matches !== 0;
      if (review) review.disabled = !filtering;
      reset.disabled = input.value.length === 0 && !filtering && !review?.checked;
      status.textContent = filtering
        ? `검색 결과 ${matches}개 지점 안내 · 학년표 일치 ${listedMatches}개 · 확인 필요 ${reviewMatches}개${hiddenReviews ? ` · 확인 필요 ${hiddenReviews}개는 체크 항목을 켜면 함께 볼 수 있습니다.` : ''}`
        : active
        ? `검색 결과 ${matches}개 지점 · 전체 ${entries.length}개`
        : directory
          ? `전국 ${entries.length}개 지점 안내에서 검색하거나 아래 지역을 선택하세요.`
          : `전체 ${entries.length}개 지점 안내를 표시하고 있습니다.`;
      empty.textContent = hiddenReviews
        ? '학년표가 일치하는 지점이 없습니다. 확인이 필요한 지점도 보려면 위 체크 항목을 선택해 주세요.'
        : '일치하는 지점이 없습니다. 검색어를 줄이거나 과목·학년 조건을 바꿔보세요.';
      rememberSearch();
    };
    const clear = () => {
      input.value = '';
      if (courseData) { subject.value = ''; grade.value = ''; review.checked = false; }
      composing = false;
      update();
      input.focus();
    };
    input.addEventListener('compositionstart', () => { composing = true; });
    input.addEventListener('compositionend', () => { composing = false; update(); });
    input.addEventListener('input', (event) => {
      if (!composing && !event.isComposing) update();
    });
    input.addEventListener('search', update);
    input.addEventListener('keydown', (event) => {
      if (event.isComposing || composing) return;
      if (event.key === 'Escape') { event.preventDefault(); clear(); }
      if (event.key === 'Enter') event.preventDefault();
    });
    reset.addEventListener('click', clear);
    if (courseData) {
      [subject, grade, review].forEach((control) => control.addEventListener('change', update));
      courseControls.hidden = false;
    }
    window.addEventListener('pageshow', () => {
      const saved = readSavedSearch();
      // Apply after the browser finishes its own persisted-form restoration.
      window.setTimeout(() => { restoreSearch(saved); update(); }, 0);
    });
    restoreSearch(readSavedSearch());
    update();
    root.querySelector('[data-branch-search-controls]').hidden = false;
  });
})();
