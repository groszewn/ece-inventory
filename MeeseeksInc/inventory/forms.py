from django import forms
from .models import Request
from .models import Item
from .models import Tag
from inventory.models import ShoppingCartInstance
 
class RequestForm(forms.ModelForm):
    item_field = forms.ModelChoiceField(queryset=Item.objects.all())
    TYPES = (
        ( 'Dispersal','Dispersal'),
        ('Loan','Loan'),
    )
    type = forms.ChoiceField(label='Select the Request Type', choices=TYPES)
    request_quantity = forms.IntegerField(min_value=1)
    class Meta:
        model = Request
        fields = ('item_field', 'request_quantity','type','reason')
        
class RequestEditForm(forms.ModelForm):
    TYPES = (
        ( 'Dispersal','Dispersal'),
        ('Loan','Loan'),
    )
    type = forms.ChoiceField(label='Select the Request Type', choices=TYPES)
    request_quantity = forms.IntegerField(min_value=1)
    class Meta:
        model = Request
        fields = ('request_quantity','type','reason')

class RequestSpecificForm(forms.Form):  
    available_quantity = forms.IntegerField(disabled=True, required=False)
    quantity = forms.IntegerField(min_value=1)
    TYPES = (
        ( 'Dispersal','Dispersal'),
        ('Loan','Loan'),
    )
    type = forms.ChoiceField(label='Select the Request Type', choices=TYPES)
    reason = forms.CharField(max_length=200)
    def __init__(self, *args, **kwargs):
        super(RequestSpecificForm, self).__init__(*args, **kwargs)
        self.fields.keyOrder = ['available_quantity','quantity','type','reason']
      
class AddToCartForm(forms.Form):
    def __init__(self, *args, **kwargs):
        super(AddToCartForm, self).__init__(*args, **kwargs)
        self.fields['quantity'] = forms.IntegerField(required=True, min_value=1)
        TYPES = (
        ( 'Dispersal','Dispersal'),
        ('Loan','Loan'),
        )
        self.fields['type'] = forms.ChoiceField(label='Select the Request Type', choices=TYPES)
        self.fields['reason'] = forms.CharField(max_length=200) 
    fields =('quantity', 'type','reason')

class EditCartAndAddRequestForm(forms.ModelForm):
    quantity = forms.IntegerField(required=True, min_value=1)
    reason = forms.CharField(required=True)
    class Meta:
        model = ShoppingCartInstance
        fields = ('quantity','type','reason')

class SearchForm(forms.Form):
    tags1 = forms.ModelMultipleChoiceField(queryset=Tag.objects.all(), required=False,widget=forms.CheckboxSelectMultiple, label="Tags to include")
    tags2 = forms.ModelMultipleChoiceField(queryset=Tag.objects.all(), required=False, widget=forms.CheckboxSelectMultiple,label="Tags to exclude")

    def __init__(self, tags, *args, **kwargs):
        super(SearchForm, self).__init__(*args, **kwargs)

        self.fields['tags1'] = forms.ModelMultipleChoiceField(queryset=Tag.objects.all(), required=False,widget=forms.SelectMultiple(), label="Tags to include")
        self.fields['tags2'] = forms.ModelMultipleChoiceField(queryset=Tag.objects.all(), required=False,widget=forms.SelectMultiple(), label="Tags to exclude")

    keyword = forms.CharField(required=False)
    model_number = forms.CharField(required=False)
    item_name = forms.CharField(required=False)
    fields = ('tags1','tags2','keyword','model_number','item_name')
