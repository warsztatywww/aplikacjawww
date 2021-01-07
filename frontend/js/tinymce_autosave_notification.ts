import tinymce from "tinymce/tinymce";

/* Show a notification when an autosave exists for a TinyMCE editor */
tinymce.on('addeditor', function(event) {
  var editor = event.editor;
  editor.on('init', function(e) {
    var notification = null;
    if (editor.plugins.autosave.hasDraft()) {
      notification = editor.notificationManager.open({
        text: 'Możesz przywrócić swoje niezapisane zmiany wybierając "Plik > Przywróć ostatni szkic"',
        type: 'info'
      });
    }
    editor.on('RestoreDraft', function(e) {
      if (notification != null)
        notification.close();
    });
  });
}, true );