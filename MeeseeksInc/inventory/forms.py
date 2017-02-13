from django import forms
from .models import Request
from .models import Item
from .models import Tag
 
class RequestForm(forms.ModelForm):
    item_field = forms.ModelChoiceField(queryset=Item.objects.all())
    class Meta:
        model = Request
        fields = ('item_field', 'request_quantity', 'reason')

class RequestSpecificForm(forms.Form):  
    quantity = forms.IntegerField()
    reason = forms.CharField(max_length=200)
    fields = ('quantity', 'reason')

       
class RequestEditForm(forms.ModelForm):
    class Meta:
        model = Request
        fields = ('request_quantity','reason')
  
class SearchForm(forms.Form):
    tags1 = forms.ModelMultipleChoiceField(queryset=Tag.objects.all(), required=False,widget=forms.CheckboxSelectMultiple, label="Tags to include")
    tags2 = forms.ModelMultipleChoiceField(queryset=Tag.objects.all(), required=False, widget=forms.CheckboxSelectMultiple,label="Tags to exclude")

    def __init__(self, tags, *args, **kwargs):
        super(SearchForm, self).__init__(*args, **kwargs)

        self.fields['tags1'] = forms.ModelMultipleChoiceField(queryset=Tag.objects.all(), required=False,widget=forms.CheckboxSelectMultiple, label="Tags to include")
        self.fields['tags2'] = forms.ModelMultipleChoiceField(queryset=Tag.objects.all(), required=False,widget=forms.CheckboxSelectMultiple, label="Tags to exclude")

    keyword = forms.CharField(required=False)
    model_number = forms.CharField(required=False)
    item_name = forms.CharField(required=False)
    fields = ('tags1','tags2','keyword','model_number','item_name')
    
