// Use Streamlit's own theme selector so forms, tables and session data follow.
// This local shortcut targets the native controls shipped with Streamlit 1.58.
(() => {
  window.portalThemeShortcut?.dispose();
  const controller = new AbortController();
  let pending = null;
  let deadline = null;
  const status = (text) => {
    const node = document.querySelector('.portal-theme-status');
    if (node) node.textContent = text;
  };
  const sync = () => {
    const app = document.querySelector('[data-testid="stApp"]');
    if (!app) return;
    const mode = getComputedStyle(app).colorScheme === 'dark' ? 'Dark' : 'Light';
    document.querySelectorAll('[data-portal-theme]').forEach(button => {
      const value = String(button.dataset.portalTheme === mode);
      if (button.getAttribute('aria-pressed') !== value) button.setAttribute('aria-pressed', value);
    });
  };
  const finish = () => {
    pending = null;
    clearTimeout(deadline);
  };
  const selectNativeTheme = () => {
    if (!pending) return;
    const root = document.querySelector('[data-testid="stThemeSwitcher"]');
    const choice = root && [...root.querySelectorAll('button')]
      .find(button => button.textContent.trim().endsWith(pending));
    if (!choice) return;
    finish();
    choice.click();
    document.querySelector('button[aria-label="Main menu"]')?.click();
    status('');
    sync();
  };
  const observer = new MutationObserver(() => { selectNativeTheme(); sync(); });
  observer.observe(document.body, {subtree: true, childList: true, attributes: true, attributeFilter: ['class', 'style']});
  document.addEventListener('click', event => {
    const button = event.target.closest('[data-portal-theme]');
    if (!button) return;
    if (button.getAttribute('aria-pressed') === 'true') return;
    const menu = document.querySelector('button[aria-label="Main menu"]');
    if (!menu) { status('Menu tema belum tersedia. Coba kembali setelah halaman selesai dimuat.'); return; }
    pending = button.dataset.portalTheme;
    status('');
    if (!document.querySelector('[data-testid="stThemeSwitcher"]')) menu.click();
    deadline = setTimeout(() => {
      finish();
      status('Gunakan menu ⋮ di kanan atas untuk memilih Light atau Dark.');
    }, 2000);
    selectNativeTheme();
  }, {signal: controller.signal});
  window.portalThemeShortcut = {dispose() {controller.abort(); observer.disconnect(); finish();}};
  sync();
})();
