from django import forms
from PIL import Image


class ImageFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True

    def validate(self, value):
        return super.validate(value)


class ImageFileField(forms.FileField):
    def clean(self, data, initial=None):
        if not data:
            return super().clean(data, initial)
        if isinstance(data, (list, tuple)):
            return [super(ImageFileField, self).clean(item, initial) for item in data]
        return [super().clean(data, initial)]


class ImageCreateForm(forms.Form):
    data = ImageFileField(widget=ImageFileInput(attrs={'multiple': True}))

    def clean(self):
        """ Validate files by checking they can be opened by PIL """
        # cleaned_data = super(ImageCreateForm, self).clean()
        image_files = self.files.getlist('data')
        invalid_images = []
        for img in image_files:
            try:
                with Image.open(img) as i:
                    i.verify()
            except (IOError, SyntaxError):
                invalid_images += [img]
        if invalid_images:
            image_names = [i._name for i in invalid_images]
            raise forms.ValidationError("Unable to add invalid images: {0}".format(image_names))
