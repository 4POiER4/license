(() => {
  'use strict';
  const money = new Intl.NumberFormat('ru-RU', {minimumFractionDigits: 2, maximumFractionDigits: 2});
  document.querySelectorAll('[data-dismiss]').forEach(button => button.addEventListener('click', () => button.parentElement.remove()));
  const menu = document.querySelector('.mobile-menu');
  const sidebar = document.querySelector('#sidebar');
  const mobileWidth = window.matchMedia('(max-width: 720px)');
  function closeMenu() {
    sidebar?.classList.remove('is-open');
    menu?.setAttribute('aria-expanded', 'false');
    menu?.setAttribute('aria-label', 'Открыть меню');
    if (sidebar) sidebar.inert = mobileWidth.matches;
  }
  closeMenu();
  mobileWidth.addEventListener('change', closeMenu);
  menu?.addEventListener('click', () => {
    const opened = sidebar.classList.toggle('is-open');
    sidebar.inert = mobileWidth.matches && !opened;
    menu.setAttribute('aria-expanded', String(opened));
    menu.setAttribute('aria-label', opened ? 'Закрыть меню' : 'Открыть меню');
  });
  document.addEventListener('keydown', event => {if (event.key === 'Escape') closeMenu();});
  document.addEventListener('click', event => {
    if (mobileWidth.matches && sidebar?.classList.contains('is-open') && !sidebar.contains(event.target) && !menu?.contains(event.target)) closeMenu();
  });

  function syncPerpetual(container) {
    const checkbox = container.querySelector('input[name$="perpetual"]');
    const end = container.querySelector('input[name$="ends_on"]');
    if (!checkbox || !end) return;
    end.disabled = checkbox.checked;
    end.required = !checkbox.checked;
    if (checkbox.checked) end.value = '';
  }
  document.querySelectorAll('[data-position], [data-license-form]').forEach(syncPerpetual);
  document.addEventListener('change', event => {
    if (event.target.matches('input[name$="perpetual"]')) syncPerpetual(event.target.closest('[data-position], [data-license-form]'));
  });

  const positions = document.querySelector('#positions');
  if (positions) {
    const totalForms = document.querySelector('#id_positions-TOTAL_FORMS');
    const currency = document.querySelector('#id_currency');
    const contractAmount = document.querySelector('#id_total_amount');
    function refreshPositions() {
      const visible = [...positions.querySelectorAll('[data-position]')].filter(row => !row.hidden);
      let cents = 0;
      visible.forEach((row, index) => {
        row.querySelector('[data-position-number]').textContent = String(index + 1).padStart(2, '0');
        row.querySelector('.remove-position').hidden = visible.length === 1;
        cents += Math.round((Number(row.querySelector('input[name$="cost"]').value) || 0) * 100);
      });
      document.querySelector('#positions-total').textContent = money.format(cents / 100);
      document.querySelectorAll('[data-contract-currency]').forEach(el => {el.textContent = currency.value;});
      const warning = document.querySelector('#amount-warning');
      const exceeds = contractAmount.value !== '' && cents > Math.round(Number(contractAmount.value) * 100);
      warning.hidden = !exceeds;
      warning.textContent = exceeds ? 'Стоимость позиций ПО превышает сумму договора. Проверьте введённые суммы.' : '';
    }
    document.querySelector('#add-position').addEventListener('click', () => {
      const index = Number(totalForms.value);
      if (index >= 200) return;
      const template = document.querySelector('#empty-position').innerHTML.replaceAll('__prefix__', String(index));
      positions.insertAdjacentHTML('beforeend', template);
      totalForms.value = index + 1;
      const row = positions.lastElementChild;
      syncPerpetual(row);
      refreshPositions();
      row.querySelector('input[name$="software"]').focus();
    });
    positions.addEventListener('click', event => {
      const button = event.target.closest('.remove-position');
      if (!button) return;
      const row = button.closest('[data-position]');
      row.querySelector('input[name$="DELETE"]').checked = true;
      row.hidden = true;
      // Deleted extra forms must not block the browser's required-field validation.
      row.querySelectorAll('input,select,textarea').forEach(input => {input.required = false;});
      refreshPositions();
    });
    document.querySelectorAll('[data-position]').forEach(row => {
      if (row.querySelector('input[name$="DELETE"]')?.checked) {
        row.hidden = true;
        row.querySelectorAll('input,select,textarea').forEach(input => {input.required = false;});
      }
    });
    document.querySelector('#contract-form').addEventListener('input', refreshPositions);
    document.querySelector('#contract-form').addEventListener('change', refreshPositions);
    refreshPositions();
  }

  const dialog = document.querySelector('#reminder-dialog');
  if (dialog) {
    let seen = false;
    try {seen = sessionStorage.getItem('license-reminders-seen') === 'true';} catch (_) { /* Private-mode storage may be unavailable. */ }
    if (!seen || dialog.dataset.force === 'true') dialog.showModal();
    function remember() {try {sessionStorage.setItem('license-reminders-seen', 'true');} catch (_) {}}
    dialog.querySelectorAll('[data-close-dialog]').forEach(button => button.addEventListener('click', () => {remember();dialog.close();}));
    dialog.addEventListener('close', remember);
    dialog.querySelectorAll('a').forEach(link => link.addEventListener('click', remember));
  }
})();
