from django import forms
from inventory.models import Request
from inventory.models import Item, Disbursement
from django.contrib.auth.models import User

class DisburseForm(forms.ModelForm):
    user_field = forms.ModelChoiceField(queryset=User.objects.filter(is_staff="False")) #to disburse only to users
    item_field = forms.ModelChoiceField(queryset=Item.objects.all())
    class Meta:
        model = Disbursement
        fields = ('user_field', 'item_field', 'total_quantity', 'comment')

class RequestEditForm(forms.ModelForm):
    item_field = forms.ModelChoiceField(queryset=Item.objects.all())
    class Meta:
        model = Request
        fields = ('item_field', 'request_quantity', 'reason')
        
class ItemEditForm(forms.ModelForm):
    #item_name = forms.ModelChoiceField(queryset=Item.objects.all())
    class Meta:
        model = Item
        fields = ('item_name', 'quantity', 'location', 'model_number', 'description')
        
class CreateItemForm(forms.ModelForm):
    class Meta:
        model = Item
        fields = ('item_name', 'quantity', 'location', 'model_number', 'description')
    
