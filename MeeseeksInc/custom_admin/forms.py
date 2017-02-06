from django import forms
from inventory.models import Request
from inventory.models import Item, Disbursement, Tag
import re
from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist
 
class DisburseForm(forms.ModelForm):
    user_field = forms.ModelChoiceField(queryset=User.objects.filter(is_staff="False")) #to disburse only to users
    item_field = forms.ModelChoiceField(queryset=Item.objects.all())
    class Meta:
        model = Disbursement
        fields = ('user_field', 'item_field', 'total_quantity', 'comment')

class AddCommentRequestForm(forms.Form):
    comment = forms.CharField(label='Comments by admin (optional)', max_length=200, required=False)
    

class RequestEditForm(forms.ModelForm):
    item_field = forms.ModelChoiceField(queryset=Item.objects.all())
    class Meta:
        model = Request
        fields = ('item_field', 'request_quantity', 'reason')
         
class ItemEditForm(forms.ModelForm):
    #item_name = forms.ModelChoiceField(queryset=Item.objects.all())
    choices = []
    for myTag in Tag.objects.all():
        if [myTag.tag,myTag.tag] not in choices:
            choices.append([myTag.tag,myTag.tag])
    tag_field = forms.MultipleChoiceField(choices, required=False, widget=forms.CheckboxSelectMultiple, label='Tags to include...')
    class Meta:
        model = Item
        fields = ('item_name', 'quantity', 'location', 'model_number', 'description','tag_field')
        
         
class CreateItemForm(forms.ModelForm):
    choices = []
    for myTag in Tag.objects.all():
        if [myTag.tag,myTag.tag] not in choices:
            choices.append([myTag.tag,myTag.tag])
    tag_field = forms.MultipleChoiceField(choices, required=False, widget=forms.CheckboxSelectMultiple, label='Tags to include...')
    new_tags = forms.CharField(required=False)
    class Meta:
        model = Item
        fields = ('item_name', 'quantity', 'location', 'model_number', 'description','tag_field')
     
 
class RegistrationForm(forms.Form):
    username = forms.CharField(label='Username', max_length=30)
    email = forms.EmailField(label='Email')
    password1 = forms.CharField(label='Password',
                                widget=forms.PasswordInput())
    password2 = forms.CharField(label='Confirm Password',
                                widget=forms.PasswordInput())
    admin = forms.BooleanField(label = 'Is new user an Admin?',
                               widget = forms.CheckboxInput, required=False)
    def clean_password2(self):
            if 'password1' in self.cleaned_data:
                password1 = self.cleaned_data['password1']
                password2 = self.cleaned_data['password2']
                if password1 == password2:
                    return password2
            raise forms.ValidationError('Passwords do not match.')
     
    def clean_username(self):
            username = self.cleaned_data['username']
            if not re.search(r'^\w+$', username):
                raise forms.ValidationError('Username can only contain alphanumeric characters and the underscore.')
            try:
                User.objects.get(username=username)
            except ObjectDoesNotExist:
                return username
            raise forms.ValidationError('Username is already taken.')
     
