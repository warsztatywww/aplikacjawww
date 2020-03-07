const gen_datatables_config = (overwrites) => {
  const column_selector = (idx, data, node) => {
    // https://datatables.net/forums/discussion/42192/exporting-data-with-buttons-and-responsive-extensions-controlled-by-column-visibility
    if ($(node).hasClass('noVis')) {
      return false;
    }
    const tableID = $(node).closest('table').attr('id');
    return tableID === undefined? false : $(tableID).DataTable().column(idx).visible();
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
