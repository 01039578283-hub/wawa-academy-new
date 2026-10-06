/* Visible images remain native links when scripting is unavailable. */
(() => {
  if (!window.HTMLDialogElement || typeof HTMLDialogElement.prototype.showModal !== 'function') return;
  let dialog, opener;
  const create = () => {
    dialog = document.createElement('dialog');
    dialog.className = 'media-zoom-dialog';
    dialog.setAttribute('aria-labelledby', 'media-zoom-title');
    dialog.innerHTML = '<header><h2 id="media-zoom-title">이미지 확대</h2><div class="media-zoom-controls"><button type="button" data-zoom-fit>화면에 맞춤</button><button type="button" data-zoom-actual>원본 크기</button><a data-zoom-original target="_blank" rel="noopener">원본 새 창</a><button type="button" data-zoom-close aria-label="이미지 확대 닫기">닫기</button></div></header><p class="media-zoom-help">이미지를 위아래·좌우로 이동해 작은 글씨를 확인하세요. Esc 키로 닫을 수 있습니다.</p><div class="media-zoom-scroll" tabindex="0" aria-label="확대한 이미지 이동 영역"><img alt=""></div>';
    document.body.append(dialog);
    const image = dialog.querySelector('img');
    dialog.querySelector('[data-zoom-close]').addEventListener('click', () => dialog.close());
    dialog.querySelector('[data-zoom-fit]').addEventListener('click', () => { image.style.width = '100%'; });
    dialog.querySelector('[data-zoom-actual]').addEventListener('click', () => { image.style.width = image.getAttribute('width') + 'px'; });
    dialog.addEventListener('click', e => { if (e.target === dialog) dialog.close(); });
    dialog.addEventListener('close', () => { image.removeAttribute('src'); if (opener) opener.focus(); });
  };
  document.addEventListener('click', event => {
    const link = event.target.closest('a[data-image-zoom]');
    if (!link || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    const source = link.querySelector('img');
    if (!source) return;
    if (!dialog) create();
    event.preventDefault(); opener = link;
    const image = dialog.querySelector('img');
    dialog.querySelector('h2').textContent = source.alt + ' 확대';
    image.alt = source.alt;
    image.setAttribute('width', source.getAttribute('width') || source.naturalWidth);
    image.setAttribute('height', source.getAttribute('height') || source.naturalHeight);
    image.style.width = source.hasAttribute('data-page-media') ? image.getAttribute('width') + 'px' : '100%';
    image.src = link.href;
    dialog.querySelector('[data-zoom-original]').href = link.href;
    dialog.showModal();
    const area = dialog.querySelector('.media-zoom-scroll'); area.scrollTop = 0; area.scrollLeft = 0;
  });
})();
