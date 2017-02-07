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
    def __init__(self, tags, *args, **kwargs):
        super(SearchForm, self).__init__(*args, **kwargs)
        choices = []
        for myTag in tags:
            if [myTag.tag,myTag.tag] not in choices:
                choices.append([myTag.tag,myTag.tag])
        self.fields['tags1'] = forms.MultipleChoiceField(choices, required=False, widget=forms.CheckboxSelectMultiple, label='Tags to include...') 
        self.fields['tags2'] = forms.MultipleChoiceField(choices, required=False, widget=forms.CheckboxSelectMultiple, label='Tags to exclude...') 
        
    keyword = forms.CharField(required=False)
    model_number = forms.CharField(required=False)
    item_name = forms.CharField(required=False)
    fields = ('tags1','tags2','keyword','model_number','item_name')