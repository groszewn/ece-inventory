from django import forms
from .models import Request
from .models import Item
from .models import Tag
from .models import UserQuery

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
    tags = forms.ModelMultipleChoiceField(queryset=Tag.objects.values_list('tag', flat=True).distinct(), required=False, widget=forms.CheckboxSelectMultiple, label='Filter by tags...')
    fields = ('tags',)