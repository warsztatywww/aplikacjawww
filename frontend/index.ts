// jQuery and Bootstrap4 and Font Awesome
import 'jquery';
import './css/custom-bootstrap.scss';
import 'bootstrap/dist/js/bootstrap.js';
import '@fortawesome/fontawesome-free/js/all';
import '@fortawesome/fontawesome-free/css/all.css';

// Select2 (type/category in workshop editor)
import 'select2';
import 'select2/dist/js/i18n/pl';
$.fn.select2.defaults.set("language", "pl");
//import 'select2/dist/css/select2.css';
import './vendor/django_select2';

// DateTime picker
import 'moment';
moment.locale('pl');
import 'eonasdan-bootstrap-datetimepicker/src/js/bootstrap-datetimepicker';
import 'eonasdan-bootstrap-datetimepicker/build/css/bootstrap-datetimepicker.css';

// Main website JS
import './js/ajax.requests.js';
import './js/warsztatywww.js';
import './js/datatables_config.js';
import './js/thing.js'; // ¯\_(ツ)_/¯
