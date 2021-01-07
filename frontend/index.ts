// jQuery and Bootstrap3
import 'jquery';
import 'bootstrap/dist/css/bootstrap.css';
import 'bootstrap/dist/js/bootstrap.js';

// Header disappearing thing
import * as Headroom from 'headroom.js';
window['Headroom'] = Headroom;
import 'headroom.js/dist/jQuery.headroom.js';

// Select2 (type/category in workshop editor)
import 'select2';
import 'select2/dist/css/select2.css';
import './vendor/django_select2';

// DateTime picker
import 'moment';
moment.locale('pl');
import 'eonasdan-bootstrap-datetimepicker-npm/src/js/bootstrap-datetimepicker';
import 'eonasdan-bootstrap-datetimepicker-npm/build/css/bootstrap-datetimepicker.css';

// Main website CSS
import './css/site.css';
import './css/main.css';
import './css/bootstrap-theme.css';

// Main website JS
import './js/template.js';
import './js/ajax.requests.js';
import './js/warsztatywww.js';
import './js/datatables_config.js';
import './js/thing.js'; // ¯\_(ツ)_/¯