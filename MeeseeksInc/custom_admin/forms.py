from django import forms
from inventory.models import Request
from inventory.models import Item, Disbursement, Item_Log, Custom_Field
from inventory.models import Tag
import re
from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist
from django.contrib.admindocs.tests.test_fields import CustomField
 
class DisburseForm(forms.ModelForm):
    user_field = forms.ModelChoiceField(queryset=User.objects.filter(is_staff="False")) #to disburse only to users
    item_field = forms.ModelChoiceField(queryset=Item.objects.all())
    total_quantity = forms.IntegerField(min_value=1)
    comment = forms.CharField(required=False)
    class Meta:
        model = Disbursement
        fields = ('user_field', 'item_field', 'total_quantity', 'comment')

class AddCommentRequestForm(forms.Form):
    comment = forms.CharField(label='Comments by admin (optional)', max_length=200, required=False)
    
class LogForm(forms.ModelForm):
    item_name = forms.ModelChoiceField(queryset=Item.objects.all())
    item_change_options = [
        (1, 'lost'),
        (2, 'acquired'), 
        (3, 'broken')
        ]
    item_change_status = forms.ChoiceField(choices=item_change_options, required=True, widget=forms.Select)
    class Meta:
        model = Item_Log
        fields = ('item_name', 'item_change_status', 'item_amount')
    
class AdminRequestEditForm(forms.ModelForm):    
    comment = forms.CharField(label='Comments by Admin (optional)', max_length=200, required=False)
    class Meta:
        model = Request
        fields = ('request_quantity', 'reason','comment')

class RequestEditForm(forms.ModelForm):
    item_field = forms.ModelChoiceField(queryset=Item.objects.all())
    request_quantity = forms.IntegerField(min_value=1)
    class Meta:
        model = Request
        fields = ('request_quantity', 'reason','comment')
         
class ItemEditForm(forms.ModelForm):
    def __init__(self, custom_fields, custom_values, *args, **kwargs):
        super(ItemEditForm, self).__init__(*args, **kwargs)
        for field in custom_fields:
            if field.field_type == 'Short':
                self.fields["%s" % field.field_name] = forms.CharField(required=False)                    
            if field.field_type == 'Long':
                self.fields["%s" % field.field_name] = forms.CharField(required=False,widget=forms.Textarea) 
            if field.field_type == 'Int':
                self.fields["%s" % field.field_name] = forms.IntegerField(required=False) 
            if field.field_type == 'Float':
                self.fields["%s" % field.field_name] = forms.FloatField(required=False)
            for val in custom_values:
                if val.field == field:
                    if field.field_type == 'Short':
                        self.fields["%s" % field.field_name] = forms.CharField(initial = val.field_value_short_text,required=False)                    
                    if field.field_type == 'Long':
                        self.fields["%s" % field.field_name] = forms.CharField(initial = val.field_value_long_text,widget=forms.Textarea,required=False) 
                    if field.field_type == 'Int':
                        self.fields["%s" % field.field_name] = forms.IntegerField(initial = val.field_value_integer,required=False) 
                    if field.field_type == 'Float':
                        self.fields["%s" % field.field_name] = forms.FloatField(initial = val.field_value_floating,required=False)
    quantity = forms.IntegerField(min_value=0)
    model_number = forms.CharField(required=False)
    description = forms.CharField(required=False)
    class Meta:
        model = Item
        fields = ('item_name', 'quantity', 'model_number', 'description')
        
class UserPermissionEditForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ('username', 'is_staff', 'is_active')
       
class AddTagForm(forms.Form):
    def __init__(self, tags, item_tags, *args, **kwargs):
        super(AddTagForm, self).__init__(*args, **kwargs)
        choices = []
        for myTag in tags:
            if [myTag.tag,myTag.tag] not in choices:
                choices.append([myTag.tag,myTag.tag])
        self.fields['tag_field'] = forms.MultipleChoiceField(choices, required=False, widget=forms.SelectMultiple(), label='Add new tags...')
        for tag in item_tags:
            self.fields["%s" % tag.tag] = forms.CharField(initial = tag.tag, label = "Edit existing tag")
        
    create_new_tags = forms.CharField(required=False)
    fields = ('tag_field','create_new_tags',)
         
class EditTagForm(forms.ModelForm):  
    class Meta:
        model = Tag 
        fields = ('tag',)
          
class CreateItemForm(forms.ModelForm):
    def __init__(self, tags, custom_fields, *args, **kwargs):
        super(CreateItemForm, self).__init__(*args, **kwargs)
        for field in custom_fields:
            if field.field_type == 'Short':
                self.fields["%s" % field.field_name] = forms.CharField(required=False)                    
            if field.field_type == 'Long':
                self.fields["%s" % field.field_name] = forms.CharField(required=False,widget=forms.Textarea) 
            if field.field_type == 'Int':
                self.fields["%s" % field.field_name] = forms.IntegerField(required=False) 
            if field.field_type == 'Float':
                self.fields["%s" % field.field_name] = forms.FloatField(required=False)
        choices = []
        for myTag in tags:
            if [myTag.tag,myTag.tag] not in choices:
                choices.append([myTag.tag,myTag.tag])
        self.fields['tag_field'] = forms.MultipleChoiceField(choices, required=False, widget=forms.SelectMultiple(), label='Tags to include...')
    
    new_tags = forms.CharField(required=False)
    location = forms.CharField(required=False)
    model_number = forms.CharField(required=False)
    description = forms.CharField(required=False)
    quantity = forms.IntegerField(min_value=0)
    class Meta:
        model = Item
        fields = ('item_name', 'quantity', 'model_number', 'description','new_tags',)

class CustomFieldForm(forms.ModelForm):  
    class Meta:
        model = Custom_Field
        fields = ('field_name','is_private','field_type',) 
        
class DeleteFieldForm(forms.Form):
    def __init__(self, fields, *args, **kwargs):
        super(DeleteFieldForm, self).__init__(*args, **kwargs)
        choices = []
        for field in fields:
            choices.append([field.field_name, field.field_name])
        self.fields['fields'] = forms.MultipleChoiceField(choices, required=False, widget=forms.CheckboxSelectMultiple(), label='Pick fields to delete...')
          
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
     
