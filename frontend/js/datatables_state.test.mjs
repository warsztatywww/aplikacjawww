import assert from 'node:assert/strict';
import test from 'node:test';

import {
  DATATABLES_STATE_CONFIG,
  clearDataTablesState,
  createDataTablesStateResetButton,
  registerDataTablesStateClearOnLogout,
} from './datatables_state.mjs';

class MemoryStorage {
  constructor(entries) {
    this.entries = new Map(entries);
  }

  get length() {
    return this.entries.size;
  }

  key(index) {
    return [...this.entries.keys()][index] ?? null;
  }

  removeItem(key) {
    this.entries.delete(key);
  }
}

test('clearDataTablesState removes only DataTables state', () => {
  const storage = new MemoryStorage([
    ['DataTables_participants-table_/participants/', '{}'],
    ['DataTables_cost-admin-table_/costs/', '{}'],
    ['unrelated-preference', 'keep me'],
  ]);

  clearDataTablesState(storage);

  assert.deepEqual([...storage.entries], [['unrelated-preference', 'keep me']]);
});

test('state config uses indefinite localStorage persistence', () => {
  assert.equal(DATATABLES_STATE_CONFIG.stateSave, true);
  assert.equal(DATATABLES_STATE_CONFIG.stateDuration, 0);
  assert.equal('stateSaveCallback' in DATATABLES_STATE_CONFIG, false);
  assert.equal('stateLoadCallback' in DATATABLES_STATE_CONFIG, false);
});

test('logout click clears all saved DataTables state', () => {
  let clickHandler;
  const logoutLink = {
    addEventListener(eventName, handler) {
      assert.equal(eventName, 'click');
      clickHandler = handler;
    },
  };
  const document = {
    querySelectorAll(selector) {
      assert.equal(selector, '[data-clear-datatables-state]');
      return [logoutLink];
    },
  };
  const storage = new MemoryStorage([
    ['DataTables_participants-table_/participants/', '{}'],
  ]);

  registerDataTablesStateClearOnLogout(document, storage);
  clickHandler();

  assert.equal(storage.length, 0);
});

test('table reset button clears its state and reloads the page', () => {
  let stateWasCleared = false;
  let pageWasReloaded = false;
  const table = {
    state: {
      clear() {
        stateWasCleared = true;
      },
    },
  };
  const button = createDataTablesStateResetButton(() => {
    pageWasReloaded = true;
  });

  button.action(null, table);

  assert.equal(stateWasCleared, true);
  assert.equal(pageWasReloaded, true);
  assert.match(button.text, /Resetuj/);
});
