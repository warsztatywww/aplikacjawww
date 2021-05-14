window.tinymce_local_file_picker = function(cb, value, meta) {
    // https://www.tiny.cloud/docs/demo/file-picker/
    var input = document.createElement('input');
    input.setAttribute('type', 'file');
    input.setAttribute('accept', 'image/*');
    input.onchange = function () {
        var file = this.files[0];

        var reader = new FileReader();
        reader.onload = function () {
            var id = 'blobid' + (new Date()).getTime();
            var blobCache =  tinymce.activeEditor.editorUpload.blobCache;
            var base64 = reader.result.split(',')[1];
            var blobInfo = blobCache.create(id, file, base64);
            blobCache.add(blobInfo);

            cb(blobInfo.blobUri(), { title: file.name });
        };
        reader.readAsDataURL(file);
    };
    input.click();
}

function send_points(row, save_btn) {
    var all_inputs = row.find(':input').not('button');
    var editable_inputs = all_inputs.filter(':not([type=hidden])');
    var saved_values = {};
    editable_inputs.each(function() {
        saved_values[$(this).attr('name')] = $(this).val();
    });
    var qualified_mark = row.find('.qualified-mark');

    var mark_changed = function () {
        save_btn.attr('disabled', false);
        save_btn.find(':first-child').removeClass('fa-cloud-upload-alt fa-check-circle').addClass('fa-save');
    };

    var mark_saving = function () {
        save_btn.attr('disabled', true);
        save_btn.find(':first-child').removeClass('fa-save fa-check-circle').addClass('fa-cloud-upload-alt');
    };

    var mark_saved = function () {
        save_btn.attr('disabled', true);
        save_btn.find(':first-child').removeClass('fa-save fa-cloud-upload-alt').addClass('fa-check-circle');
    };

    mark_saved();
    save_btn.click(function() {
        var data = {};
        all_inputs.each(function() {
            data[$(this).attr('name')] = $(this).val();
        });
        mark_saving();
        $.ajax({
            'url': '/savePoints/',
            'data': data,
            'error': function(xhr, textStatus, errorThrown) {
                mark_changed();
                alert('Błąd: ' + errorThrown);
            },
            'method': 'POST',
            'success': function(value) {
                if(value.error) {
                    mark_changed();
                    alert('Błąd:\n' + value.error);
                } else {
                    editable_inputs.each(function() {
                        saved_values[$(this).attr('name')] = value[$(this).attr('name')];
                        $(this).val(""); // For whatever reason, this is required to get the field to reformat with the correct comma. Don't ask.
                        $(this).val(saved_values[$(this).attr('name')]);
                    });
                    mark_saved();
                    qualified_mark.html(value.mark);
                }
            }
        });
    });

    editable_inputs.each(function() {
        $(this).on('change keyup mouseup', function () {
            if ($(this).val() != saved_values[$(this).attr('name')])
                mark_changed();
        });
    });
}

$('button.savePointsButton').each(function() {
    var save_btn = $(this);
    var row = $(save_btn.parents('tr'));
    send_points(row, save_btn);
});

window.handle_registration_change = function(workshop_name_txt, register) {
    var proper_url;
    if(register) {
        proper_url = $("#" + workshop_name_txt).data('register');
    } else {
        proper_url = $("#" + workshop_name_txt).data('unregister');
    }
    var no_workshop_card_header = $("#" + workshop_name_txt).find('.card-header').length === 0;

    function error(message) {
        var elem = $('<div class="alert alert-danger fade"><a href="#" class="close" data-dismiss="alert">&times;</a>' +
                     '<strong>Error!</strong> <span></span></div>');
        elem.find('span').text(message);
        $("#" + workshop_name_txt).after(elem); // add the error to the dom
        setTimeout(function() {
            elem.addClass('show');
        },10);
    }

    $.ajax({
        url : proper_url, // the endpoint
        type : "POST", // http method

        // handle a successful response
        success : function(json) {
            if (json.error) {
                error(json.error);
            }
            if (json.redirect) {
                window.location.href = json.redirect;
            }
            if (json.content) {
                $("#" + workshop_name_txt).replaceWith(json.content);
                if (no_workshop_card_header) {
                    $("#" + workshop_name_txt).find('.card-header').replaceWith('');
                    $("#" + workshop_name_txt).find('.button-div').removeClass('d-none d-md-block');
                    $("#" + workshop_name_txt).find('.solutions-button').removeClass('d-none d-md-inline-block');
                    $("#" + workshop_name_txt).find('.solutions-button').addClass('d-inline-block');
                }
                $("#" + workshop_name_txt).find('[data-toggle="tooltip"]').tooltip();
            }
        },
        error: function(xhr, errmsg, errcode) {
            error('Wystąpił problem przy wysyłaniu danych (' + xhr.status + ': ' + errcode + ').');
        }
    });
}

$(function () {
    $('[data-toggle="tooltip"]').tooltip();
    $('[data-toggle="popover"]').popover();

    // Automatically hide 'Saved successfully' alerts after 4 seconds
    $(".alert-auto-dismiss").delay(4000).fadeTo(500, 0).slideUp(500, function(){
        $(this).remove();
    });

    $('.dateinput').each(function (i, x) {
        var dates = null;
        if ($(x).data('start-date') && $(x).data('end-date')) {
            dates = [];
            for(var date = moment($(x).data('start-date')); date <= moment($(x).data('end-date')); date.add(1, 'days'))
                dates.push(date.toDate());
        }
        $(x).datetimepicker({
            format: 'L',
            locale: 'pl',
            defaultDate: $(x).data('default-date'),
            enabledDates: dates,
        });
    });

    // Facebook fix your sh*t (╯°□°)╯︵ ┻━┻
    function fixBrokenUnresponsiveFacebook() {
        $('iframe').each(function() {
            var url = $(this).attr('src');
            if (url.indexOf('facebook.com/plugins/page.php') === -1)
                return;
            if($(this).width() == 0 || $(this).height() == 0)
                return;
            url = url.replace(/width=([0-9]+)/, 'width=' + Math.round($(this).width()));
            url = url.replace(/height=([0-9]+)/, 'height=' + Math.round($(this).height()));
            if ($(this).attr('src') != url)
                $(this).attr('src', url);
        });
    }
    fixBrokenUnresponsiveFacebook();
    $(window).resize(fixBrokenUnresponsiveFacebook);

    // Make sure the year selector is always initially scrolled to the selected one
    function yearSelectorToCurrent() {
        var nav = $('nav.year-navigation');
        if (nav.length === 0)
            return;
        var selected = nav.find('.active');
        if (selected.length === 1)
            nav.scrollLeft(selected.offset().left - nav.offset().left + nav.scrollLeft() - (nav.width() - selected.width()) / 2);
    }
    yearSelectorToCurrent();
    $(window).resize(yearSelectorToCurrent);
});
