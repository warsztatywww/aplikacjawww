import datatables_Polish from 'datatables.net-plugins/i18n/pl.json';
import { Base64 } from 'js-base64';
import { vcard_export } from './datatables_vcard_export.ts';

// Remove once my i18n contributions at https://datatables.net/plug-ins/i18n/ make it into the release
datatables_Polish.searchPanes.emptyPanes = 'Brak filtrów';
datatables_Polish.searchPanes.loadMessage = 'Ładuję filtry...';
datatables_Polish.searchPanes.title = 'Aktywne filtry - %d';
datatables_Polish.searchPanes.showMessage = 'Pokaż wszystkie';
datatables_Polish.searchPanes.collapseMessage = 'Ukryj wszystkie';
datatables_Polish.searchPanes.collapse = {
  "0": "Filtry",
  "_": "Filtry (%d)"
};

window.gen_datatables_config = (myConfig_) => {
  const myConfig = Object.assign({
    paging: true,
    filters: true,
    vcardEnable: false,
    vcardName: null,
  }, myConfig_);

  const column_selector = (idx, data, node) => {
    // https://datatables.net/forums/discussion/42192/exporting-data-with-buttons-and-responsive-extensions-controlled-by-column-visibility
    // When the colvis/responsive plugin hides a column this might be done in one of 2 ways:
    // By adding the noVis class or by physically detaching the DOM element from the table
    if ($(node).hasClass('noVis')) {
      return false;
    }
    const table = $(node).closest('table');
    return table.length === 0 ? false : table.DataTable().column(idx).visible();
  };

  function strip_tags(data, row, column, node)
  {
    return $.trim($("<div/>").html(data).text().replace(/( *\n *)+/g, '\n').replace(/ +/g, ' '));
  }

  function strip_tags_and_newlines(data, row, column, node)
  {
    return strip_tags(data, row, column, node).replace(/\n|\r/g, ', ');
  }

  let config = {
    dom: 'B' + (myConfig.filters ? 'P' : '') + 'frti' + (myConfig.paging ? 'p' : '') + 'l',
    paging: myConfig.paging,
    colReorder: true,
    deferRender: true,
    createdRow: (row) => {
      $(row).find('[data-toggle="tooltip"]').tooltip();
      $(row).find('[data-toggle="popover"]').popover();
    },
    buttons: {
      dom: {
        button: {
          className: 'btn',
        },
      },
      buttons: [
        {
          extend: 'colvis',
          className: 'btn-primary',
          text: '<i class="fas fa-columns"></i> Wybierz kolumny',
          columns: ':gt(0)'
        },
        {
          extend: 'copy',
          text: '<i class="fas fa-copy"></i> <span class="d-none d-md-inline">Kopiuj</span>',
          className: 'btn-outline-dark btn-sm px-2 px-md-4',
          exportOptions: {
            columns: column_selector,
            format: {body: strip_tags_and_newlines}
          }
        },
        {
          extend: 'excel',
          text: '<i class="fas fa-file-excel"></i> <span class="d-none d-md-inline">Excel</span>',
          className: 'btn-outline-dark btn-sm px-2 px-md-4',
          exportOptions: {
            columns: column_selector,
            format: {body: strip_tags}
          }
        },
        {
          extend: 'pdf',
          text: '<i class="fas fa-file-pdf"></i> <span class="d-none d-md-inline">PDF</span>',
          className: 'btn-outline-dark btn-sm px-2 px-md-4',
          exportOptions: {
            columns: column_selector,
            format: {body: strip_tags}
          },
        },
        {
          extend: 'print',
          text: '<i class="fas fa-print"></i> <span class="d-none d-md-inline">Drukuj</span>',
          className: 'btn-outline-dark btn-sm px-2 px-md-4',
          exportOptions: {
            columns: column_selector,
            format: {body: strip_tags}
          }
        },
      ],
    },
    "language": datatables_Polish,
    "fnRowCallback" : function(nRow, aData, iDisplayIndex){
      $("td:first", nRow).html(iDisplayIndex +1);
      return nRow;
    },
    "pageLength": 50,
    "lengthMenu": [[10, 25, 50, 100, -1], [10, 25, 50, 100, "All"]],
    "stateSave": true,
    "stateSaveCallback": function(settings, data) {
      window.location.hash = '#' + Base64.encode(JSON.stringify(data));
    },
    "stateLoadCallback": function(settings) {
      const data = Base64.decode(window.location.hash.substring(1));
      return data ? JSON.parse(data) : null;
    },
    "searchPanes": {
      "show": false,
      "initCollapsed": true,
      "orderable": false,
      "clear": false,
      "layout": "columns-3",
    }
  };

  if (myConfig.vcardEnable) {
    config.buttons.buttons.push({
      text: '<i class="fas fa-address-book"></i> <span class="d-none d-md-inline">vCard</span>',
      className: 'btn-outline-dark btn-sm px-2 px-md-4',
      action: vcard_export,
      title: myConfig.vcardName,
    });
  }

  return config;
};
