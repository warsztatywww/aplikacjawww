// DataTables - loaded only on pages which require them
import 'datatables.net';
import 'datatables.net-bs4';
import 'datatables.net-bs4/css/dataTables.bootstrap4.css';
import 'datatables.net-buttons';
import 'datatables.net-buttons/js/buttons.colVis';
import 'datatables.net-buttons/js/buttons.html5';
import 'datatables.net-buttons/js/buttons.print';
import 'datatables.net-buttons-bs4';
import 'datatables.net-buttons-bs4/css/buttons.bootstrap4.css';
import 'datatables.net-colreorder';
import 'datatables.net-colreorder-bs4';
import 'datatables.net-colreorder-bs4/css/colReorder.bootstrap4.css';
import 'datatables.net-searchpanes';
import 'datatables.net-searchpanes-bs4';
import 'datatables.net-searchpanes-bs4/css/searchPanes.bootstrap4.css';
import 'datatables.net-select';
import 'datatables.net-select-bs4';
import 'datatables.net-select-bs4/css/select.bootstrap4.css';
import 'datatables.net-plugins/sorting/intl';

$.fn.dataTable.ext.order.intl('pl');

/********** LAZY LOADING PATCHES **********/
// A patch to lazy-load pdfmake
window['pdfMake'] = true;
const originalPdfHtml5Action = $.fn.dataTableExt.buttons.pdfHtml5.action;
$.fn.dataTableExt.buttons.pdfHtml5.action = function pdfHtml5Action(e, dt, button, config) {
    var _this = this;
    if (typeof window['pdfMake'] !== "object") {
        import('pdfmake/build/pdfmake').then(({ default: pdfMake }) => {
            import('pdfmake/build/vfs_fonts').then(({ default: pdfFonts }) => {
                pdfMake.vfs = pdfFonts.pdfMake.vfs;
                window['pdfMake'] = pdfMake;
                originalPdfHtml5Action.call(_this, e, dt, button, config);
            });
        });
    } else {
        originalPdfHtml5Action.call(_this, e, dt, button, config);
    }
};

// A patch to lazy-load JSZip (required for Excel exports)
window['JSZip'] = true;
const originalExcelHtml5Action = $.fn.dataTableExt.buttons.excelHtml5.action;
$.fn.dataTableExt.buttons.excelHtml5.action = function excelHtml5Action(e, dt, button, config) {
    var _this = this;
    if (typeof window['JSZip'] !== "object") {
        import('jszip').then(({ default: JSZip }) => {
            window['JSZip'] = JSZip;
            originalExcelHtml5Action.call(_this, e, dt, button, config);
        });
    } else {
        originalExcelHtml5Action.call(_this, e, dt, button, config);
    }
};
