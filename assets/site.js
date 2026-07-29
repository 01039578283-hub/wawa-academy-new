document.documentElement.classList.add('js-ready');
document.querySelectorAll('a[href^="#"]').forEach((link) => {
  link.addEventListener('click', (event) => {
    const target = document.querySelector(link.getAttribute('href'));
    if (target) {
      event.preventDefault();
      target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  });
});

document.querySelectorAll('[data-hub-tools="true"]').forEach((finder) => {
  const directories = [...document.querySelectorAll('[data-hub-directory="true"]')];
  const items = [...document.querySelectorAll('[data-hub-item="true"]')];
  const input = finder.querySelector('input[type="search"]');
  const status = finder.querySelector('.hub-search-status');
  const clearButton = finder.querySelector('[data-hub-clear="true"]');
  const regionButtons = [...finder.querySelectorAll('[data-hub-region]')];
  const expandButton = finder.querySelector('[data-hub-expand="true"]');
  const collapseButton = finder.querySelector('[data-hub-collapse="true"]');
  let activeRegion = 'all';

  const normalize = (value) => value.normalize('NFKC').toLocaleLowerCase('ko-KR').replace(/\s+/g, '');

  const refreshContainers = (openMatches = false) => {
    directories.forEach((directory) => {
      const grids = [...directory.querySelectorAll('.math-child-grid, .mini-link-grid')];
      grids.forEach((grid) => {
        const hasVisibleItem = [...grid.querySelectorAll('[data-hub-item="true"]')].some((item) => !item.hidden);
        grid.hidden = !hasVisibleItem;
        const heading = grid.previousElementSibling;
        if (heading && /^H[2-4]$/.test(heading.tagName)) heading.hidden = !hasVisibleItem;
      });

      [...directory.querySelectorAll('details')].reverse().forEach((panel) => {
        const hasVisibleItem = [...panel.querySelectorAll('[data-hub-item="true"]')].some((item) => !item.hidden);
        panel.hidden = !hasVisibleItem;
        if (openMatches && hasVisibleItem) panel.open = true;
      });

      directory.querySelectorAll('.math-child-region, .math-level-hub-card, .english-level-hub-card').forEach((group) => {
        group.hidden = ![...group.querySelectorAll('[data-hub-item="true"]')].some((item) => !item.hidden);
      });
      directory.hidden = !items.some((item) => directory.contains(item) && !item.hidden);
    });
  };

  const applyFilters = () => {
    const query = normalize(input.value);
    let visible = 0;
    items.forEach((item) => {
      const matchesRegion = activeRegion === 'all' || item.dataset.region === activeRegion;
      const matchesQuery = !query || normalize(item.dataset.search || item.textContent).includes(query);
      item.hidden = !(matchesRegion && matchesQuery);
      if (!item.hidden) visible += 1;
    });
    refreshContainers(Boolean(query));
    const regionLabel = activeRegion === 'all' ? '전체 지역' : activeRegion;
    status.textContent = query
      ? `${regionLabel}에서 “${input.value.trim()}” 검색 결과 ${visible.toLocaleString('ko-KR')}개입니다.`
      : `${regionLabel} ${visible.toLocaleString('ko-KR')}개 페이지를 표시합니다.`;
  };

  input.addEventListener('input', applyFilters);
  clearButton.addEventListener('click', () => {
    input.value = '';
    activeRegion = 'all';
    regionButtons.forEach((button) => {
      const active = button.dataset.hubRegion === 'all';
      button.classList.toggle('is-active', active);
      button.setAttribute('aria-pressed', String(active));
    });
    items.forEach((item) => { item.hidden = false; });
    directories.forEach((directory) => {
      directory.hidden = false;
      directory.querySelectorAll('[hidden]').forEach((element) => { element.hidden = false; });
      directory.querySelectorAll('details').forEach((panel) => { panel.open = false; });
    });
    applyFilters();
    input.focus();
  });

  regionButtons.forEach((button) => {
    button.addEventListener('click', () => {
      activeRegion = button.dataset.hubRegion;
      regionButtons.forEach((candidate) => {
        const active = candidate === button;
        candidate.classList.toggle('is-active', active);
        candidate.setAttribute('aria-pressed', String(active));
      });
      applyFilters();
    });
  });

  expandButton.addEventListener('click', () => {
    directories.forEach((directory) => {
      directory.querySelectorAll('details:not([hidden])').forEach((panel) => { panel.open = true; });
    });
  });
  collapseButton.addEventListener('click', () => {
    directories.forEach((directory) => {
      directory.querySelectorAll('details').forEach((panel) => { panel.open = false; });
    });
  });
});

document.querySelectorAll('[data-split-directory="true"]').forEach((directory, directoryIndex) => {
  const input = directory.querySelector('[data-split-search="true"]');
  const clearButton = directory.querySelector('[data-split-clear="true"]');
  const expandButton = directory.querySelector('[data-split-expand="true"]');
  const collapseButton = directory.querySelector('[data-split-collapse="true"]');
  const status = directory.querySelector('[data-split-status="true"]');
  const groupsContainer = directory.querySelector('.split-directory-groups');
  const groups = [...directory.querySelectorAll('[data-split-group="true"]')];
  const items = [...directory.querySelectorAll('[data-split-item="true"]')];

  if (!input || !clearButton || !expandButton || !collapseButton || !status || !groupsContainer || !groups.length) return;

  const initialOpenGroups = new Set(groups.filter((group) => group.open));
  const normalize = (value) => String(value || '')
    .normalize('NFKC')
    .toLocaleLowerCase('ko-KR')
    .replace(/\s+/g, '');
  const format = (value) => value.toLocaleString('ko-KR');
  const statusId = status.id || `split-directory-status-${directoryIndex + 1}`;
  const groupsId = groupsContainer.id || `split-directory-groups-${directoryIndex + 1}`;

  status.id = statusId;
  status.setAttribute('aria-atomic', 'true');
  input.setAttribute('aria-describedby', statusId);
  input.setAttribute('inputmode', 'search');
  groupsContainer.id = groupsId;
  expandButton.setAttribute('aria-controls', groupsId);
  collapseButton.setAttribute('aria-controls', groupsId);

  const pageCount = (visibleItems) => visibleItems.reduce(
    (total, item) => total + item.querySelectorAll('.split-intent-grid a').length,
    0,
  );

  const restoreInitialOpenState = () => {
    groups.forEach((group) => { group.open = initialOpenGroups.has(group); });
  };

  const applyFilter = () => {
    const rawQuery = input.value.trim();
    const query = normalize(rawQuery);

    items.forEach((item) => {
      const searchable = item.dataset.search || item.textContent;
      item.hidden = Boolean(query) && !normalize(searchable).includes(query);
    });

    groups.forEach((group) => {
      const hasVisibleItem = [...group.querySelectorAll('[data-split-item="true"]')]
        .some((item) => !item.hidden);
      group.hidden = !hasVisibleItem;
      if (query && hasVisibleItem) group.open = true;
    });
    if (!query) restoreInitialOpenState();

    const visibleItems = items.filter((item) => !item.hidden);
    const visiblePages = pageCount(visibleItems);
    status.textContent = query
      ? `“${rawQuery}” 검색 결과 ${format(visibleItems.length)}개 동네 · ${format(visiblePages)}개 안내페이지입니다.`
      : `${format(items.length)}개 동네 · ${format(pageCount(items))}개 안내페이지`;
  };

  input.addEventListener('input', applyFilter);
  input.addEventListener('keydown', (event) => {
    if (event.key !== 'Escape' || !input.value) return;
    input.value = '';
    applyFilter();
  });
  clearButton.addEventListener('click', () => {
    input.value = '';
    applyFilter();
    input.focus();
  });
  expandButton.addEventListener('click', () => {
    groups.forEach((group) => {
      if (!group.hidden) group.open = true;
    });
  });
  collapseButton.addEventListener('click', () => {
    groups.forEach((group) => { group.open = false; });
  });

  applyFilter();
});
