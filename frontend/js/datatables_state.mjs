const DATATABLES_STATE_PREFIX = 'DataTables_';

export const DATATABLES_STATE_CONFIG = Object.freeze({
  stateSave: true,
  stateDuration: 0,
});

export function clearDataTablesState(storage) {
  for (let index = storage.length - 1; index >= 0; index -= 1) {
    const key = storage.key(index);
    if (key !== null && key.startsWith(DATATABLES_STATE_PREFIX)) {
      storage.removeItem(key);
    }
  }
}

export function registerDataTablesStateClearOnLogout(document, storage) {
  const logoutLinks = document.querySelectorAll('[data-clear-datatables-state]');
  logoutLinks.forEach((link) => {
    link.addEventListener('click', () => clearDataTablesState(storage));
  });
}

export function createDataTablesStateResetButton(
  reload = () => window.location.reload(),
) {
  return {
    text: '<i class="fas fa-history"></i> Resetuj ustawienia tabeli',
    className: 'btn-outline-dark btn-sm px-2 px-md-4',
    action(event, table) {
      table.state.clear();
      reload();
    },
  };
}
