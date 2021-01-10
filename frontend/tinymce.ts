// TinyMCE - loaded only on pages which require it
import tinymce from 'tinymce/tinymce';

import 'tinymce/icons/default';

import 'tinymce/themes/silver';
import 'tinymce/skins/ui/oxide/skin.css';

import 'tinymce/plugins/preview';
import 'tinymce/plugins/paste';
import 'tinymce/plugins/searchreplace';
import 'tinymce/plugins/autolink';
import 'tinymce/plugins/code';
import 'tinymce/plugins/visualblocks';
import 'tinymce/plugins/visualchars';
import 'tinymce/plugins/image';
import 'tinymce/plugins/link';
import 'tinymce/plugins/media';
import 'tinymce/plugins/codesample';
import 'tinymce/plugins/table';
import 'tinymce/plugins/charmap';
import 'tinymce/plugins/hr';
import 'tinymce/plugins/nonbreaking';
import 'tinymce/plugins/anchor';
import 'tinymce/plugins/toc';
import 'tinymce/plugins/advlist';
import 'tinymce/plugins/lists';
import 'tinymce/plugins/wordcount';
import 'tinymce/plugins/imagetools';
import 'tinymce/plugins/textpattern';
import 'tinymce/plugins/quickbars';
import 'tinymce/plugins/emoticons';
import 'tinymce/plugins/emoticons/js/emojis';
import 'tinymce/plugins/autosave';

import 'tinymce-i18n/langs5/pl';

/* Our custom 'autosave is available' dialog */
import './js/tinymce_autosave_notification.ts';

/* Make sure the style files are loaded from correct directory */
tinymce.baseURL += '/tinymce';

/* django_tinymce.js from django-tinymce (I don't want to load this file separately...) */
function initTinyMCE(el) {
  if (el.closest('.empty-form') === null) {  // Don't do empty inlines
    var mce_conf = JSON.parse(el.dataset.mceConf);

    // There is no way to pass a JavaScript function as an option
    // because all options are serialized as JSON.
    const fns = [
      'color_picker_callback',
      'file_browser_callback',
      'file_picker_callback',
      'images_dataimg_filter',
      'images_upload_handler',
      'paste_postprocess',
      'paste_preprocess',
      'setup',
      'urlconverter_callback',
    ];
    fns.forEach((fn_name) => {
      if (typeof mce_conf[fn_name] != 'undefined') {
        if (mce_conf[fn_name].includes('(')) {
          mce_conf[fn_name] = eval('(' + mce_conf[fn_name] + ')');
        }
        else {
          mce_conf[fn_name] = window[mce_conf[fn_name]];
        }
      }
    });

    const id = el.id;
    if ('elements' in mce_conf && mce_conf['mode'] == 'exact') {
      mce_conf['elements'] = id;
    }

    // <-- PATCHES for webpack packaging HERE -->
    /*if (el.dataset.mceGzConf) {
      tinyMCE_GZ.init(JSON.parse(el.dataset.mceGzConf));
    }
    if (!tinyMCE.editors[id]) {
      tinyMCE.init(mce_conf);
    }*/

    mce_conf['skin'] = false;

    if (!tinymce.editors[id]) {
      tinymce.init(mce_conf);
    }
  }
}

// Call function fn when the DOM is loaded and ready. If it is already
// loaded, call the function now.
// http://youmightnotneedjquery.com/#ready
function ready(fn) {
  if (document.readyState !== 'loading') {
    fn();
  } else {
    document.addEventListener('DOMContentLoaded', fn);
  }
}

ready(function() {
  // initialize the TinyMCE editors on load
  document.querySelectorAll('.tinymce').forEach(function(el) {
    initTinyMCE(el);
  });

  // initialize the TinyMCE editor after adding an inline
  document.body.addEventListener("click", function(ev) {
    if (!ev.target.parentNode ||
        !ev.target.parentNode.getAttribute("class") ||
        !ev.target.parentNode.getAttribute("class").includes("add-row")) {
      return;
    }
    const addRow = ev.target.parentNode;
    setTimeout(function() {  // We have to wait until the inline is added
      addRow.parentNode.querySelectorAll('textarea.tinymce').forEach(function(el) {
        initTinyMCE(el);
      });
    }, 0);
  }, true);
});