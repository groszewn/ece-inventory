import re

from dal import autocomplete
import dal_queryset_sequence
import dal_select2_queryset_sequence
from django import forms
from django.contrib.admindocs.tests.test_fields import CustomField
from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist

from inventory.models import Item, Disbursement, Item_Log, Custom_Field
from inventory.models import Request
from inventory.models import Tag


class DisburseForm(forms.ModelForm):
    user_field = forms.ModelChoiceField(queryset=User.objects.filter(is_staff="False")) #to disburse only to users
#     user_field = forms.ModelChoiceField(
#         queryset=User.objects.filter(is_staff="False"),
#         widget=autocomplete.ModelSelect2(url='custom_admin:userfield-autocomplete')
#     )
#     user_field = dal_queryset_sequence.fields.QuerySetSequenceModelField(
#         queryset=autocomplete.QuerySetSequence(
#             User.objects.filter(is_staff="False"),
#         ),
#         required=False,
#         widget=dal_select2_queryset_sequence.widgets.QuerySetSequenceSelect2('custom_admin:userfield-autocomplete'),
#     )
    item_field = forms.ModelChoiceField(queryset=Item.objects.all())
    total_quantity = forms.IntegerField(min_value=0)
    comment = forms.CharField(required=False)
    class Meta:
        model = Disbursement
        fields = ('user_field', 'item_field', 'total_quantity', 'comment')

class DisburseSpecificForm(forms.Form):
    user_field = forms.ModelChoiceField(queryset=User.objects.filter(is_staff="False")) #to disburse only to users
    total_quantity = forms.IntegerField(min_value=0)
    comment = forms.CharField(required=False)
    
    def __init__(self, *args, **kwargs):
        super(DisburseSpecificForm, self).__init__(*args, **kwargs)


class AddCommentRequestForm(forms.Form):
    comment = forms.CharField(label='Comments by admin (optional)', max_length=200, required=False)
    
class LogForm(forms.ModelForm):
    item_name = forms.ModelChoiceField(queryset=Item.objects.all())
    item_change_options = [
        ('Lost', 'Lost'),
        ('Broken', 'Broken'), 
        ('Acquired', 'Acquired')
        ]
    item_change_status = forms.ChoiceField(choices=item_change_options, required=True, widget=forms.Select)
    item_amount = forms.IntegerField(min_value=0)

    class Meta:
        model = Item_Log
        fields = ('item_name', 'item_change_status', 'item_amount')
    
class AdminRequestEditForm(forms.ModelForm):    
    comment = forms.CharField(label='Comments by Admin (optional)', max_length=200, required=False)
    class Meta:
        model = Request
        fields = ('request_quantity', 'reason','comment')

class RequestEditForm(forms.ModelForm):
    request_quantity = forms.IntegerField(min_value=1)
    class Meta:
        model = Request
        fields = ('request_quantity', 'reason')
         
class ItemEditForm(forms.ModelForm):
    def __init__(self, user, custom_fields, custom_values, *args, **kwargs):
        super(ItemEditForm, self).__init__(*args, **kwargs)
        if not user.is_superuser and user.is_staff:
            self.fields['quantity'].widget.attrs['readonly'] = True
            #quantity=forms.IntegerField(min_value=0, disabled=True, required=False)
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
    description = forms.CharField(required=False,widget=forms.Textarea)
    class Meta:
        model = Item
        fields = ('item_name', 'quantity', 'model_number', 'description')
        
class UserPermissionEditForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ('username', 'is_superuser', 'is_staff', 'is_active')
        
    def clean(self):
        cleaned_data = super(UserPermissionEditForm, self).clean()
        if cleaned_data['is_superuser']:
            cleaned_data['is_staff'] = True
        return cleaned_data
       
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
    description = forms.CharField(required=False,widget=forms.Textarea)
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
    username = forms.CharField(label='Username', max_length=30, required = True)
    email = forms.EmailField(label='Email', required = False)
    password1 = forms.CharField(label='Password',
                                widget=forms.PasswordInput(), required = True )
    password2 = forms.CharField(label='Confirm Password',
                                widget=forms.PasswordInput(), required = True )
    admin = forms.BooleanField(label = 'Is new user an Admin?',
                               widget = forms.CheckboxInput, required=False)
    staff = forms.BooleanField(label = 'Is new user a Staff?',
                               widget = forms.CheckboxInput, required=False)
    def clean_password2(self):
        if 'password1' in self.cleaned_data:
            password1 = self.cleaned_data['password1']
            password2 = self.cleaned_data['password2']
            if password1 == password2:
                return password2
            raise forms.ValidationError('Passwords do not match.')
    def clean_username(self):
        try:
            user = User.objects.get(username__iexact=self.cleaned_data['username'])
        except User.DoesNotExist:
            return self.cleaned_data['username']
        raise forms.ValidationError(("The username already exists. Please try another one."))
     
