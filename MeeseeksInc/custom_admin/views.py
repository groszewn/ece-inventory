from datetime import date, datetime, timedelta
from json.encoder import JSONEncoder
import pickle
from appdirs import unicode
from dal import autocomplete
from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.models import User
from django.contrib.messages.views import SuccessMessageMixin
from django.core import mail
from django.core.exceptions import ObjectDoesNotExist
from django.core.mail import EmailMessage
from django.db.models import F
from django.forms.formsets import formset_factory
from django.http import HttpResponseRedirect
from django.shortcuts import render, get_object_or_404, redirect,\
    render_to_response
from django.template.defaulttags import comment
from django.template.loader import render_to_string
from django.urls import reverse
from django.urls import reverse_lazy 
from django.utils import timezone
from django.views import generic
from django.views.generic.edit import FormView
import requests, json
from rest_framework.authtoken.models import Token

from custom_admin.forms import AssetsRequestForm, BaseAssetsRequestFormSet,\
    BaseAssetCheckInFormset, AssetEditForm, AddAssetsForm
from custom_admin.tasks import loan_reminder_email as task_email
from inventory.models import Asset, Request, Item, Disbursement, Tag, Log, Custom_Field, Custom_Field_Value, Loan, SubscribedUsers, EmailPrependValue, LoanReminderEmailBody, LoanSendDates, Asset_Custom_Field_Value
from .forms import ConvertLoanForm, UserPermissionEditForm, DisburseSpecificForm, CheckInLoanForm, EditLoanForm, EditTagForm, DisburseForm, ItemEditForm, CreateItemForm, RegistrationForm, AddCommentRequestForm, LogForm, AddTagForm, CustomFieldForm, DeleteFieldForm, SubscribeForm, ChangeEmailPrependForm, ChangeLoanReminderBodyForm, BackfillRequestForm, AddCommentBackfillForm, AddNotesBackfillForm, LogAssetDestruction
from django.core.exceptions import ObjectDoesNotExist

def staff_check(user):
    return user.is_staff

def admin_check(user):
    return user.is_superuser

def active_check(user):
    return user.is_active

def get_host(request):
    return 'http://' + request.META.get('HTTP_HOST')

class AdminIndexView(LoginRequiredMixin, UserPassesTestMixin, generic.ListView):  ## ListView to display a list of objects
    login_url = "/login/"
    template_name = 'custom_admin/index.html'
    context_object_name = 'instance_list'
    model = Tag
    def get_context_data(self, **kwargs):
        context = super(AdminIndexView, self).get_context_data(**kwargs)
        context['request_list'] = Request.objects.all()
        context['approved_request_list'] = Request.objects.filter(status="Approved")
        context['pending_request_list'] = Request.objects.filter(status="Pending")
        context['denied_request_list'] = Request.objects.filter(status="Denied")
        context['item_list'] = Item.objects.all()
        context['disbursed_list'] = Disbursement.objects.filter(admin_name=self.request.user.username)
        context['user_list'] = User.objects.all()
        context['loan_list'] = Loan.objects.all()
        context['current_user'] = self.request.user.username
        context['tags'] = Tag.objects.distinct('tag')
        if self.request.user.is_staff or self.request.user.is_superuser:
            context['custom_fields'] = Custom_Field.objects.filter(field_kind='Item') 
        else:
            context['custom_fields'] = Custom_Field.objects.filter(field_kind='Item',is_private=False)
        context['tags'] = Tag.objects.distinct('tag')
        return context
    
    def get_queryset(self):
        """Return the last five published questions."""
        return Asset.objects.order_by('item')[:5]

    def test_func(self):
        return self.request.user.is_staff

    
class LogView(LoginRequiredMixin, UserPassesTestMixin, generic.ListView):
    login_url='/login/'
    permission_required = 'is_staff'
    template_name = 'custom_admin/log.html'
    context_object_name = 'log_list'
    context_object_name = 'request_list'
    context_object_name = 'item_list'
    def get_context_data(self, **kwargs):
        context = super(LogView, self).get_context_data(**kwargs)
        context['log_list'] = Log.objects.all()
        request_lst = []
        item_lst = []
        for log in Log.objects.all():
            if log.nature_of_event == "Request" and Request.objects.filter(request_id=log.request_id).exists():
                request_lst.append(log.request_id)
            if Item.objects.filter(item_id=log.item_id).exists():
                item_lst.append(log.item_id)
        context['request_list'] = request_lst
        context['item_list'] = item_lst
        return context
        
    def get_queryset(self):
        return Log.objects.all()

    def log_item(request):
        form = LogForm(request.POST or None)
        if request.method=="POST":
            form = LogForm(request.POST)
            if form.is_valid():
                item = Item.objects.get(item_id=form['item_name'].value())
                change_type = form['item_change_status'].value()
                amount = int(form['item_amount'].value())
                if change_type == 'Acquired':  # this correlates to the item_change_option numbers for the tuples
                    item.quantity = F('quantity')+amount
                    Log.objects.create(request_id=None, item_id=item.item_id, item_name=item.item_name, initiating_user=request.user, nature_of_event="Acquire", 
                                       affected_user='', change_occurred="Acquired " + str(amount))
                    item.save()
                    messages.success(request, ('Successfully logged ' + str(item.item_name) + ' (added ' + str(amount) +')'))
                elif change_type == "Broken":
                    if item.quantity >= amount:
                        item.quantity = F('quantity')-amount
                        item.save()
                        Log.objects.create(request_id=None, item_id=item.item_id, item_name=item.item_name, initiating_user=request.user, nature_of_event="Broken", 
                                           affected_user='', change_occurred="Broke " + str(amount))
                        messages.success(request, ('Successfully logged ' + item.item_name + ' (removed ' + str(amount) +')'))
                    else:
                        messages.error(request, ("You can't break more of " + item.item_name + " than you have."))
                        return redirect(reverse('custom_admin:index'))
                elif change_type == "Lost":
                    if item.quantity >= amount:
                        item.quantity = F('quantity')-amount
                        item.save()
                        Log.objects.create(request_id=None, item_id=item.item_id, item_name=item.item_name, initiating_user=request.user, nature_of_event="Lost", 
                                           affected_user='', change_occurred="Lost " + str(amount))
                        messages.success(request, ('Successfully logged ' + item.item_name + ' (removed ' + str(amount) +')'))
                    else:
                        messages.error(request, ("You can't lose more of " + item.item_name + " than you have."))
                        return redirect(reverse('custom_admin:index'))
                form.save()
                return redirect('/customadmin')
            else:
                messages.error(request, ('Please enter a valid value in order to submit this form.'))
        return render(request, 'inventory/log_item.html', {'form': form})
    
    def log_asset(request, pk):
        asset = Asset.objects.get(asset_id=pk)
        item = Item.objects.get(item_id=asset.item.item_id)
        if request.method == "POST":
            form = LogAssetDestruction(request.POST or None)
            if form.is_valid():
                change_type = form['item_change_status'].value()
                if change_type == 'Broken':
                    Log.objects.create(request_id=None, item_id=item.item_id, item_name=item.item_name, initiating_user=request.user, nature_of_event="Broken", 
                                           affected_user='', change_occurred="Broke " + str(1))
                elif change_type == 'Lost':
                    Log.objects.create(request_id=None, item_id=item.item_id, item_name=item.item_name, initiating_user=request.user, nature_of_event="Lost", 
                                           affected_user='', change_occurred="Lost " + str(1))
                item.quantity -= 1
                item.save()
                asset.delete()
                messages.success(request, ('Successfully logged ' + item.item_name + ' (removed 1)'))
                return redirect(request.META.get('HTTP_REFERER'))
        else:
            form = LogAssetDestruction()
        return render(request, 'custom_admin/asset_destroy.html', {'form':form, 'pk':pk})
    def test_func(self):
        return self.request.user.is_staff

class AssetView(LoginRequiredMixin, UserPassesTestMixin, generic.ListView):
    login_url='/login/'
    permission_required = 'is_staff'
    
    def edit_asset(request, pk):
        asset = Asset.objects.get(asset_id=pk)
        orig_tag = asset.asset_tag
        asset_custom_fields = Custom_Field.objects.filter(field_kind='Asset')
        asset_custom_vals = Asset_Custom_Field_Value.objects.filter(asset=asset)
        if request.method == "POST":
            form = AssetEditForm(asset_custom_fields, asset_custom_vals, asset.asset_tag, request.POST)
            if form.is_valid():
                asset = Asset.objects.get(asset_id=pk)
                url = get_host(request) + '/api/asset/' + asset.asset_id + '/'
                payload = {}
                for field in asset_custom_fields:
                    if form[field.field_name].value():
                        payload[field.field_name] = form[field.field_name].value()
                    else:
                        payload[field.field_name] = ''
                if form['asset_tag'].value():
                    payload['asset_tag'] = form['asset_tag'].value() 
                header = get_header(request)
                if Asset.objects.filter(asset_tag=form['asset_tag'].value()).exists() and form['asset_tag'].value() != orig_tag:
                        messages.error(request, ('An asset with that asset tag already exists. That change could not be saved.'))
                if form['asset_tag'].value() is '':
                        messages.error(request, ('Asset tags cannot be blank. That change could not be saved.'))
                response = requests.put(url, headers = header, data=json.dumps(payload))
                if response.status_code == 200:
                    messages.success(request, ('Successfully edited asset with tag: ' + asset.asset_tag + ' (' + asset.asset_id + ').')) 
                else:
                    messages.error(request, ('Failed to edit asset with tag: ' + asset.asset_tag + ' (' + asset.asset_id + ')'))
                return redirect(request.META.get('HTTP_REFERER'))
        else:
            form = AssetEditForm(asset_custom_fields, asset_custom_vals, asset.asset_tag) 
        return render(request, 'custom_admin/edit_asset_inner.html', {'form': form, 'pk':pk, 'asset_tag':asset.asset_tag, 'item_name':asset.item.item_name})
            
    def delete_asset(request, pk):
        asset = Asset.objects.get(asset_id=pk)
        url = get_host(request) + '/api/asset/' + asset.asset_id + '/'
        header = get_header(request)
        response = requests.delete(url, headers = header)
        if response.status_code == 204:
            messages.success(request, ('Successfully deleted asset: ' + pk ))
        else:
            messages.error(request, ('Failed to delete asset: ' + pk ))
        return redirect(request.META.get('HTTP_REFERER'))     
    
    def delete_asset_from_detail(request, pk):
        asset = Asset.objects.get(asset_id=pk)
        asset_item_id = asset.item.item_id
        AssetView.delete_asset(request,pk)
        return redirect('/item/' + asset_item_id) 
    
    def add_assets(request, pk): 
        if request.method == "POST":
            form = AddAssetsForm(request.POST)
            if form.is_valid():
                item = Item.objects.get(item_id=pk)
                if item.is_asset:
                    user = request.user
                    token, create = Token.objects.get_or_create(user=user)
                    http_host = get_host(request)
                    url=http_host+'/api/add/assets/'+item.item_id+'/'
                    payload = {'num_assets':form['num_assets'].value()}
                    header = {'Authorization': 'Token '+ str(token), 
                              "Accept": "application/json", "Content-type":"application/json"}
                    requests.post(url, headers = header, data=json.dumps(payload))
                return redirect(request.META.get('HTTP_REFERER')) 
        else:
            form = AddAssetsForm() 
        return render(request, 'custom_admin/add_assets_inner.html', {'form': form, 'pk':pk})

def make_loan_checkin_asset_form(loan):
    queryset = Asset.objects.filter(loan=loan)
    class CheckInLoanAssetForm(forms.Form):
        asset_id = forms.ModelChoiceField(queryset=queryset, label='Asset')
        class Meta:
            model = Asset
            exclude = ('item','loan','disbursement')
    return CheckInLoanAssetForm

def obj_dict(obj):
    return obj.__dict__    
    
class LoanView(LoginRequiredMixin, UserPassesTestMixin, generic.ListView):
    login_url='/login/'
    permission_required = 'is_staff'
    def convert_loan(request, pk): #redirect to main if deleted
        loan = Loan.objects.get(loan_id=pk)
        loan_orig_quantity = loan.total_quantity
        if request.method == "POST":
            form = ConvertLoanForm(loan.total_quantity, request.POST)
            if form.is_valid():
                url = get_host(request) + '/api/loan/convert/' + loan.loan_id + '/'
                payload = {'number_to_convert':form['items_to_convert'].value()}
                header = get_header(request)
                response = requests.post(url, headers = header, data=json.dumps(payload))
                if response.status_code == 200:
                    messages.success(request, ('Converted ' + form['items_to_convert'].value() + ' from loan of ' + loan.item_name.item_name + ' to disbursement. (' + loan.user_name +')'))
                else:
                    messages.error(request, ('Failed to convert ' + form['items_to_convert'].value() + ' from loan of ' + loan.item_name.item_name + ' to disbursement. (' + loan.user_name +')'))
                if loan_orig_quantity - int(form['items_to_convert'].value()) <= 0:
                    return redirect('/customadmin')
                return redirect(request.META.get('HTTP_REFERER')) 
        else:
            form = ConvertLoanForm(loan.total_quantity) 
        return render(request, 'custom_admin/convert_loan_inner.html', {'form': form, 'pk':pk, 'num_loaned' : loan.total_quantity, 'item_name':loan.item_name.item_name})    
    
    def convert_loan_with_assets(request, pk): #redirect to main if deleted
        loan = Loan.objects.get(loan_id=pk)
        ConvertLoanAssetForm = make_loan_checkin_asset_form(loan)
        ConvertLoanAssetFormset = formset_factory(ConvertLoanAssetForm, extra=loan.total_quantity, formset=BaseAssetCheckInFormset)
        if request.method == "POST":
            formset = ConvertLoanAssetFormset(request.POST)
            if formset.is_valid():
                token, create = Token.objects.get_or_create(user=request.user)
                http_host = get_host(request)
                url=http_host+'/api/loan/convert_with_assets/'+pk+'/'
                asset_ids = []
                for form in formset:
                    asset_ids.append(form['asset_id'].value())
                payload = {'asset_ids': asset_ids}
                header = {'Authorization': 'Token '+ str(token), 
                          "Accept": "application/json", "Content-type":"application/json"}
                requests.post(url, headers = header, data = json.dumps(payload, default=obj_dict))
                messages.success(request, ('Converted ' + str(len([x for x in asset_ids if x])) + ' from loan of ' + loan.item_name.item_name + ' to disbursement. (' + loan.user_name +')'))
                return redirect(reverse('custom_admin:index'))
            else:
                form_errors = formset.non_form_errors()
                return render(request, 'custom_admin/convert_loan_with_asset_inner.html', {'formset': formset, 'pk':pk, 'num_loaned':loan.total_quantity, 'item_name':loan.item_name, 'form_errors':form_errors})
        else:
            formset = ConvertLoanAssetFormset()
        return render(request, 'custom_admin/convert_loan_with_asset_inner.html', {'formset': formset, 'pk':pk, 'num_loaned':loan.total_quantity, 'item_name':loan.item_name})
 
    def check_in_loan(request, pk):
        loan = Loan.objects.get(loan_id=pk)
        if request.method == "POST":
            loan = Loan.objects.get(loan_id=pk)
            loan_orig_quantity = loan.total_quantity
            form = CheckInLoanForm(loan.total_quantity, request.POST) 
            if form.is_valid():
                item = loan.item_name
                items_checked_in = form['items_to_check_in'].value()
                user = request.user
                token, create = Token.objects.get_or_create(user=user)
                http_host = get_host(request)
                url=http_host+'/api/loan/checkin/'+pk+'/'
                payload = {'check_in':int(items_checked_in), 'total_quantity': loan.total_quantity, 'comment':loan.comment}
                header = {'Authorization': 'Token '+ str(token), 
                      "Accept": "application/json", "Content-type":"application/json"}
                requests.post(url, headers = header, data = json.dumps(payload))
                messages.success(request, ('Successfully checked in ' + items_checked_in + ' ' + item.item_name + '.'))
                if loan_orig_quantity - int(form['items_to_check_in'].value()) <= 0:
                    return redirect('/customadmin')
                return redirect(request.META.get('HTTP_REFERER'))
        else:
            form = CheckInLoanForm(loan.total_quantity) # blank request form with no data yet
        return render(request, 'custom_admin/loan_check_in_inner.html', {'form': form, 'pk':pk, 'num_loaned' : loan.total_quantity, 'item_name':loan.item_name.item_name})   
    def check_in_loan_with_assets(request,pk):
        loan = Loan.objects.get(loan_id=pk)
        CheckInLoanAssetForm = make_loan_checkin_asset_form(loan)
        CheckInLoanAssetFormset = formset_factory(CheckInLoanAssetForm, extra=loan.total_quantity, formset=BaseAssetCheckInFormset)
        if request.method == "POST":
            formset = CheckInLoanAssetFormset(request.POST)
            if formset.is_valid():
                token, create = Token.objects.get_or_create(user=request.user)
                http_host = get_host(request)
                url=http_host+'/api/loan/checkin_with_assets/'+pk+'/'
                asset_ids = []
                for form in formset:
                    asset_ids.append(form['asset_id'].value())
                payload = {'asset_ids': asset_ids}
                header = {'Authorization': 'Token '+ str(token), 
                          "Accept": "application/json", "Content-type":"application/json"}
                requests.post(url, headers = header, data = json.dumps(payload, default=obj_dict))
                messages.success(request, ('Successfully checked-in ' + str(len([x for x in asset_ids if x])) + ' ' + loan.item_name.item_name))
                return redirect(reverse('custom_admin:index'))
            else:
                form_errors = formset.non_form_errors()
                return render(request, 'custom_admin/loan_check_in_assets_inner.html', {'formset': formset, 'pk':pk, 'num_loaned':loan.total_quantity, 'item_name':loan.item_name, 'form_errors':form_errors})
        else:
            formset = CheckInLoanAssetFormset()
        return render(request, 'custom_admin/loan_check_in_assets_inner.html', {'formset': formset, 'pk':pk, 'num_loaned':loan.total_quantity, 'item_name':loan.item_name})

    def edit_loan(request, pk):
        loan = Loan.objects.get(loan_id=pk)
        if request.method == "POST":
            form = EditLoanForm(request.POST, instance=loan) 
            if form.is_valid():
                post = form.save(commit=False)
                user = request.user
                token, create = Token.objects.get_or_create(user=user)
                http_host = get_host(request)
                url=http_host+'/api/loan/update/'+loan.loan_id+'/'
                payload = {'comment': post.comment,'total_quantity':post.total_quantity}
                header = {'Authorization': 'Token '+ str(token), 
                      "Accept": "application/json", "Content-type":"application/json"}
                response = requests.put(url, headers = header, data=json.dumps(payload))
                if response.status_code == 400:
                    messages.error(request, ('You cannot loan more items than the quantity available.'))
                    return redirect(request.META.get('HTTP_REFERER'))
                messages.success(request, ('Successfully edited loan for ' + loan.item_name.item_name + '.'))
                return redirect(request.META.get('HTTP_REFERER'))
        else:
            form = EditLoanForm(instance=loan) # blank request form with no data yet
        return render(request, 'custom_admin/edit_loan_inner.html', {'form': form, 'pk':pk, 'num_left':loan.item_name.quantity, 'item_name':loan.item_name.item_name, 'is_asset':loan.item_name.is_asset})      
    def test_func(self):
        return self.request.user.is_staff

def make_disburse_asset_form(item):
    queryset = Asset.objects.filter(item=item)
    class DisburseAssetForm(forms.Form):
        asset_id = forms.ModelChoiceField(queryset=queryset, label='Asset')
        class Meta:
            model = Asset
            exclude = ('item','loan','disbursement')
    return DisburseAssetForm

class DisbursementView(LoginRequiredMixin, UserPassesTestMixin):
    login_url='/login/'
    permission_required = 'is_staff'
    def post_new_disburse(request):
        if request.method == "POST":
            form = DisburseForm(request.POST) # create request-form with the data from the request        
            if form.is_valid():
                item = Item.objects.get(item_id=form['item_field']).value()
                user = request.user
                token, create = Token.objects.get_or_create(user=user)
                http_host = get_host(request)
                url=http_host+'/api/disbursements/direct/'+item.item_id+'/'
                payload = {'total_quantity':int(form['total_quantity'].value()), 
                       'comment':form['comment'].value(), 'type':form['type'].value()}
                header = {'Authorization': 'Token '+ str(token), 
                          "Accept": "application/json", "Content-type":"application/json"}
                requests.post(url, headers = header, data=json.dumps(payload))
                if item.quantity < int(form['total_quantity'].value()):
                    messages.error(request, ('Not enough stock available for ' + item.item_name + ' (' + User.objects.get(id=form['user_field'].value()).username +')'))
                    return redirect(reverse('custom_admin:index'))
                messages.success(request, 
                                 ('Successfully disbursed ' + form['total_quantity'].value() + " " + item.item_name + ' (' + User.objects.get(id=form['user_field'].value()).username +')'))
                return redirect('/customadmin')
        else:
            form = DisburseForm() # blank request form with no data yet
        return render(request, 'custom_admin/single_disburse_inner.html', {'form': form})   

    def post_new_disburse_specific(request, pk):
        item = Item.objects.get(item_id=pk)
        if request.method == "POST":
            form = DisburseSpecificForm(request.POST) # create request-form with the data from the request
            if form.is_valid():
                user_name = User.objects.get(id=form['user_field'].value()).username
                item = Item.objects.get(item_id=pk)
                user = request.user
                token, create = Token.objects.get_or_create(user=user)
                http_host = get_host(request)
                url=http_host+'/api/disbursements/direct/'+item.item_id+'/'
                payload = {'admin_name': user.username,'user_name':user_name, 
                           'item_name':item.item_name, 'total_quantity':int(form['total_quantity'].value()), 
                           'comment':form['comment'].value(),'type':form['type'].value()}
                header = {'Authorization': 'Token '+ str(token), 
                          "Accept": "application/json", "Content-type":"application/json"}
                requests.post(url, headers = header, data=json.dumps(payload))
                if item.quantity >= int(form['total_quantity'].value()):
                    if form['type'].value() == "Loan":
                        messages.success(request, "Directly disbursed " + item.item_name + " as loan.")
                    if form['type'].value() == "Dispersal":
                        messages.success(request, "Directly disbursed " + item.item_name + " as dispersal.")
                else:
                    messages.error(request, ('Not enough stock available for ' + item.item_name + ' (' + User.objects.get(id=form['user_field'].value()).username +')'))
                    return redirect(reverse('custom_admin:index'))
                
                return redirect('/item/'+pk)
        else:
            form = DisburseSpecificForm() # blank request form with no data yet
        return render(request, 'custom_admin/specific_disburse_inner.html', {'form': form, 'pk':pk, 'amount_left':item.quantity, 'item_name':item.item_name})
    
    def post_new_disburse_asset(request, pk):
        DisburseAssetForm = make_disburse_asset_form(Item.objects.get(item_id=pk))
#             form = DisburseAssetForm(request.POST, extra=request.POST.get('extra_field_count'))
        DisburseAssetFormSet = formset_factory(DisburseAssetForm, extra=1, formset=BaseAssetCheckInFormset)
        if request.method == 'POST':
            formset = DisburseAssetFormSet(request.POST)
            if formset.is_valid():
                token, create = Token.objects.get_or_create(user=request.user)
                http_host = get_host(request)
                url=http_host+'/api/loan/convert_with_assets/'+pk+'/'
                asset_ids = []
                for form in formset:
                    asset_ids.append(form['asset_id'].value())
                print(asset_ids)
                payload = {'asset_ids': asset_ids}
                header = {'Authorization': 'Token '+ str(token), 
                          "Accept": "application/json", "Content-type":"application/json"}
#                 requests.post(url, headers = header, data = json.dumps(payload, default=obj_dict))
                return redirect(request.META.get('HTTP_REFERER'))  
        else:
            formset = DisburseAssetFormSet()
#             form = make_disburse_asset_form(Item.objects.get(item_id=pk))
        return render(request, "custom_admin/direct_disbursements_with_assets_inner.html", { 'formset': formset, 'pk':pk})
    
    def test_func(self):
        return self.request.user.is_staff

def make_asset_request_form(item):
    queryset = Asset.objects.exclude(loan__isnull=False).exclude(disbursement__isnull=False).filter(item=item)
    print(queryset)
    class AssetsRequestForm(forms.ModelForm):
        asset_id = forms.ModelChoiceField(queryset=queryset, label='Asset')
        class Meta:
            model = Asset
            exclude = ('item','loan','disbursement', 'asset_tag')
    return AssetsRequestForm
    
@login_required(login_url='/login/')
@user_passes_test(staff_check, login_url='/login/')
def request_accept_with_assets(request, pk):
    indiv_request = Request.objects.get(request_id=pk)
    AssetsRequestForm = make_asset_request_form(indiv_request.item_name)
    AssetsRequestFormset = formset_factory(AssetsRequestForm, extra=indiv_request.request_quantity, formset=BaseAssetsRequestFormSet)
    if request.method == "POST":
        formset = AssetsRequestFormset(request.POST)
        commentForm = AddCommentRequestForm(request.POST, instance=indiv_request)
        if all([commentForm.is_valid(), formset.is_valid()]):
            indiv_request.type = commentForm['type'].value()
            indiv_request.save()
            comment = commentForm['comment'].value()
            token, create = Token.objects.get_or_create(user=request.user)
            http_host = get_host(request)
            url=http_host+'/api/requests/approve_with_assets/'+pk+'/'
            asset_ids = []
            for form in formset:
                asset_ids.append(form['asset_id'].value())
            payload = {'comment':comment, 'asset_ids': asset_ids}
            header = {'Authorization': 'Token '+ str(token), 
                      "Accept": "application/json", "Content-type":"application/json"}
            requests.put(url, headers = header, data = json.dumps(payload, default=obj_dict))
            if indiv_request.type == "Dispersal": 
                messages.success(request, ('Successfully disbursed assets of ' + indiv_request.item_name.item_name + ' (' + indiv_request.user_id +')'))
            elif indiv_request.type == "Loan":
                messages.success(request, ('Successfully loaned assets of ' + indiv_request.item_name.item_name + ' (' + indiv_request.user_id +')'))
            return redirect(reverse('custom_admin:index'))
        else:
            form_errors = formset.non_form_errors()
            return render(request, 'custom_admin/request_accept_with_asset_inner.html', {'commentForm': commentForm, 'formset': formset, 'pk':pk, 'num_requested':indiv_request.request_quantity, 'num_available':Item.objects.get(item_name=indiv_request.item_name).quantity, 'item_name':indiv_request.item_name.item_name, 'form_errors':form_errors})
    else:
        commentForm = AddCommentRequestForm(instance=indiv_request)
        formset = AssetsRequestFormset()
    return render(request, 'custom_admin/request_accept_with_asset_inner.html', {'commentForm': commentForm, 'formset': formset, 'pk':pk, 'num_requested':indiv_request.request_quantity, 'num_available':Item.objects.get(item_name=indiv_request.item_name).quantity, 'item_name':indiv_request.item_name.item_name})

    
class RequestsView(LoginRequiredMixin, UserPassesTestMixin):
    login_url='/login/'
    permission_required = 'is_staff'
    def approve_all_requests(request):
        pending_requests = Request.objects.filter(status="Pending")
        if not pending_requests:
            messages.error(request, ('No requests to accept!'))
            return redirect(reverse('custom_admin:index'))
        for indiv_request in pending_requests:
            item = get_object_or_404(Item,item_name=indiv_request.item_name.item_name)
            user = request.user
            token, create = Token.objects.get_or_create(user=user)
            http_host = get_host(request)
            url=http_host+'/api/requests/approve/'+indiv_request.request_id+'/'
            payload = {'comment':""}
            header = {'Authorization': 'Token '+ str(token), 
                      "Accept": "application/json", "Content-type":"application/json"}
            requests.put(url, headers = header, data = json.dumps(payload))
            if item.quantity >= indiv_request.request_quantity:
                if indiv_request.type == "Dispersal":
                    messages.add_message(request, messages.SUCCESS, 
                                     ('Successfully disbursed ' + indiv_request.item_name.item_name + ' (' + indiv_request.user_id +')'))
                if indiv_request.type == "Loan":
                    messages.add_message(request, messages.SUCCESS, 
                                     ('Successfully loaned ' + indiv_request.item_name.item_name + ' (' + indiv_request.user_id +')'))
            else:
                messages.add_message(request, messages.ERROR, 
                                     ('Not enough stock available for ' + indiv_request.item_name.item_name + ' (' + indiv_request.user_id +')'))    
        return redirect(reverse('custom_admin:index'))

    def deny_request(request, pk):
        user = request.user
        token, create = Token.objects.get_or_create(user=user)
        http_host = get_host(request)
        url=http_host+'/api/requests/deny/'+pk+'/'
        payload = {'comment':''}
        header = {'Authorization': 'Token '+ str(token), 
                  "Accept": "application/json", "Content-type":"application/json"}
        requests.put(url, headers = header, data = json.dumps(payload))
        messages.success(request, ('Denied disbursement ' + indiv_request.item_name.item_name + ' (' + indiv_request.user_id +')'))
        return redirect(reverse('custom_admin:index'))
     
    def deny_all_request(request):
        pending_requests = Request.objects.filter(status="Pending")
        if not pending_requests:
            messages.error(request, ('No requests to deny!'))
            return redirect(reverse('custom_admin:index'))
        for indiv_request in pending_requests:
            user = request.user
            token, create = Token.objects.get_or_create(user=user)
            http_host = get_host(request)
            url=http_host+'/api/requests/deny/'+indiv_request.request_id+'/'
            payload = {'comment':''}
            header = {'Authorization': 'Token '+ str(token), 
                      "Accept": "application/json", "Content-type":"application/json"}
            requests.put(url, headers = header, data = json.dumps(payload))
        messages.success(request, ('Denied all pending requests.'))
        return redirect(reverse('custom_admin:index'))
    
    def approve_request(request, pk):
        indiv_request = Request.objects.get(request_id=pk)
        item = Item.objects.get(item_id=indiv_request.item_name_id)
        if item.quantity >= indiv_request.request_quantity:
            token, create = Token.objects.get_or_create(user=user)
            http_host = get_host(request)
            url=http_host+'/api/requests/approve/'+item.item_id+'/'
            payload = {'comment':""}
            header = {'Authorization': 'Token '+ str(token), 
                      "Accept": "application/json", "Content-type":"application/json"}
            requests.put(url, headers = header, data = json.dumps(payload))
            messages.success(request, ('Successfully disbursed ' + indiv_request.item_name.item_name + ' (' + indiv_request.user_id +')'))
        else:
            messages.error(request, ('Not enough stock available for ' + indiv_request.item_name.item_name + ' (' + indiv_request.user_id +')'))
            return redirect(reverse('custom_admin:index'))
     
        return redirect(reverse('custom_admin:index'))
    def add_comment_to_request_deny(request, pk):
        indiv_request = Request.objects.get(request_id=pk)
        if request.method == "POST":
            form = AddCommentRequestForm(request.POST) # create request-form with the data from the request
            if form.is_valid():
                comment = form['comment'].value()
                user = request.user
                token, create = Token.objects.get_or_create(user=user)
                http_host = get_host(request)
                url=http_host+'/api/requests/deny/'+pk+'/'
                payload = {'comment':comment}
                header = {'Authorization': 'Token '+ str(token), 
                      "Accept": "application/json", "Content-type":"application/json"}
                requests.put(url, headers = header, data = json.dumps(payload))
                indiv_request = Request.objects.get(request_id=pk)
                messages.success(request, ('Denied disbursement ' + indiv_request.item_name.item_name + ' (' + indiv_request.user_id +')'))
                if "request_detail" in request.META.get('HTTP_REFERER'):
                    return redirect(reverse('custom_admin:index'))
                return redirect(request.META.get('HTTP_REFERER')) 
        else:
            form = AddCommentRequestForm() # blank request form with no data yet
        return render(request, 'custom_admin/request_deny_comment_inner.html', {'form': form, 'pk':pk, 'num_requested':indiv_request.request_quantity, 'num_available':Item.objects.get(item_name=indiv_request.item_name).quantity, 'item_name':indiv_request.item_name.item_name})    
    def add_comment_to_request_accept(request, pk):
        indiv_request = Request.objects.get(request_id=pk)
        if request.method == "POST":
            form = AddCommentRequestForm(request.POST, instance=indiv_request) # create request-form with the data from the request
            if form.is_valid():
                indiv_request = Request.objects.get(request_id=pk)
                item = Item.objects.get(item_name=indiv_request.item_name)
                if item.quantity >= indiv_request.request_quantity:
                    comment = form['comment'].value()
                    indiv_request.type = form['type'].value()
                    indiv_request.save()
                    item = Item.objects.get(item_name=indiv_request.item_name)
                    user = request.user
                    token, create = Token.objects.get_or_create(user=user)
                    http_host = get_host(request)
                    url=http_host+'/api/requests/approve/'+pk+'/'
                    payload = {'comment':comment}
                    header = {'Authorization': 'Token '+ str(token), 
                          "Accept": "application/json", "Content-type":"application/json"}
                    requests.put(url, headers = header, data = json.dumps(payload))
                    if indiv_request.type == "Dispersal": 
                        messages.success(request, ('Successfully disbursed ' + indiv_request.item_name.item_name + ' (' + indiv_request.user_id +')'))
                    elif indiv_request.type == "Loan":
                        messages.success(request, ('Successfully loaned ' + indiv_request.item_name.item_name + ' (' + indiv_request.user_id +')'))
                else:
                    messages.error(request, ('Not enough ' + indiv_request.item_name.item_name + ' remaining to approve this request.'))
            if "request_detail" in request.META.get('HTTP_REFERER'):
                return redirect(reverse('custom_admin:index'))
            return redirect(request.META.get('HTTP_REFERER'))  
        else:
            form = AddCommentRequestForm(instance=indiv_request) # blank request form with no data yet
        return render(request, 'custom_admin/request_accept_comment_inner.html', {'form': form, 'pk':pk, 'num_requested':indiv_request.request_quantity, 'num_available':Item.objects.get(item_name=indiv_request.item_name).quantity, 'item_name':indiv_request.item_name.item_name})
    def test_func(self):
        return self.request.user.is_superuser
    
class CustomFieldView(LoginRequiredMixin, UserPassesTestMixin, FormView): 
    login_url='/login/'
    permission_required = 'is_superuser'
    form_class = CustomFieldForm
    success_url = '/customadmin/'
    template_name = 'custom_admin/create_custom_field.html'
    
    def form_valid(self, form):
        field_name = form['field_name'].value()
        field_type = form['field_type'].value()
        is_private = form['is_private'].value()
        field_for = form['field_kind'].value()
        if field_for == "Asset" and Custom_Field.objects.filter(field_kind='Asset',field_name=field_name).exists():
            messages.error(self.request,"This custom asset field name is already taken.")
            return redirect(self.request.META.get('HTTP_REFERER'))
        if field_for == "Item" and Custom_Field.objects.filter(field_kind='Item',field_name=field_name).exists():
            messages.error(self.request,"This custom item field name is already taken.")
            return redirect(self.request.META.get('HTTP_REFERER'))
        user = self.request.user
        token, create = Token.objects.get_or_create(user=user)
        http_host = get_host(self.request)
        url=http_host+'/api/custom/field/'
        payload = {'field_name': field_name,'field_type':field_type, 'is_private':is_private, 'field_kind':field_for}
        header = {'Authorization': 'Token '+ str(token), 
                      "Accept": "application/json", "Content-type":"application/json"}
        requests.post(url, headers = header, data=json.dumps(payload))
        return super(CustomFieldView, self).form_valid(form)
    
    def test_func(self):
        return self.request.user.is_superuser
    
    
    def delete_custom_field(request):
        fields = Custom_Field.objects.filter(field_kind='Item')
        asset_fields = Custom_Field.objects.filter(field_kind='Asset')
        if request.method == 'POST':
            form = DeleteFieldForm(fields,asset_fields,request.POST)
            if form.is_valid():
                pickedFields = form.cleaned_data.get('fields')
                if pickedFields:
                    for field in pickedFields:
                        delField = Custom_Field.objects.get(field_kind='Item',field_name=field)
                        user = request.user
                        token, create = Token.objects.get_or_create(user=user)
                        http_host = get_host(request)
                        url=http_host+'/api/custom/field/modify/'+ str(delField.id)+ '/'
                        header = {'Authorization': 'Token '+ str(token), 
                              "Accept": "application/json", "Content-type":"application/json"}
                        requests.delete(url, headers = header)
                pickedAssetFields = form.cleaned_data.get('asset_fields')
                if pickedAssetFields:
                    for a_field in pickedAssetFields:
                        delField = Custom_Field.objects.get(field_kind='Asset',field_name=a_field)
                        user = request.user
                        token, create = Token.objects.get_or_create(user=user)
                        http_host = get_host(request)
                        url=http_host+'/api/custom/field/modify/'+ str(delField.id)+ '/'
                        header = {'Authorization': 'Token '+ str(token), 
                              "Accept": "application/json", "Content-type":"application/json"}
                        requests.delete(url, headers = header)  
                return redirect(reverse('custom_admin:index'))
        else:
            form = DeleteFieldForm(fields,asset_fields)
        return render(request, 'custom_admin/delete_custom_field.html', {'form': form})
    
    def modify_custom_field(request):
        fields = Custom_Field.objects.filter(field_kind='Item')
        asset_fields = Custom_Field.objects.filter(field_kind='Asset')
        return render(request, 'custom_admin/modify_custom_field.html', {'fields':fields,'asset_fields':asset_fields})
    
    def modify_custom_field_modal(request,pk):
        field = Custom_Field.objects.get(id=pk)
        orig_type = field.field_type
        orig_kind = field.field_kind
        if request.method == "POST":
            form = CustomFieldForm(request.POST or None, instance=field)
            if form.is_valid():
                field_name = form['field_name'].value()
                field_type = form['field_type'].value()
                is_private = form['is_private'].value()
                field_for = form['field_kind'].value()
                user = request.user
                token, create = Token.objects.get_or_create(user=user)
                http_host = get_host(request)
                url=http_host+'/api/custom/field/modify/' + str(field.id) + '/'
                payload = {'field_name': field_name,'field_type':field_type, 'is_private':is_private, 'field_kind':field_for}
                header = {'Authorization': 'Token '+ str(token), 
                      "Accept": "application/json", "Content-type":"application/json"}
                requests.put(url, headers = header, data=json.dumps(payload))
                messages.success(request, ("Edited the " + field.field_name + " custom field."))
                if orig_kind != field_for:
                    messages.info(request, "You have changed the kind of the custom field. Your previous field value data will return if you switch the kind back while keeping the same data type." )
                if orig_type != field_type:
                     messages.info(request, "You have changed the data type of the custom field. We have reset all old values in order to apply this change." )
                return redirect(reverse('custom_admin:modify_custom_field'))
        else:
            form = CustomFieldForm(instance=field)
        return render(request, 'custom_admin/custom_field_modify_inner.html', {'form': form, 'pk':pk}) 

class RegistrationView(LoginRequiredMixin, UserPassesTestMixin, FormView):
    login_url='/login/'
    permission_required = 'is_superuser'
    form_class = RegistrationForm
    success_url = '/customadmin/'
    template_name = 'custom_admin/register_user.html'
    def form_valid(self, form):
        username = form['username'].value()
        password = form['password1'].value()
        email = form['email'].value()
        is_staff = form['staff'].value()
        is_superuser = form['admin'].value()
        user = self.request.user
        token, create = Token.objects.get_or_create(user=user)
        http_host = get_host(self.request)
        url=http_host+'/api/users/'
        payload = {'username': username,'password':password, 'email':email, 'is_staff':is_staff, 
                       'is_superuser':is_superuser, 'is_active':True}
        header = {'Authorization': 'Token '+ str(token), 
                      "Accept": "application/json", "Content-type":"application/json"}
        requests.post(url, headers = header, data = json.dumps(payload))  
        return super(RegistrationView, self).form_valid(form)
    def form_invalid(self, form):
        messages.error(self.request, form.errors.popitem())
        return super(RegistrationView, self).form_invalid(form)
    def test_func(self):
        return self.request.user.is_superuser

class UserListView(LoginRequiredMixin, UserPassesTestMixin, generic.ListView):  ## ListView to display a list of objects
    login_url = "/login/"
    template_name = 'custom_admin/user_list.html'
    context_object_name = 'user_list'
    queryset = User.objects.all()
    def get_context_data(self, **kwargs):
        context = super(UserListView, self).get_context_data(**kwargs)
        context['user_list'] = User.objects.all()
        # And so on for more models
        return context
    def test_func(self):
        return self.request.user.is_staff
    
    def edit_permission(request, pk):
        user = User.objects.get(username = pk)
        if request.method == "POST":
            form = UserPermissionEditForm(request.POST or None, instance=user, initial={'username': user.username, 'email':user.email})
            if form.is_valid():    
                user = request.user
                token, create = Token.objects.get_or_create(user=user)
                http_host = get_host(request)
                url=http_host+'/api/users/'+form['username'].value()+'/'
                payload = {'username':form['username'].value(), 'is_superuser':form.cleaned_data.get('is_superuser'),
                       'is_staff':form.cleaned_data.get('is_staff'), 'is_active':form['is_active'].value(), 
                       'email':form['email'].value()}
                header = {'Authorization': 'Token '+ str(token), 
                      "Accept": "application/json", "Content-type":"application/json"}
                requests.put(url, headers = header, data = json.dumps(payload))
        else:
            form = UserPermissionEditForm(instance = user, initial = {'username': user.username, 'email':user.email})
        return render(request, 'custom_admin/user_edit.html', {'form': form})    


@login_required(login_url='/login/')    
@user_passes_test(active_check, login_url='/login/')
def api_guide_page(request):
    if not request.user.is_staff:
        my_template = 'inventory/base.html'
    else:
        my_template = 'custom_admin/base.html'
    return render(request, 'custom_admin/api_guide.html', {'my_template':my_template})

@login_required(login_url='/login/')    
@user_passes_test(active_check, login_url='/login/')
def upload_page(request):
    if(not request.user.is_staff):
        my_template = 'inventory/base.html'
    else:
        my_template = 'custom_admin/base.html'
    return render(request, 'custom_admin/upload.html', {'my_template':my_template})



@login_required(login_url='/login/')
@user_passes_test(admin_check, login_url='/login/')
def toggleAsset(request, pk):
    user = request.user
    token, create = Token.objects.get_or_create(user=user)
    http_host = get_host(request)
    if Item.objects.get(item_id=pk).is_asset:
        # change back to non-asset
        url=http_host+'/api/requests/deny/'+pk+'/'
        payload = {'comment':''}
        header = {'Authorization': 'Token '+ str(token), 
                  "Accept": "application/json", "Content-type":"application/json"}
        requests.put(url, headers = header, data = json.dumps(payload))
    else:
        # change to asset
        url=http_host+'/api/requests/deny/'+pk+'/'
        payload = {'comment':''}
        header = {'Authorization': 'Token '+ str(token), 
                  "Accept": "application/json", "Content-type":"application/json"}
        requests.put(url, headers = header, data = json.dumps(payload))
        
    
    return redirect(reverse('custom_admin:index'))

class TagView(LoginRequiredMixin, UserPassesTestMixin):
    login_url='/login/'
    
    def delete_tag(request, pk, item):
        item = Item.objects.get(item_id=item)
        tag = Tag.objects.get(id=pk)
        tag.delete()
        return redirect('/item/' + item.item_id)

    def add_tags_module(request, pk):
        if request.method == "POST":
            item = Item.objects.get(item_id = pk)
            tags = Tag.objects.all()
            item_tags = item.tags.all()
            form = AddTagForm(tags, item_tags, request.POST or None)
            if form.is_valid():
                pickedTags = form.cleaned_data.get('tag_field')
                createdTags = form['create_new_tags'].value()
                item = Item.objects.get(item_id=pk)
                if pickedTags:
                    for oneTag in pickedTags:
                        if not item.tags.filter(tag=oneTag).exists():
                            t = Tag(tag=oneTag) 
                            t.save(force_insert=True)
                            item.tags.add(t)
                            item.save()
                if createdTags is not "":
                    tag_list = [x.strip() for x in createdTags.split(',')]
                    for oneTag in tag_list:
                        if not item.tags.filter(tag=oneTag).exists():
                            t = Tag(tag=oneTag)
                            t.save(force_insert=True)
                            item.tags.add(t)
                            item.save()
                for ittag in item_tags:
                    if form[ittag.tag].value() is "":
                        ittag.delete()
                    else:
                        ittag.tag = form[ittag.tag].value().strip()
                        ittag.save()
                    print(form[ittag.tag+"Checkbox"])
                    print(form[ittag.tag+"Checkbox"].value())
                    if form[ittag.tag+"Checkbox"].value() == True:
                        ittag.delete()
                return redirect('/item/' + pk)
        else:
            item = Item.objects.get(item_id = pk)
            tags = Tag.objects.all()
            item_tags = item.tags.all()
            form = AddTagForm(tags, item_tags)
        return render(request, 'custom_admin/add_tags_module_inner.html', {'form': form,'pk':pk, 'item_tags':item_tags})

    def test_func(self):
        return self.request.user.is_staff 
    
class ItemView(LoginRequiredMixin, UserPassesTestMixin):
    login_url='/login/'
    def test_func(self):
        return self.request.user.is_staff 
    def delete_item(request, pk):
        user = request.user
        token, create = Token.objects.get_or_create(user=user)
        http_host = get_host(request)
        url=http_host+'/api/items/'+pk+'/'
        header = {'Authorization': 'Token '+ str(token), 
                  "Accept": "application/json", "Content-type":"application/json"}
        requests.delete(url, headers = header)#, data = json.dumps(payload))
        return redirect(reverse('custom_admin:index'))
    
    def create_new_item(request):
        tags = Tag.objects.all()
        custom_fields = Custom_Field.objects.filter(field_kind='Item')
        if request.method== 'POST':
            form = CreateItemForm(tags, custom_fields, request.POST or None)
            if form.is_valid():
                post = form.save(commit=False)
                pickedTags = form.cleaned_data.get('tag_field')
                createdTags = form['new_tags'].value()
                post.save()
                messages.success(request, (form['item_name'].value() + " created successfully."))
                item = Item.objects.get(item_name = form['item_name'].value())
                Log.objects.create(request_id=None, item_id=item.item_id, item_name = item.item_name, initiating_user=request.user, nature_of_event="Create", 
                           affected_user='', change_occurred="Created item " + str(item.item_name))
                if pickedTags:
                    for oneTag in pickedTags:
                        t = Tag(tag=oneTag)
                        t.save(force_insert=True)
                        item.tags.add(t)
                        item.save()
                if createdTags is not "":
                    tag_list = [x.strip() for x in createdTags.split(',')]
                    for oneTag in tag_list:
                        t = Tag(tag=oneTag)
                        t.save()
                        item.tags.add(t)
                        item.save()
                for field in custom_fields:
                    field_value = form[field.field_name].value()
                    custom_val = Custom_Field_Value(item=item, field=field, value=field_value)
                    custom_val.save()  
                if item.is_asset:   
                    user = request.user
                    token, create = Token.objects.get_or_create(user=user)
                    http_host = get_host(request)
                    url=http_host+'/api/to_asset/'+item.item_id+'/'
                    header = {'Authorization': 'Token '+ str(token), 
                              "Accept": "application/json", "Content-type":"application/json"}
                    requests.get(url, headers = header)
                return redirect('/customadmin')
            else:
                messages.error(request, ("An error occurred while trying to create " + form['item_name'].value() + "."))
        else:
            form = CreateItemForm(tags, custom_fields)
        return render(request, 'custom_admin/item_create.html', {'form':form,'tags':tags})

    def edit_item_module(request, pk):
        item = Item.objects.get(item_id=pk)
        custom_fields = Custom_Field.objects.filter(field_kind='Item')
        custom_vals = Custom_Field_Value.objects.filter(item = item)
        original_quantity = item.quantity
        if request.method == "POST":
            form = ItemEditForm(request.user, custom_fields, custom_vals, item, request.POST or None, instance=item)
            if form.is_valid():
                values_custom_field = []
                if int(form['quantity'].value())!=original_quantity:    
                    Log.objects.create(request_id = None, item_id=str(item.item_id), item_name=item.item_name, initiating_user=request.user, nature_of_event='Override', 
                                         affected_user='', change_occurred="Change quantity from " + str(original_quantity) + ' to ' + str(form['quantity'].value()))
                else:
                    Log.objects.create(request_id=None, item_id = str(item.item_id), item_name=item.item_name, initiating_user=request.user, nature_of_event='Edit', 
                                         affected_user='', change_occurred="Edited " + str(form['item_name'].value()))
            form.save()
            for field in custom_fields:
                field_value = form[field.field_name].value()
                if Custom_Field_Value.objects.filter(item = item, field = field).exists():
                    custom_val = Custom_Field_Value.objects.get(item = item, field = field)
                else:
                    custom_val = Custom_Field_Value(item=item, field=field)
                custom_val.value = field_value
                custom_val.save()
            messages.success(request, ('Edited ' + item.item_name + '. (' + request.user.username +')'))
            return redirect('/item/' + pk)
        else:
            form = ItemEditForm(request.user, custom_fields, custom_vals, item, instance=item)
        return render(request, 'custom_admin/item_edit_module_inner.html', {'form': form, 'pk':pk}) 

@login_required(login_url='/login/')
@user_passes_test(active_check, login_url='/login/')
def create_backfill_from_loan(request, pk):
    loan = Loan.objects.get(loan_id=pk)
    if request.method == 'POST':
        form = BackfillRequestForm(request.POST, request.FILES)
        if form.is_valid():
            user = request.user
            token, create = Token.objects.get_or_create(user=user)
            http_host = get_host(request)
            url=http_host+'/api/loan/backfill/create/'+pk+'/'
            payload = {'backfill_quantity':int(form['quantity'].value()), 'backfill_status':'Requested', 
                       'loan_id':loan.loan_id}
            files = {'backfill_pdf':form['pdf'].value()}
            header = {'Authorization': 'Token '+ str(token)}#, 
                 #     "Accept": "application/json", "Content-type":"application/json"} 
            requests.post(url, headers=header, data=payload, files=files)
            if int(form['quantity'].value()) > loan.total_quantity:
                messages.error(request, ("You can't backfill more than is loaned."))
            else:
                messages.success(request, ('Successfully requested backfill.'))
            return redirect(request.META.get('HTTP_REFERER')) 
    else:
        form = BackfillRequestForm()
    return render(request, 'custom_admin/backfill_from_loan.html', {'form': form, 'pk':pk})
        
         
@login_required(login_url='/login/')
@user_passes_test(staff_check, login_url='/login/')
def add_notes_to_backfill(request, pk):
    loan = Loan.objects.get(loan_id=pk)
    if request.method == "POST":
        form = AddNotesBackfillForm(request.POST, instance=loan) # create request-form with the data from the request
        if form.is_valid():
            user = request.user
            token, create = Token.objects.get_or_create(user=user)
            http_host = get_host(request)
            url=http_host+'/api/loan/backfill/notes/'+pk+'/'
            payload = {'backfill_notes':form['backfill_notes'].value()}
            header = {'Authorization': 'Token '+ str(token), 
                      "Accept": "application/json", "Content-type":"application/json"}
            requests.put(url, headers = header, data = json.dumps(payload))
            return redirect(request.META.get('HTTP_REFERER'))  
    else:
        form = AddNotesBackfillForm(instance=loan) # blank request form with no data yet
    return render(request, 'custom_admin/backfill_add_notes.html', {'form': form, 'pk':pk})         
         
            
@login_required(login_url='/login/')
@user_passes_test(staff_check, login_url='/login/')
def add_comment_to_backfill_accept(request, pk):
    loan = Loan.objects.get(loan_id=pk)
    if request.method == "POST":
        form = AddCommentBackfillForm(request.POST) # create request-form with the data from the request
        if form.is_valid():
            user = request.user
            token, create = Token.objects.get_or_create(user=user)
            http_host = get_host(request)
            url=http_host+'/api/loan/backfill/approve/'+pk+'/'
            payload = {'backfill_notes':form['backfill_notes'].value()}
            header = {'Authorization': 'Token '+ str(token), 
                      "Accept": "application/json", "Content-type":"application/json"}
            requests.put(url, headers = header, data = json.dumps(payload))
            return redirect(request.META.get('HTTP_REFERER'))  
    else:
        form = AddCommentBackfillForm() # blank request form with no data yet
    return render(request, 'custom_admin/backfill_accept_comment.html', {'form': form, 'pk':pk})

@login_required(login_url='/login/')
@user_passes_test(staff_check, login_url='/login/')
def add_comment_to_backfill_deny(request, pk):
    loan = Loan.objects.get(loan_id=pk)
    if request.method == "POST":
        form = AddCommentBackfillForm(request.POST) # create request-form with the data from the request
        if form.is_valid():
            print("DENYING")
            user = request.user
            token, create = Token.objects.get_or_create(user=user)
            http_host = get_host(request)
            url=http_host+'/api/loan/backfill/deny/'+pk+'/'
            payload = {'backfill_notes':form['backfill_notes'].value()}
            header = {'Authorization': 'Token '+ str(token), 
                      "Accept": "application/json", "Content-type":"application/json"}
            requests.put(url, headers = header, data = json.dumps(payload))
            return redirect(request.META.get('HTTP_REFERER'))  
    else:
        form = AddCommentBackfillForm() # blank request form with no data yet
    return render(request, 'custom_admin/backfill_deny_comment.html', {'form': form, 'pk':pk})

@login_required(login_url='/login/')
@user_passes_test(staff_check, login_url='/login/')
def add_comment_to_backfill_complete(request, pk):
    loan = Loan.objects.get(loan_id=pk)
    if request.method == "POST":
        form = AddCommentBackfillForm(request.POST) # create request-form with the data from the request
        if form.is_valid():
            user = request.user
            token, create = Token.objects.get_or_create(user=user)
            http_host = get_host(request)
            url=http_host+'/api/loan/backfill/complete/'+pk+'/'
            payload = {'backfill_notes':form['backfill_notes'].value()}
            header = {'Authorization': 'Token '+ str(token), 
                      "Accept": "application/json", "Content-type":"application/json"}
            requests.put(url, headers = header, data = json.dumps(payload))
            return redirect(request.META.get('HTTP_REFERER'))  
    else:
        form = AddCommentBackfillForm() # blank request form with no data yet
    return render(request, 'custom_admin/backfill_complete_comment.html', {'form': form, 'pk':pk})


@login_required(login_url='/login/')
@user_passes_test(staff_check, login_url='/login/')
def add_comment_to_backfill_asset_complete(request, pk):
    loan = Loan.objects.get(loan_id=pk)
    if request.method == "POST":
        form = AddCommentBackfillForm(request.POST) # create request-form with the data from the request
        if form.is_valid():
            user = request.user
            token, create = Token.objects.get_or_create(user=user)
            http_host = get_host(request)
            url=http_host+'/api/loan/backfill/complete/asset/'+pk+'/'
            payload = {'backfill_notes':form['backfill_notes'].value()}
            header = {'Authorization': 'Token '+ str(token), 
                      "Accept": "application/json", "Content-type":"application/json"}
            requests.put(url, headers = header, data = json.dumps(payload))
            return redirect(request.META.get('HTTP_REFERER'))  
    else:
        form = AddCommentBackfillForm() # blank request form with no data yet
    return render(request, 'custom_admin/backfill_complete_comment_asset.html', {'form': form, 'pk':pk})


@login_required(login_url='/login/')
@user_passes_test(staff_check, login_url='/login/')
def add_comment_to_backfill_fail(request, pk):
    loan = Loan.objects.get(loan_id=pk)
    if request.method == "POST":
        form = AddCommentBackfillForm(request.POST) # create request-form with the data from the request
        if form.is_valid():
            user = request.user
            token, create = Token.objects.get_or_create(user=user)
            http_host = get_host(request)
            url=http_host+'/api/loan/backfill/fail/'+pk+'/'
            payload = {'backfill_notes':form['backfill_notes'].value()}
            header = {'Authorization': 'Token '+ str(token), 
                      "Accept": "application/json", "Content-type":"application/json"}
            requests.put(url, headers = header, data = json.dumps(payload))
            return redirect(request.META.get('HTTP_REFERER'))  
    else:
        form = AddCommentBackfillForm() # blank request form with no data yet
    return render(request, 'custom_admin/backfill_fail_comment.html', {'form': form, 'pk':pk})


@login_required(login_url='/login/')
@user_passes_test(staff_check, login_url='/login/')
def loan_reminder_body(request):
    try:
        body = LoanReminderEmailBody.objects.all()[0]
    except (ObjectDoesNotExist, IndexError) as e:
        body = LoanReminderEmailBody.objects.create(body='')
    try:
        start_dates = [str(x.date) for x in LoanSendDates.objects.all()]
        selected_dates = []
        for d in start_dates:
            selected_dates.append(d)
    except ObjectDoesNotExist:
        selected_dates = None
    if request.method == "POST":
        form = ChangeLoanReminderBodyForm(request.POST or None, initial={'body':body.body})
        if form.is_valid():
            input_date_list = form['send_dates'].value().split(',')
            #output_date_list = [datetime.strptime(x, "%m/%d/%Y") for x in input_date_list]
            payload_send_dates=[]
            for date in input_date_list:
                if date != '':
                    lst = date.split('/')
                    formatted = lst[2]+'-'+lst[0]+'-'+lst[1]
                    payload_send_dates.append({'date':formatted})
              
                #LoanSendDates.objects.create(date=date)
                #task_email.apply_async(eta=date+timedelta(hours=3))
            #LoanReminderEmailBody.objects.create(body=form['body'].value())
            user = request.user
            token, create = Token.objects.get_or_create(user=user)
            http_host = get_host(request)
            url_send_dates=http_host+'/api/loan/email/dates/configure/'
            url_loan_body = http_host+'/api/loan/email/body/'
            payload_loan_body = {'body':form['body'].value()}
            header = {'Authorization': 'Token '+ str(token), 
                      "Accept": "application/json", "Content-type":"application/json"} 
            requests.post(url_loan_body, headers = header, data = json.dumps(payload_loan_body))
            requests.post(url_send_dates, headers = header, data = json.dumps(payload_send_dates))
            return redirect(reverse('custom_admin:change_loan_body'))
    else:
        form = ChangeLoanReminderBodyForm(initial= {'body':body.body})
    return render(request, 'custom_admin/loan_email_body.html', {'form':form, 'selected_dates':sorted(selected_dates)})

class EmailView(LoginRequiredMixin, UserPassesTestMixin):
    login_url='/login/'  
 
    def delete_task_queue(request):
        user = request.user
        token, create = Token.objects.get_or_create(user=user)
        http_host = get_host(request)
        url=http_host+'/api/loan/email/dates/delete/'
        header = {'Authorization': 'Token '+ str(token), 
              "Accept": "application/json", "Content-type":"application/json"} 
        requests.delete(url, headers = header)#, data = json.dumps(payload_loan_body))
        return loan_reminder_body(request)    
    def delay_email(request):
        task_email.apply_async(eta=datetime.utcnow()+timedelta(minutes=5))
        return redirect(reverse('custom_admin:log'))
    def create_email(request):
        email = mail.EmailMessage(
        'Testing delayed email', 
        'Body goes here', 
        'noreply@duke.edu', 
        ['nrg12@duke.edu'], 
        )
        email.send(fail_silently=False)
        return redirect(reverse('custom_admin:log')) 
    def change_email_prepend(request):
        try:
            text = EmailPrependValue.objects.all()[0].prepend_text
        except (ObjectDoesNotExist, IndexError) as e:
            text=''
        if request.method == "POST":
            form = ChangeEmailPrependForm(request.POST or None, initial={'text': text})
            if form.is_valid():
                if form['text'].value() == text:
                    return redirect('/customadmin')
                else:
                    EmailPrependValue.objects.all().delete()
                    EmailPrependValue.objects.create(prepend_text=form['text'].value())
                return redirect('/customadmin')
        else:
            form = ChangeEmailPrependForm(initial={'text':text})
        return render(request, 'custom_admin/change_prepend.html', {'form': form})     

    def subscribe(request):
        exists = SubscribedUsers.objects.filter(user=request.user.username).exists()
        if request.method == "POST":
            form = SubscribeForm(request.POST or None, initial = {'subscribed': exists})
            if form.is_valid(): 
                user = request.user
                token, create = Token.objects.get_or_create(user=user)
                http_host = get_host(request)
                url=http_host+'/api/subscribe/'+user.username+'/'
                payload = {'user':user.username, 'email':user.email}
                header = {'Authorization': 'Token '+ str(token), 
                      "Accept": "application/json", "Content-type":"application/json"} 
                if form['subscribed'].value():
                    requests.post(url, headers = header, data = json.dumps(payload))
                #SubscribedUsers.objects.get_or_create(user=request.user.username)
                else:
                    requests.delete(url, headers=header, data=json.dumps(payload))
                return redirect('/customadmin')
        else:
            form = SubscribeForm(initial = {'subscribed': exists})
        return render(request, 'custom_admin/subscribe.html', {'form': form})   
    def loan_reminder_body(request):
        try:
            body = LoanReminderEmailBody.objects.all()[0]
        except (ObjectDoesNotExist, IndexError) as e:
            body = LoanReminderEmailBody.objects.create(body='')
        try:
            start_dates = [str(x.date) for x in LoanSendDates.objects.all()]
            selected_dates = []
            for d in start_dates:
                selected_dates.append(d)
        except ObjectDoesNotExist:
            selected_dates = None
        if request.method == "POST":
            form = ChangeLoanReminderBodyForm(request.POST or None, initial={'body':body.body})
            if form.is_valid():
                input_date_list = form['send_dates'].value().split(',')
                payload_send_dates=[]
                for date in input_date_list:
                    if date != '':
                        lst = date.split('/')
                        formatted = lst[2]+'-'+lst[0]+'-'+lst[1]
                        payload_send_dates.append({'date':formatted})
                user = request.user
                token, create = Token.objects.get_or_create(user=user)
                http_host = get_host(request)
                url_send_dates=http_host+'/api/loan/email/dates/configure/'
                url_loan_body = http_host+'/api/loan/email/body/'
                payload_loan_body = {'body':form['body'].value()}
                header = {'Authorization': 'Token '+ str(token), 
                      "Accept": "application/json", "Content-type":"application/json"} 
                requests.post(url_loan_body, headers = header, data = json.dumps(payload_loan_body))
                requests.post(url_send_dates, headers = header, data = json.dumps(payload_send_dates))
                return redirect(reverse('custom_admin:change_loan_body'))
        else:
            form = ChangeLoanReminderBodyForm(initial= {'body':body.body})
        return render(request, 'custom_admin/loan_email_body.html', {'form':form, 'selected_dates':sorted(selected_dates)})   
    def test_func(self):
        return self.request.user.is_staff
        




################### DJANGO CRIPSY FORM STUFF ###################
class AjaxTemplateMixin(object):
    def dispatch(self, request, *args, **kwargs):
        if not hasattr(self, 'ajax_template_name'):
            split = self.template_name.split('.html')
            split[-1] = '_inner'
            split.append('.html')
            self.ajax_template_name = ''.join(split)
        if request.is_ajax():
            self.template_name = self.ajax_template_name
        return super(AjaxTemplateMixin, self).dispatch(request, *args, **kwargs)

class UserAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        # Don't forget to filter out results depending on the visitor !
        if not self.request.user.is_authenticated():
            return User.objects.none()

        qs = User.objects.filter(is_staff="False")

        if self.q:
            qs = qs.filter(name__istartswith=self.q)

        return qs  
#     
# class TagAutocomplete(autocomplete.Select2QuerySetView):
#     def get_queryset(self):
#         qs = Tag.objects.all()
#         if self.q:
#             qs = qs.filter(name__istartswith-self.q)
#         return qs
################################################################

@login_required(login_url='/login/')    
@user_passes_test(active_check, login_url='/login/')    
def get_token(request):
    user = request.user
    token, create = Token.objects.get_or_create(user=user)
    return token.key

@login_required(login_url='/login/')    
@user_passes_test(active_check, login_url='/login/')
def get_header(request):
    token = get_token(request)
    header = {'Authorization': 'Token ' + token,"Accept": "application/json", "Content-type":"application/json"}
    return header