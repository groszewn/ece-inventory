from django import forms
from .models import Request
from .models import Item
from .models import Tag
 
class RequestForm(forms.ModelForm):
    item_field = forms.ModelChoiceField(queryset=Item.objects.all())
    class Meta:
        model = Request
        fields = ('item_field', 'request_quantity', 'reason')
         
class RequestEditForm(forms.ModelForm):
    item_field = forms.ModelChoiceField(queryset=Item.objects.all())
    class Meta:
        model = Request
        fields = ('item_field', 'request_quantity', 'reason')
  
class SearchForm(forms.Form):
    choices = []
    for myTag in Tag.objects.all():
        if [myTag.tag,myTag.tag] not in choices:
            choices.append([myTag.tag,myTag.tag])
    tags = forms.MultipleChoiceField(choices, required=False, widget=forms.CheckboxSelectMultiple, label='Filter by tags...')
    keyword = forms.CharField(required=False)
    fields = ('tags','keyword')