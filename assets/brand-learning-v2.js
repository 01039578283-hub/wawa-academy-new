/* Local to reviewed pages: native, shareable anchor navigation; no player JS. */
document.addEventListener('click', (event) => {
  const link = event.target.closest('a[href^="#"]');
  if (!link || event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
  const hash = link.getAttribute('href');
  if (hash.length < 2) return;
  let id;
  try { id = decodeURIComponent(hash.slice(1)); } catch { return; }
  const target = document.getElementById(id);
  if (!target) return;
  // Stop the legacy listener from replacing native anchors with long smooth scrolling.
  event.stopImmediatePropagation();
}, true);
