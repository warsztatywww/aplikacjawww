const gen_datatables_default_config = (table_selector) => {
  const column_selector = (idx, data, node) => {
	// https://datatables.net/forums/discussion/42192/exporting-data-with-buttons-and-responsive-extensions-controlled-by-column-visibility
	return $(table_selector).DataTable().column( idx ).visible();
  };
  return {
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
				const div = document.createElement("div");
				div.innerHTML = data;
				const percent = div.innerText;
			  if(type === 'export') {
				return percent;
			  } else {
				return parseFloat(percent.replace('%', ''));
			  }
			}
		  }
	  },
	  {
		targets: 'datatables-status',
		render: (data, type, row) => {
		  const isExport = type === 'export';
		  if(isExport || type === 'display') {
			if(data == 'Z')
			  return isExport ? 'Zakwalifikowany' : '<span class="qualified">Zakwalifikowany</span>';
			else if(data == "None")
			  return '';
			else if(data == 'O')
			  return isExport ? 'Odrzucony' : '<span class="not-qualified">Odrzucony</span>' ;
			else
			  return data;
		  } else
			return data;
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
	  "url": datatables_polish_locale_url,
	},
	"fnRowCallback" : function(nRow, aData, iDisplayIndex){
	  $("td:first", nRow).html(iDisplayIndex +1);
	  return nRow;
	},
	"pageLength": 50,
	"lengthMenu": [[10, 25, 50, 100, -1], [10, 25, 50, 100, "All"]],
  };
};
