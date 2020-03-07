const gen_datatables_config = (overwrites) => {
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
  return Object.assign({
    dom: 'Bfrtipl',
    responsive: true,
    colReorder: true,
    deferRender: true,
    createdRow: (row) => {
      $(row).find('[data-toggle="popover"]').popover();
    },
    columnDefs: [
      {
        targets: 'datatables-points',
        render: (data, type, row) => {
          if(type === 'display') {
            return data;
          } else {
            const percent = $("<div/>").html(data).text();
            if(type === 'export') {
              return percent;
            } else {
              // type is one of ['order', 'sort', 'type']
              return parseFloat(percent.replace('%', ''));
            }
          }
        }
      },
      {
        targets: 'datatables-status',
        render: (data, type, row) => {
          if(type === 'display')
            return data;
          else
            return $("<div/>").html(data).text();
        }
      },
      {
        targets: 'datatables-yes-no',
        render: (data, type, row) => {
          if(type === 'export') {
            return data.split("> ").pop();
          } else
            return data;
        }
      }
    ],
    buttons: [
      {
        extend: 'colvis',
        columns: ':gt(0)'
      },
      {
        extend: 'copy',
        exportOptions: {
          columns: column_selector,
          orthogonal: 'export'
        }
      },
      {
        extend: 'excel',
        exportOptions: {
          columns: column_selector,
          orthogonal: 'export'
        }
      },
      {
        extend: 'pdf',
        exportOptions: {
          columns: column_selector,
          orthogonal: 'export'
        },
       },
       {
        extend: 'print',
        exportOptions: {
          columns: column_selector,
          orthogonal: 'export'
        }
       },
    ],
    "language": {
      "url": datatables_locale_url,
    },
    "fnRowCallback" : function(nRow, aData, iDisplayIndex){
      $("td:first", nRow).html(iDisplayIndex +1);
      return nRow;
    },
    "pageLength": 50,
    "lengthMenu": [[10, 25, 50, 100, -1], [10, 25, 50, 100, "All"]],
  }, overwrites);
};
