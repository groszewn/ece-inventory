from datetime import datetime
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.models import User
from django.db.models.expressions import F
from django.db.models.signals import post_save
from django.dispatch.dispatcher import receiver
from django.core.mail import EmailMessage
from django.forms.formsets import formset_factory
from django.forms.models import inlineformset_factory, modelformset_factory, ModelMultipleChoiceField
from django.http import HttpResponseRedirect
from django.http.response import Http404
from django.shortcuts import render, redirect, render_to_response
from django.test import Client
from django.template import Context
from django.template.loader import render_to_string, get_template
from django.urls import reverse
from django.utils import timezone
from django.views import generic
from django.views.generic.base import View, TemplateResponseMixin
from django.views.generic.edit import FormMixin, ModelFormMixin, ProcessFormView
import django_filters
from django_filters.filters import ModelChoiceFilter, ModelMultipleChoiceFilter, \
    DateTimeFilter
from django_filters.rest_framework.filterset import FilterSet
import requests, json, urllib, subprocess
import rest_framework
from rest_framework import status, permissions, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.generics import ListCreateAPIView, ListAPIView
from rest_framework.renderers import TemplateHTMLRenderer
from rest_framework.response import Response
from rest_framework.views import APIView
from custom_admin.forms import AdminRequestEditForm, DisburseForm
from inventory.forms import EditCartAndAddRequestForm
from inventory.permissions import IsAdminOrUser, IsOwnerOrAdmin, IsAtLeastUser, \
    IsAdminOrManager, AdminAllManagerNoDelete, IsAdmin
from inventory.serializers import ItemSerializer, RequestSerializer, \
    RequestUpdateSerializer, RequestAcceptDenySerializer, RequestPostSerializer, \
    DisbursementSerializer, DisbursementPostSerializer, UserSerializer, \
    GetItemSerializer, TagSerializer, CustomFieldSerializer, CustomValueSerializer, \
    LogSerializer, MultipleRequestPostSerializer, LoanSerializer, FullLoanSerializer, \
    SubscribeSerializer, LoanReminderBodySerializer, LoanSendDatesSerializer

from .forms import RequestForm, RequestSpecificForm, AddToCartForm, RequestEditForm
from .models import Instance, Request, Item, Disbursement, Custom_Field, Custom_Field_Value
from .models import Instance, Request, Item, Disbursement, Tag, ShoppingCartInstance, Log, Loan, SubscribedUsers, EmailPrependValue, \
    LoanReminderEmailBody, LoanSendDates

from django.core.exceptions import ObjectDoesNotExist
from MeeseeksInc.celery import app


def get_host(request):
    return 'http://' + request.META.get('HTTP_HOST')

def active_check(user):
    return user.is_active

class IndexView(LoginRequiredMixin, UserPassesTestMixin, generic.ListView):
    login_url = "/login/"
    template_name = 'inventory/index.html'
    context_object_name = 'item_list'
    model = Tag
    
    def get_context_data(self, **kwargs):
        context = super(IndexView, self).get_context_data(**kwargs)
        if self.request.user.is_staff or self.request.user.is_superuser:
            context['custom_fields'] = Custom_Field.objects.filter() 
            context['request_list'] = Request.objects.all()
            context['approved_request_list'] = Request.objects.filter(status="Approved")
            context['pending_request_list'] = Request.objects.filter(status="Pending")
            context['denied_request_list'] = Request.objects.filter(status="Denied")
            context['disbursed_list'] = Disbursement.objects.filter()
            context['loan_list'] = Loan.objects.all()
            context['my_template'] = 'custom_admin/base.html'
        else:
            context['custom_fields'] = Custom_Field.objects.filter(is_private=False) 
            context['request_list'] = Request.objects.filter(user_id=self.request.user.username)
            context['approved_request_list'] = Request.objects.filter(user_id=self.request.user.username, status="Approved")
            context['pending_request_list'] = Request.objects.filter(user_id=self.request.user.username, status="Pending")
            context['denied_request_list'] = Request.objects.filter(user_id=self.request.user.username, status="Denied")
            context['disbursed_list'] = Disbursement.objects.filter(user_name=self.request.user.username)
            context['loan_list'] = Loan.objects.filter(user_name=self.request.user.username) 
            context['my_template'] = 'inventory/base.html'
        context['item_list'] = Item.objects.all()
        context['current_user'] = self.request.user.username
        context['tags'] = Tag.objects.distinct('tag')
        return context

    def get_queryset(self):
        """Return the last five published questions."""
        return Instance.objects.order_by('item')[:5] 
    def test_func(self):
        return self.request.user.is_active
                          
class DetailView(FormMixin, LoginRequiredMixin, UserPassesTestMixin, generic.DetailView):
    login_url = "/login/"
    template_name = 'inventory/detail.html'
    model = Item
    form_class = AddToCartForm
        
    def get_context_data(self, **kwargs):
        context = super(DetailView, self).get_context_data(**kwargs)
        context['form'] = self.get_form()
        context['item'] = self.get_object()
        tags = self.get_object().tags.all()
        if tags:
            context['tag_list'] = tags
        user = User.objects.get(username=self.request.user.username)
        if(not user.is_staff): # if not admin or manager
            context['custom_fields'] = Custom_Field.objects.filter(is_private=False)
            context['request_list'] = Request.objects.filter(user_id=self.request.user.username, item_name=self.get_object().item_id , status = "Pending")
            context['loan_list'] = Loan.objects.filter(user_name=self.request.user.username, item_name=self.get_object().item_id , status = "Checked Out")
            context['my_template'] = 'inventory/base.html'
        else: # if admin/manager
            context['custom_fields'] = Custom_Field.objects.all()
            context['request_list'] = Request.objects.filter(item_name=self.get_object().item_id , status = "Pending")  
            context['loan_list'] = Loan.objects.filter(item_name=self.get_object().item_id , status = "Checked Out")
            context['my_template'] = 'custom_admin/base.html'  
        context['custom_vals'] = Custom_Field_Value.objects.all()
        context['log_list'] = Log.objects.filter(item_id=self.get_object().item_id)
        context['current_user'] = self.request.user.username
        return context
    
    def post(self, request, *args, **kwargs): 
        self.object = self.get_object()
        form = self.get_form()
        if form.is_valid():
            return self.form_valid(form)
        else:
            return self.form_invalid(form)
        
    def form_valid(self, form):
        quantity = form['quantity'].value()
        type = form['type'].value()
        reason = form['reason'].value()
        item = Item.objects.get(item_id = self.object.pk)
        username = self.request.user.username
        cart_instance = ShoppingCartInstance(user_id=username, item=item, 
                                            type=type,quantity=quantity,reason=reason)
        cart_instance.save()
        messages.success(self.request, 
                                 ('Successfully added ' + form['quantity'].value() + " " + item.item_name + " to cart."))
        if self.request.user.is_staff:
            return redirect('/customadmin')
        else:
            return redirect('/')
    
    def test_func(self):
        return self.request.user.is_active

class CartListView(LoginRequiredMixin, UserPassesTestMixin, generic.CreateView):
    login_url = "/login/"
    template_name = 'inventory/inventory_cart.html'
    model = ShoppingCartInstance
    form_class = EditCartAndAddRequestForm
    
    def get(self, request, *args, **kwargs):
        self.object = None
        form_class = self.get_form_class()
        form = self.get_form(form_class)
        EditCartAddRequestFormSet = modelformset_factory(ShoppingCartInstance, fields=('quantity','type','reason',), extra=len(self.get_queryset()))
        formset = EditCartAddRequestFormSet(queryset=self.get_queryset())
        return self.render_to_response(
            self.get_context_data(formset=formset))
        
    def test_func(self):
        return self.request.user.is_active
        
    def get_queryset(self):
        return ShoppingCartInstance.objects.filter(user_id=self.request.user.username).order_by('quantity')
    
    def get_context_data(self, **kwargs):
        context = super(CartListView, self).get_context_data(**kwargs)
        context['cart_list'] = self.get_queryset()
        if self.request.user.is_staff:
            context['my_template'] = 'custom_admin/base.html'
        else:
            context['my_template'] = 'inventory/base.html'
        return context
    
    def post(self, request, *args, **kwargs):
        self.object = None
        form_class = self.get_form_class()
        form = self.get_form(form_class)
        EditCartAddRequestFormSet = modelformset_factory(ShoppingCartInstance, fields=('quantity','type','reason',), extra=len(self.get_queryset()))
        formset = EditCartAddRequestFormSet(self.request.POST)
        if (formset.is_valid()):
            return self.form_valid(formset)
        else:
            messages.error(self.request, 'Form is invalid!')
            return self.form_invalid(formset)

    def form_valid(self, formset):
        """
        Called if all forms are valid. Creates a Recipe instance along with
        associated Ingredients and Instructions and then redirects to a
        success page.
        """
        request_list = []
        for idx,form in enumerate(formset):
            if idx<len(self.get_queryset()):
                quantity = form.cleaned_data['quantity']
                reason = form.cleaned_data['reason']
                type = form.cleaned_data['type']
                cart_instance = self.get_queryset()[idx]
                item = cart_instance.item
                item_request = Request(item_name = item, user_id=self.request.user.username, type=type, request_quantity=quantity, status="Pending", reason = reason, time_requested=timezone.now())
                item_request.save()
                request_list.append((item, quantity))
                Log.objects.create(request_id=item_request.request_id, item_id=item.item_id, item_name=item.item_name, initiating_user=str(item_request.user_id), nature_of_event='Request', 
                        affected_user='', change_occurred="Requested " + str(item_request.request_quantity))
        # SEND EMAIL
        try:
            prepend = EmailPrependValue.objects.all()[0].prepend_text+ ' '
        except (ObjectDoesNotExist, IndexError) as e:
            prepend = ''
        subject = prepend + 'Request confirmation'
        to = [self.request.user.email]
        from_email='noreply@duke.edu'
        ctx = {
            'user':self.request.user,
            'request':request_list,
        }
        for user in SubscribedUsers.objects.all():
            to.append(user.email)
        message=render_to_string('inventory/request_confirmation_email.txt', ctx)
        EmailMessage(subject, message, bcc=to, from_email=from_email).send()
         
        # DELETE ALL CART INSTANCES
        for cart_instance in self.get_queryset():
            cart_instance.delete()
        messages.success(self.request, 'You have successfully requested the items in the cart.')
        if self.request.user.is_staff:
            return HttpResponseRedirect('/customadmin')
        else:
            return HttpResponseRedirect('/')

    def form_invalid(self, formset):
        return self.render_to_response(
            self.get_context_data(formset=formset))
        
    def delete_cart_instance(request, pk):
        ShoppingCartInstance.objects.get(cart_id=pk).delete()
        messages.success(request, 'You have successfully removed item from cart.')
        return redirect('/inventory_cart')

class RequestDetailView(LoginRequiredMixin, UserPassesTestMixin, generic.DetailView):
    login_url = "/login/"
    model = Request
    template_name = 'inventory/request_detail.html'
    
    def get_context_data(self, **kwargs):
        context = super(RequestDetailView, self).get_context_data(**kwargs)
        context['request'] = self.get_object()
        context['current_user'] = self.request.user.username
        if self.request.user.is_staff:
            context['my_template'] = 'custom_admin/base.html'
        else:
            context['my_template'] = 'inventory/base.html'
        return context
    
    def test_func(self):
        return self.request.user.is_active

    def edit_request(request, pk): 
        instance = Request.objects.get(request_id=pk)
        if request.method == "POST":
            form = RequestEditForm(request.POST, instance=instance)
            if form.is_valid():
                post = form.save(commit=False)
                url = get_host(request) + '/api/requests/' + instance.request_id + '/'
                payload = {'request_quantity':post.request_quantity,'type':post.type, 'reason':post.reason, 'status':'Pending'}
                header = get_header(request)
                response = requests.put(url, headers = header, data=json.dumps(payload))
                if response.status_code == 201:
                    messages.success(request, 'You just edited the request successfully.')
                    return redirect('/request_detail/' + instance.request_id )
                else:
                    messages.error(request, 'An error occurred.')
                    return redirect('/request_detail/' + instance.request_id ) 
        else:
            form = RequestEditForm(instance=instance)
        return render(request, 'inventory/request_edit_inner.html', {'form': form, 'pk':pk})
 
    def cancel_request(request, pk):
        instance = Request.objects.get(request_id=pk)
        url = get_host(request) + '/api/requests/' + instance.request_id + '/'
        header = get_header(request)
        response = requests.delete(url, headers = header)
        if response.status_code == 204:
            messages.success(request, ('Successfully deleted request for ' + str(instance.item_name)))
        else:
            messages.error(request, ('Failed to delete request for ' + str(instance.item_name)))
        if request.user.is_staff:
            return redirect(reverse('custom_admin:index'))
        else:
            return redirect(reverse('inventory:index'))

    def request_specific_item(request, pk):
        if request.method == "POST":
            form = RequestSpecificForm(request.POST) # create request-form with the data from the request
            if form.is_valid():
                url = get_host(request) + '/api/requests/create/' + pk + '/'
                payload = {'request_quantity':form['quantity'].value(),'type':form['type'].value(), 'reason':form['reason'].value(), 'status':'Pending'}
                header = get_header(request)
                response = requests.post(url, headers = header, data=json.dumps(payload))
                item = Item.objects.get(item_id=pk)
                if response.status_code == 201:
                    messages.success(request, ('Successfully requested ' + item.item_name + ' (' + request.user.username +')'))
                else:
                    messages.error(request, ('Could not request ' + item.item_name + ' (' + request.user.username +')'))
                return redirect(reverse('inventory:detail', kwargs={'pk':item.item_id}))  
        else:
            form = RequestSpecificForm(initial={'available_quantity': Item.objects.get(item_id=pk).quantity}) # blank request form with no data yet
        return render(request, 'inventory/request_specific_item_inner.html', {'form': form, 'pk':pk})


class LoanDetailView(LoginRequiredMixin, UserPassesTestMixin, generic.DetailView):
    login_url = "/login/"
    model = Loan
    template_name = 'inventory/loan_detail.html'
    
    def get_context_data(self, **kwargs):
        context = super(LoanDetailView, self).get_context_data(**kwargs)
        context['loan'] = self.get_object()
        if self.request.user.is_staff:
            context['my_template'] = 'custom_admin/base.html'
        else:
            context['my_template'] = 'inventory/base.html'
        return context
    
    def test_func(self):
        return self.request.user.is_active
 
@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_auth_token(sender, instance=None, created=False, **kwargs):
    if created:
        Token.objects.create(user=instance)
        
def get_api_token(request):
    messages.success(request, ('Successfully generated API access token: ' + get_token(request)))
    if request.user.is_staff:
        return  HttpResponseRedirect(reverse('custom_admin:index'))
    elif request.user.is_superuser:
        return  HttpResponseRedirect(reverse('custom_admin:index'))
    else:
        return  HttpResponseRedirect(reverse('inventory:index'))

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

def request_token(request):
    request_url = "https://oauth.oit.duke.edu/oauth/authorize.php?"
    params = {
        'response_type':'token',
        # 'client_id' : 'meeseeks-prod',
        'client_id': 'meeseeks-inc--inventory-system',
        #'redirect_uri' : 'https://meeseeksinc.colab.duke.edu/get_access_token',
        'redirect_uri':'http://localhost:8000/get_access_token',
        'scope':'basic identity:netid:read',
        'state':11291,
    }
    url = request_url #+ '?'urllib.parse.urlencode(params)
    for key, val in params.items():
        url+=str(key)
        url+='='
        url+=str(val)
        url+='&'
    url=url[:-1]
    return HttpResponseRedirect(url)

def getAccessToken(request): 
    return render(request, 'inventory/oauth_access_token.html')
    
def check_OAuth_login(request):
    token = request.GET['token']
    url = "https://api.colab.duke.edu/identity/v1/"
    headers = {'Accept':'application/json', 'x-api-key':'api-docs', 'Authorization': 'Bearer ' + token}
    returnDict = requests.get(url, headers=headers)
    dct = returnDict.json()
    name = dct['displayName']
    email = dct["eduPersonPrincipalName"]
    netid = dct['netid']
    userExists = User.objects.filter(username=netid).count()
    if userExists:
        user = User.objects.get(username=netid)
        login(request, user)
    else:
        user = User.objects.create_user(username=netid,email=email, password=None)
        user.save()
        login(request, user)
    return check_login(request)

@user_passes_test(active_check, login_url='/login/')    
def check_login(request):
    if request.user.is_staff:
        return  HttpResponseRedirect(reverse('custom_admin:index'))
    elif request.user.is_superuser:
        return  HttpResponseRedirect(reverse('custom_admin:index'))
    else:
        return  HttpResponseRedirect(reverse('inventory:index'))
