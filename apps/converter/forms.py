from django import forms


class UploadForm(forms.Form):
    document = forms.FileField(
        label="Documento",
        widget=forms.ClearableFileInput(
            attrs={
                "class": (
                    "block w-full text-sm text-gray-600 file:mr-4 file:rounded-md file:border-0 "
                    "file:bg-indigo-50 file:px-4 file:py-2 file:text-sm file:font-medium "
                    "file:text-indigo-700 hover:file:bg-indigo-100"
                )
            }
        ),
    )
