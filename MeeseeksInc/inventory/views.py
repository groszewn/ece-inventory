
############################# IMPORTS FOR ORIGINAL DJANGO ####################
from datetime import datetime

from django.conf import settings
from django.contrib import messages
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.models import User
from django.contrib.auth.models import User
from django.db.models.expressions import F
from django.db.models.signals import post_save
from django.dispatch.dispatcher import receiver
from django.forms.formsets import formset_factory
from django.forms.models import inlineformset_factory, modelformset_factory, \
    ModelMultipleChoiceField
from django.http import HttpResponseRedirect
from django.http.response import Http404
from django.shortcuts import render, redirect, render_to_response
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from django.views import generic
from django.views.generic.base import View, TemplateResponseMixin
from django.views.generic.edit import FormMixin
from django.views.generic.edit import FormMixin, ModelFormMixin
from django.views.generic.edit import FormMixin, ProcessFormView
import django_filters
from django_filters.filters import ModelChoiceFilter, ModelMultipleChoiceFilter
from django_filters.rest_framework.filterset import FilterSet
import requests, json, urllib, subprocess
from rest_framework import status, permissions, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.generics import ListCreateAPIView, ListAPIView
from rest_framework.renderers import TemplateHTMLRenderer
from rest_framework.response import Response
from rest_framework.views import APIView

from custom_admin.forms import AdminRequestEditForm
from custom_admin.forms import DisburseForm
from inventory.forms import EditCartAndAddRequestForm
from inventory.permissions import IsAdminOrUser, IsOwnerOrAdmin
from inventory.serializers import ItemSerializer, RequestSerializer, \
    RequestUpdateSerializer, RequestAcceptDenySerializer, RequestPostSerializer, \
    DisbursementSerializer, DisbursementPostSerializer, UserSerializer, \
    GetItemSerializer, TagSerializer, CustomFieldSerializer

from .forms import RequestForm, RequestEditForm, RequestSpecificForm, SearchForm
from .forms import RequestForm, RequestEditForm, RequestSpecificForm, SearchForm, AddToCartForm
from .models import Instance, Request, Item, Disbursement, Custom_Field, Custom_Field_Value
from .models import Instance, Request, Item, Disbursement, Tag, ShoppingCartInstance, Log
from .models import Tag


def active_check(user):
    return user.is_active
########################### IMPORTS FOR API ##############################
########################## ORIGINAL DJANGO VIEW CLASSES ###################################
###########################################################################################
################ DEFINE VIEWS AND RESPECTIVE FILES ##################
class IndexView(LoginRequiredMixin, UserPassesTestMixin, generic.ListView):  ## ListView to display a list of objects
    login_url = "/login/"
    template_name = 'inventory/index.html'
    context_object_name = 'item_list'
    
    def get_context_data(self, **kwargs):
        context = super(IndexView, self).get_context_data(**kwargs)
        tags = Tag.objects.all()
        context['form'] = SearchForm(tags)
        context['request_list'] = Request.objects.filter(user_id=self.request.user.username)
        context['approved_request_list'] = Request.objects.filter(user_id=self.request.user.username, status="Approved")
        context['pending_request_list'] = Request.objects.filter(user_id=self.request.user.username, status="Pending")
        context['denied_request_list'] = Request.objects.filter(user_id=self.request.user.username, status="Denied")
        context['item_list'] = Item.objects.all()
        context['disbursed_list'] = Disbursement.objects.filter(user_name=self.request.user.username)
        context['custom_fields'] = Custom_Field.objects.filter(is_private=False)
        context['custom_vals'] = Custom_Field_Value.objects.all()
        return context
    def get_queryset(self):
        """Return the last five published questions."""
        return Instance.objects.order_by('item')[:5]
    
    def test_func(self):
        return self.request.user.is_active
        
class SearchResultView(FormMixin, LoginRequiredMixin, UserPassesTestMixin, generic.ListView):  ## ListView to display a list of objects
    login_url = "/login/"
    template_name = 'inventory/search_result.html'
    context_object_name = 'item_list'
   
    def get_context_data(self, **kwargs):
        context = super(IndexView, self).get_context_data(**kwargs)
        context['request_list'] = Request.objects.filter(user_id=self.request.user.username)
        context['item_list'] = Item.objects.all()
        context['disbursed_list'] = Disbursement.objects.filter(user_name=self.request.user.username)
        return context
    def get_queryset(self):
        """Return the last five published questions."""
        return Instance.objects.order_by('item')[:5]
    def test_func(self):
        return self.request.user.is_active
      
class DetailView(FormMixin, LoginRequiredMixin, UserPassesTestMixin, generic.DetailView): ## DetailView to display detail for the object
    login_url = "/login/"
    model = Item
    context_object_name = 'tag_list'
    context_object_name = 'item'
    context_object_name = 'request_list'
    context_object_name = 'custom_fields'
    context_object_name = 'custom_vals'
    context_object_name = 'current_user'
    template_name = 'inventory/detail.html' # w/o this line, default would've been inventory/<model_name>.html
    form_class = AddToCartForm
    
        
    def get_context_data(self, **kwargs):
        context = super(DetailView, self).get_context_data(**kwargs)
        context['form'] = self.get_form()
        context['item'] = self.get_object()
#         tags = Tag.objects.filter(item_name=self.get_object())
        tags = self.get_object().tags.all()
        if tags:
            context['tag_list'] = tags
        user = User.objects.get(username=self.request.user.username)
        # if admin / not admin
        if(not user.is_staff):
            context['custom_fields'] = Custom_Field.objects.filter(is_private=False)
            context['request_list'] = Request.objects.filter(user_id=self.request.user.username, item_name=self.get_object().item_id , status = "Pending")
        else:
            context['custom_fields'] = Custom_Field.objects.all()
            context['request_list'] = Request.objects.filter(item_name=self.get_object().item_id , status = "Pending")    
        context['custom_vals'] = Custom_Field_Value.objects.all()
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
        item = Item.objects.get(item_id = self.object.pk)
        username = self.request.user.username
        cart_instance = ShoppingCartInstance(user_id=username, item=item, 
                                            quantity=quantity)
        cart_instance.save()
        messages.success(self.request, 
                                 ('Successfully added ' + form['quantity'].value() + " " + item.item_name + " to cart."))
        return redirect(reverse('inventory:detail', kwargs={'pk':item.item_id})) 
    
    def test_func(self):
        return self.request.user.is_active

class CartListView(LoginRequiredMixin, UserPassesTestMixin, generic.CreateView): ## DetailView to display detail for the object
    login_url = "/login/"
#     context_object_name = 'cart_list'
    template_name = 'inventory/inventory_cart.html' # w/o this line, default would've been inventory/<model_name>.html
    model = ShoppingCartInstance
    form_class = EditCartAndAddRequestForm
    
    def get(self, request, *args, **kwargs):
        """
        Handles GET requests and instantiates blank versions of the form
        and its inline formsets.
        """
        self.object = None
        form_class = self.get_form_class()
        form = self.get_form(form_class)
        EditCartAddRequestFormSet = modelformset_factory(ShoppingCartInstance, fields=('quantity', 'reason'), extra=len(self.get_queryset()))
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
        return context
    
    def post(self, request, *args, **kwargs):
        self.object = None
        form_class = self.get_form_class()
        form = self.get_form(form_class)
        EditCartAddRequestFormSet = modelformset_factory(ShoppingCartInstance, fields=('quantity', 'reason'), extra=len(self.get_queryset()))
        formset = EditCartAddRequestFormSet(self.request.POST)
        if (formset.is_valid()):
            return self.form_valid(formset)
        else:
            return self.form_invalid(formset)

    def form_valid(self, formset):
        """
        Called if all forms are valid. Creates a Recipe instance along with
        associated Ingredients and Instructions and then redirects to a
        success page.
        """
        for idx,form in enumerate(formset):
            if idx<len(self.get_queryset()):
                dataFromForm = form.cleaned_data
                quantity = dataFromForm.get('quantity')
                reason = dataFromForm.get('reason')
                cart_instance = self.get_queryset()[idx]
                item = cart_instance.item
                item_request = Request(item_name = item, user_id=self.request.user.username, request_quantity=quantity, status="Pending", reason = reason, time_requested=timezone.now())
                item_request.save()
                Log.objects.create(request_id=item_request.request_id, item_id=item.item_id, item_name=item.item_name, initiating_user=str(item_request.user_id), nature_of_event='Request', 
                        affected_user=None, change_occurred="Requested " + str(item_request.request_quantity))

         
        # DELETE ALL CART INSTANCES
        for cart_instance in self.get_queryset():
            cart_instance.delete()
        messages.success(self.request, 'You have successfully requested the items in the cart.')
        return HttpResponseRedirect('/')

    def form_invalid(self, formset):
        return self.render_to_response(
            self.get_context_data(formset=formset))

@user_passes_test(active_check, login_url='/login/')
def delete_cart_instance(request, pk): 
    ShoppingCartInstance.objects.get(cart_id=pk).delete()
    messages.success(request, 'You have successfully removed item from cart.')
    return redirect('/inventory_cart')

def request_token(request):
    request_url = "https://oauth.oit.duke.edu/oauth/authorize.php?"
    params = {
        'response_type':'token',
        'client_id': 'meeseeks-inc--inventory-system',
        #'redirect_uri' : 'http://localhost:8000/login/check_OAuth_login',
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
    
@login_required(login_url='/login/')    
@user_passes_test(active_check, login_url='/login/')
def search_view(request):
    tags = Tag.objects.all()
    return render(request, 'inventory/search.html', {'tags': tags})

@login_required(login_url='/login/')
@user_passes_test(active_check, login_url='/login/')
def edit_request(request, pk):
    instance = Request.objects.get(request_id=pk)
    if request.method == "POST":
        form = RequestEditForm(request.POST, instance=instance, initial = {'item_field': instance.item_name})
        if form.is_valid():
            messages.success(request, 'You just edited the request successfully.')
            post = form.save(commit=False)
#             post.item_id = form['item_field'].value()
#             post.item_name = Item.objects.get(item_id = post.item_id)
            post.status = "Pending"
            post.time_requested = timezone.now()
            post.save()
            Log.objects.create(request_id=instance.request_id, item_id=post.item_name.item_id, item_name=post.item_name, initiating_user=str(post.user_id), nature_of_event='Edit', 
                                         affected_user=None, change_occurred="Edited request for " + str(post.item_name))
            item = instance.item_name
            return redirect('/item/' + item.item_id)
    else:
        form = RequestEditForm(instance=instance, initial = {'item_field': instance.item_name})
    return render(request, 'inventory/request_edit.html', {'form': form})
  
@login_required(login_url='/login/')
@user_passes_test(active_check, login_url='/login/')
def edit_request_main_page(request, pk):
    instance = Request.objects.get(request_id=pk)
    if request.method == "POST":
        form = RequestEditForm(request.POST, instance=instance, initial = {'item_field': instance.item_name})
        if form.is_valid():
            messages.success(request, 'You just edited the request successfully.')
            post = form.save(commit=False)
#             post.item_id = form['item_field'].value()
#             post.item_name = Item.objects.get(item_id = post.item_id)
            post.status = "Pending"
            post.time_requested = timezone.now()
            post.save()
            Log.objects.create(reference_id = str(instance.request_id), item_name=str(post.item_name), initiating_user=str(post.user_id), nature_of_event='Edit', 
                                         affected_user=None, change_occurred="Edited request for " + str(post.item_name))
            item = instance.item_name
            return redirect('/')
    else:
        form = RequestEditForm(instance=instance, initial = {'item_field': instance.item_name})
    return render(request, 'inventory/request_edit.html', {'form': form})
  
  
# class ResultsView(LoginRequiredMixin, generic.DetailView):
#     login_url = "/login/"
#     model = Question
#     template_name = 'inventory/results.html' # w/o this line, default would've been inventory/<model_name>.html  

@login_required(login_url='/login/')
@user_passes_test(active_check, login_url='/login/')
def post_new_request(request):
    if request.method == "POST":
        form = RequestForm(request.POST) # create request-form with the data from the request 
        if form.is_valid():
            post = form.save(commit=False)
            post.item_id = form['item_field'].value()
            post.item_name = Item.objects.get(item_id = post.item_id)
            post.user_id = request.user.username
            post.status = "Pending"
            post.time_requested = timezone.now()
            post.save()
            Log.objects.create(request_id = post.request_id,item_id=post.item_name.item_id, item_name=post.item_name, initiating_user=post.user_id, nature_of_event='Request', 
                                         affected_user=None, change_occurred="Requested " + str(form['request_quantity'].value()))
            return redirect('/')
    else:
        form = RequestForm() # blank request form with no data yet
    return render(request, 'inventory/request_create.html', {'form': form})

class request_detail(ModelFormMixin, LoginRequiredMixin, UserPassesTestMixin, generic.DetailView):
    login_url = "/login/"
    model = Request
    template_name = 'inventory/request_detail.html'
    form_class = AdminRequestEditForm
    context_object_name = 'form'
    context_object_name = 'request'
    context_object_name = 'current_user'
    
    def get_context_data(self, **kwargs):
        context = super(request_detail, self).get_context_data(**kwargs)
        context['form'] = self.get_form()
        context['request'] = self.get_object()
        context['current_user'] = self.request.user.username
        return context
    
    def post(self, request, pk):
        indiv_request = Request.objects.get(request_id=pk)
        item = Item.objects.get(item_id=indiv_request.item_name_id)
        if request.method == "POST":
            form = AdminRequestEditForm(request.POST, instance=indiv_request)
            if form.is_valid():
                if 'edit' in request.POST:
                    post = form.save(commit=False)
                    post.comment = ""
                    post.status = "Pending"
                    post.time_requested = timezone.localtime(timezone.now())
                    post.save()
                    messages.success(request, ('Successfully edited ' + indiv_request.item_name.item_name + '.'))
                    Log.objects.create(request_id=indiv_request.request_id, item_id=item.item_id, item_name=item.item_name, initiating_user=str(indiv_request.user_id), nature_of_event='Edit', 
                                         affected_user=None, change_occurred="Edited request for " + str(item.item_name))
                    return redirect('/request_detail/' + pk)
                if 'approve' in request.POST:
                    if item.quantity >= indiv_request.request_quantity:
                        # decrement quantity in item
                        item.quantity = F('quantity')-indiv_request.request_quantity
                        item.save()
         
                        # change status of request to approved
                        indiv_request.status = "Approved"
                        indiv_request.save()
         
                        # add new disbursement item to table
                        disbursement = Disbursement(admin_name=request.user.username, user_name=indiv_request.user_id, item_name=Item.objects.get(item_id = indiv_request.item_name_id), 
                                    total_quantity=indiv_request.request_quantity, comment=indiv_request.comment, time_disbursed=timezone.localtime(timezone.now()))
                        disbursement.save()
                        Log.objects.create(request_id=disbursement.disburse_id, item_id=item.item_id, item_name=item.item_name, initiating_user=str(dibursement.admin_name), nature_of_event='Disburse', 
                                         affected_user=str(disbursement.user_name), change_occurred="Disbursed " + str(disbursement.total_quantity))
                        messages.success(request, ('Successfully disbursed ' + indiv_request.item_name.item_name + ' (' + indiv_request.user_id +')'))
                    else:
                        messages.error(request, ('Not enough stock available for ' + indiv_request.item_name.item_name + ' (' + indiv_request.user_id +')'))
                if 'deny' in request.POST:
                    indiv_request.status = "Denied"
                    indiv_request.save()
                    Log.objects.create(request_id=indiv_request.request_id, item_id=item.item_id, item_name=item.item_name, initiating_user=str(request.user.username), nature_of_event='Deny', 
                                         affected_user=indiv_request.user_id, change_occurred="Denied request for " + str(item.item_name))
                    messages.success(request, ('Denied disbursement ' + indiv_request.item_name.item_name + ' (' + indiv_request.user_id +')'))
                if 'cancel' in request.POST:
                    instance = Request.objects.get(request_id=pk)
                    Log.objects.create(request_id=indiv_request.request_id, item_id=item.item_id, item_name=item.item_name, initiating_user=str(request.user.username), nature_of_event='Delete', 
                             affected_user=None, change_occurred="Cancelled request for " + str(item.item_name))
                    Request.objects.get(request_id=pk).delete()
                    messages.success(request, ('Canceled request for ' + indiv_request.item_name.item_name + ' (' + indiv_request.user_id +')'))
                    return redirect('/')
                return redirect(reverse('custom_admin:index'))
            else:
                form = AdminRequestEditForm(instance=instance)
                return render(request, 'inventory/request_detail.html', {'form': form}) 
            
    def test_func(self):
        return self.request.user.is_active

@login_required(login_url='/login/')
@user_passes_test(active_check, login_url='/login/')
def approve_request(self, request, pk):
    indiv_request = Request.objects.get(request_id=pk)
    item = Item.objects.get(item_id=indiv_request.item_name_id)
    if item.quantity >= indiv_request.request_quantity:
        # decrement quantity in item
        item.quantity = F('quantity')-indiv_request.request_quantity
        item.save()

        # change status of request to approved
        indiv_request.status = "Approved"
        indiv_request.save()

        # add new disbursement item to table
        disbursement = Disbursement(admin_name=request.user.username, user_name=indiv_request.user_id, item_name=Item.objects.get(item_id = indiv_request.item_name_id), 
                    total_quantity=indiv_request.request_quantity, comment=indiv_request.comment, time_disbursed=timezone.localtime(timezone.now()))
        disbursement.save()
        Log.objects.create(request_id=indiv_request.request_id, item_id=item.item_id, item_name=item.item_name, initiating_user=str(request.user.username), nature_of_event='Disburse', 
                                     affected_user=disbursement.user_name, change_occurred="Disbursed " + str(disbursement.total_quantity))
        messages.success(request, ('Successfully disbursed ' + indiv_request.item_name.item_name + ' (' + indiv_request.user_id +')'))
    else:
        messages.error(request, ('Not enough stock available for ' + indiv_request.item_name.item_name + ' (' + indiv_request.user_id +')'))
    return redirect('/')

@login_required(login_url='/login/')    
@user_passes_test(active_check, login_url='login/')  
def cancel_request(request, pk):
    instance = Request.objects.get(request_id=pk)
    Log.objects.create(request_id = instance.request_id,item_id=instance.item_name.item_id, item_name=instance.item_name, initiating_user=instance.user_id, nature_of_event='Delete', 
                                         affected_user=None, change_occurred="Cancelled request for " + str(instance.item_name))
    messages.success(request, ('Successfully deleted request for ' + str(instance.item_name )))
    instance.delete()
    return redirect('/')

@login_required(login_url='/login/')
@user_passes_test(active_check, login_url='/login/')
def request_specific_item(request, pk):
    if request.method == "POST":
        form = RequestSpecificForm(request.POST) # create request-form with the data from the request
        if form.is_valid():
            reason = form['reason'].value()
            quantity = form['quantity'].value()
            item = Item.objects.get(item_id=pk)
            specific_request = Request(user_id=request.user.username, item_name=item, 
                                            request_quantity=quantity, status="Pending", reason=reason, time_requested=timezone.now())
            specific_request.save()
            
            messages.success(request, ('Successfully requested ' + item.item_name + ' (' + request.user.username +')'))
            request_id = specific_request.request_id
            Log.objects.create(request_id=request_id,item_id=item.item_id, item_name=item.item_name, initiating_user=request.user, nature_of_event='Request', 
                                         affected_user=None, change_occurred="Requested " + str(quantity))
            return redirect(reverse('inventory:detail', kwargs={'pk':item.item_id}))  
    else:
        form = RequestSpecificForm(initial={'available_quantity': Item.objects.get(item_id=pk).quantity}) # blank request form with no data yet
    return render(request, 'inventory/request_specific_item_inner.html', {'form': form, 'pk':pk})


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_auth_token(sender, instance=None, created=False, **kwargs):
    if created:
        Token.objects.create(user=instance)
        
def get_api_token(request):
    user = request.user
    token, create = Token.objects.get_or_create(user=user)
    messages.success(request, ('Successfully generated API access token: ' + token.key))
    if user.is_staff:
        return  HttpResponseRedirect(reverse('custom_admin:index'))
    elif user.is_superuser:
        return  HttpResponseRedirect(reverse('custom_admin:index'))
    else:
        return  HttpResponseRedirect(reverse('inventory:index'))
    
#################################### API VIEW CLASSES #####################################
###########################################################################################
###########################################################################################
########################################## Item ###########################################
class TagsMultipleChoiceFilter(django_filters.ModelMultipleChoiceFilter):
    def filter(self, qs, value): # way to pass through data
        return qs

class ItemFilter(FilterSet):
    included_tags = TagsMultipleChoiceFilter(
        queryset = Tag.objects.all(),
        name="tags", 
    )
    excluded_tags = TagsMultipleChoiceFilter(
        queryset = Tag.objects.all(),
        name="tags", 
    )
    class Meta:
        model = Item
        fields = ['item_name', 'model_number', 'quantity', 'description','included_tags', 'excluded_tags']
        

class APIItemList(ListCreateAPIView):
    """
    List all Items, or create a new item (for admin only)
    """
    permission_classes = (IsAdminOrUser,)
    model = Item
    queryset = Item.objects.all()
    serializer_class = ItemSerializer
    filter_class = ItemFilter
    
    def get_queryset(self):
        """ allow rest api to filter by submissions """
        queryset = Item.objects.all()
        included = self.request.query_params.getlist('included_tags')
        excluded = self.request.query_params.getlist('excluded_tags')
        if not included and excluded:
            queryset = queryset.exclude(tags__in=excluded)
        elif not excluded and included:
            queryset = queryset.filter(tags__in=included)
        elif excluded and included:    
            tags = [x for x in included if x not in excluded]
            queryset=queryset.filter(tags__in=tags)
        return queryset
    
    def get(self, request, format=None):
        items = self.filter_queryset(self.get_queryset())
        serializer = ItemSerializer(items, many=True)
        return Response(serializer.data)

    def post(self, request, format=None):
        serializer = ItemSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            data=serializer.data
            item_id=data['item_id']
            item_name=data['item_name']
            Log.objects.create(request_id=None, item_id=item_id, item_name = item_name, initiating_user=request.user, nature_of_event="Create", 
                       affected_user=None, change_occurred="Created item " + str(name))
            name = request.query_params.get('item_name')
            item = Item.objects.get(item_name = name)
            for field in Custom_Field.objects.all():
                value = request.query_params.get(field,None)
                if value is not None:
                    custom_val = Custom_Field_Value(item=item, field=field)
                    if field.field_type == 'Short':    
                        custom_val.field_value_short_text = value
                    if field.field_type == 'Long':
                        custom_val.field_value_long_text = value
                    if field.field_type == 'Int':
                        if value != '':
                            custom_val.field_value_integer = value
                        else:
                            custom_val.field_value_integer = None
                    if field.field_type == 'Float':
                        if value != '':
                            custom_val.field_value_floating = value 
                        else:
                            custom_val.field_value_floating = None
                    custom_val.save()
            
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class APIItemDetail(APIView):
    """
    Retrieve, update or delete a snippet instance.
    """
    permission_classes = (IsAdminOrUser,)
    
    def get_object(self, pk):
        try:
            return Item.objects.get(item_id=pk)
        except Item.DoesNotExist:
            raise Http404

    def get(self, request, pk, format=None):
        item = self.get_object(pk)
        context = {
            "request": self.request,
            "pk": pk,
        }
        serializer = GetItemSerializer(item, context=context)
        return Response(serializer.data)

    def put(self, request, pk, format=None):
        item = self.get_object(pk)
        starting_quantity = item.quantity
        serializer = ItemSerializer(item, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            data = serializer.data
            quantity=data['quantity']
            if quantity!=starting_quantity:    
                Log.objects.create(request_id=None, item_id=item.item_id, item_name=item.item_name, initiating_user=request.user, nature_of_event='Override', 
                                         affected_user=None, change_occurred="Change quantity from " + str(starting_quantity) + ' to ' + str(quantity))
            else:
                Log.objects.create(request_id=None, item_id=item.item_id, item_name=item.item_name, initiating_user=request.user, nature_of_event='Edit', 
                                         affected_user=None, change_occurred="Edited " + str(name))
            for field in Custom_Field.objects.all():
                value = request.query_params.get(field,None)
                if value is not None:
                    if Custom_Field_Value.objects.filter(item = item, field = field).exists():
                        custom_val = Custom_Field_Value.objects.get(item = item, field = field)
                    else:
                        custom_val = Custom_Field_Value(item=item, field=field)
                    if field.field_type == 'Short':    
                        custom_val.field_value_short_text = value
                    if field.field_type == 'Long':
                        custom_val.field_value_long_text = value
                    if field.field_type == 'Int':
                        if field_value != '':
                            custom_val.field_value_integer = value
                        else:
                            custom_val.field_value_integer = None
                    if field.field_type == 'Float':
                        if field_value != '':
                            custom_val.field_value_floating = value 
                        else:
                            custom_val.field_value_floating = None
                    custom_val.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk, format=None):
        item = self.get_object(pk)
        Log.objects.create(request_id=None, item_id=item.item_id, item_name = item.item_name, initiating_user=request.user, nature_of_event="Delete", 
                       affected_user=None, change_occurred="Deleted item " + str(item.item_name))
        item.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

########################################## Request ########################################
class APIRequestList(APIView):  
    """
    List all Requests (for yourself if user, all if admin), or create a new request 
    """
    permission_classes = (IsAdminOrUser,)
    
    def get(self, request, format=None):
        requests = [];
        if User.objects.get(username=request.user.username).is_staff:
            requests = Request.objects.all()
        else:
            requests = Request.objects.filter(user_id=request.user.username)
        serializer = RequestSerializer(requests, many=True)
        return Response(serializer.data)
    
class APIRequestDetail(APIView):
    """
    Retrieve, update or delete a request instance.
    """
    permission_classes = (IsAdminOrUser,)
    
    def get_object(self, pk):
        try:
            return Request.objects.get(request_id=pk)
        except Request.DoesNotExist:
            raise Http404

    def get(self, request, pk, format=None):
        indiv_request = self.get_object(pk)
        if indiv_request.user_id == request.user.username or User.objects.get(username=request.user.username).is_staff:
            serializer = RequestSerializer(indiv_request)
            return Response(serializer.data)
        return Response("Need valid authentication", status=status.HTTP_400_BAD_REQUEST)
    
    def put(self, request, pk, format=None):
        indiv_request = self.get_object(pk)
        if indiv_request.user_id == request.user.username or User.objects.get(username=request.user.username).is_staff:
            serializer = RequestUpdateSerializer(indiv_request, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save(time_requested=timezone.now())
                Log.objects.create(request_id=indiv_request.request_id, item_id=indiv_request.item_name.item_id, item_name=indiv_request.item_name, initiating_user=str(request.user_id), nature_of_event='Edit', 
                                         affected_user=None, change_occurred="Edited request for " + str(indiv_request.item_name))
                return Response(serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)     
        return Response("Need valid authentication", status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk, format=None):
        indiv_request = self.get_object(pk)
        if indiv_request.user_id == request.user.username or User.objects.get(username=request.user.username).is_staff:
            Log.objects.create(request_id=indiv_request.request_id, item_id=indiv_request.item_name.item_id, item_name = indiv_request.item_name, initiating_user=request.user, nature_of_event="Delete", 
                       affected_user=None, change_occurred="Cancelled request for " + str(indiv_request.item_name))
            indiv_request.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response("Need valid authentication", status=status.HTTP_400_BAD_REQUEST) 

class APIRequestThroughItem(APIView):
    """
    Create an item request
    """
    permission_classes = (IsAdminOrUser,)
    
    def post(self, request, pk, format=None):
        context = {
            "request": self.request,
        }
        serializer = RequestPostSerializer(data=request.data, context=context)
        if serializer.is_valid():
            serializer.save(item_name=Item.objects.get(item_id=pk))
            data=serializer.data
            id=data['request_id']
            name=data['item_name']
            quantity=data['request_quantity']
            Log.objects.create(request_id=id, item_id=pk, item_name = name, initiating_user=request.user, nature_of_event="Request", 
                       affected_user=None, change_occurred="Requested " + str(quantity))
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
class APIApproveRequest(APIView):
    """
    Approve a request with an optional reason.
    """
    permission_classes = (IsAdminOrUser,)
    def get_object(self, pk):
        try:
            return Request.objects.get(request_id=pk)
        except Request.DoesNotExist:
            raise Http404
        
    def put(self, request, pk, format=None):
        indiv_request = self.get_object(pk)
        if not indiv_request.status == "Pending":
            return Response("Already approved or denied.", status=status.HTTP_400_BAD_REQUEST)
        serializer = RequestAcceptDenySerializer(indiv_request, data=request.data, partial=True)
        item = Item.objects.get(item_id=indiv_request.item_name_id)
        if item.quantity >= indiv_request.request_quantity:
            # decrement quantity in item
            item.quantity = F('quantity')-indiv_request.request_quantity
            item.save()
            
            disbursement = Disbursement(admin_name=request.user.username, user_name=indiv_request.user_id, item_name=Item.objects.get(item_id = indiv_request.item_name_id), 
                                    total_quantity=indiv_request.request_quantity, time_disbursed=timezone.localtime(timezone.now()))
            disbursement.save()
            if serializer.is_valid():
                serializer.save(status="Approved")
                Log.objects.create(request_id=indiv_request.request_id, item_id=item.item_id, item_name = item.item_name, initiating_user=request.user, nature_of_event="Disburse", 
                       affected_user=disbursement.user_name, change_occurred="Disbursed " + str(disbursement.total_quantity))
                return Response(serializer.data, status=status.HTTP_201_CREATED)
        else:
            return Response("Not enough stock available", status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class APIDenyRequest(APIView):
    """
    Retrieve, update or delete a request instance.
    """
    permission_classes = (IsAdminOrUser,)
    
    def get_object(self, pk):
        try:
            return Request.objects.get(request_id=pk)
        except Request.DoesNotExist:
            raise Http404
        
    def put(self, request, pk, format=None):
        indiv_request = self.get_object(pk)
        if not indiv_request.status == "Pending":
            return Response("Already approved or denied.", status=status.HTTP_400_BAD_REQUEST)
        serializer = RequestAcceptDenySerializer(indiv_request, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save(status="Denied")
            Log.objects.create(request_id=indiv_request.request_id, item_id=indiv_request.item_name.item_id, item_name = indiv_request.item_name, initiating_user=request.user, nature_of_event="Deny", 
                       affected_user=indiv_request.user_id, change_occurred="Denied request for " + str(indiv_request.item_name))
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

########################################## Disbursement ###########################################
class APIDisbursementList(APIView):
    """
    List all Disbursements (for yourself if user, all if admin)
    """
    permission_classes = (IsAdminOrUser,)
    
    def get(self, request, format=None):
        requests = [];
        if User.objects.get(username=request.user.username).is_staff:
            requests = Disbursement.objects.all()
        else:
            requests = Disbursement.objects.filter(user_name=request.user.username)
        serializer = DisbursementSerializer(requests, many=True)
        return Response(serializer.data)
    
class APIDirectDisbursement(APIView):
    """
    Create a direct disbursement
    """
    permission_classes = (IsAdminOrUser,)
    
    def get_object(self, pk): #get the item to directly disburse to
        try:
            return Item.objects.get(item_id=pk)
        except Item.DoesNotExist:
            raise Http404
        
    def post(self, request, pk, format=None):
        context = {
            "request": self.request,
        }
        item_to_disburse = self.get_object(pk)
        serializer = DisbursementPostSerializer(data=request.data, context=context)
        if serializer.is_valid():
            if item_to_disburse.quantity >= int(request.data.get('total_quantity')):
                # decrement quantity in item
                item_to_disburse.quantity = F('quantity')-int(request.data.get('total_quantity'))
                item_to_disburse.save()
                serializer.save(item_name=item_to_disburse)
                data = serializer.data
                recipient=data['user_name']
                quantity = data['total_quantity']
                Log.objects.create(request_id=None, item_id=item_to_disburse.item_id, item_name = item_to_disburse.item_name, initiating_user=request.user, nature_of_event="Disburse", 
                       affected_user=recipient, change_occurred="Disbursed " + str(quantity))
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            else:
                return Response("Not enough stock available", status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

########################################## Users ###########################################
class APICreateNewUser(APIView):
    """
    Create new user as an admin 
    """
    permission_classes = (IsAdminOrUser,)
    
    def post(self, request, format=None):
        serializer = UserSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            username=serializer.data['username']
            Log.objects.create(request_id=None, item_id=None, item_name = None, initiating_user=request.user, nature_of_event="Create", 
                       affected_user=username, change_occurred="Created user")
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

########################################### Tags ##################################################
class APITagList(APIView):
    """
    List all Disbursements (for yourself if user, all if admin)
=======
########################################## Custom Field ###########################################    
class APICustomField(APIView):
    permission_classes = (IsAdminOrUser,)
    
    def get(self, request, format=None):
<<<<<<< HEAD
        serializer = TagSerializer(Tag.objects.all(), many=True)
        return Response(serializer.data)
=======
        if self.request.user.is_staff:
            fields = Custom_Field.objects.all()
            serializer = CustomFieldSerializer(fields, many=True)
            return Response(serializer.data)
        else:
            fields = Custom_Field.objects.filter(is_private = False)
            serializer = CustomFieldSerializer(fields, many=True)
            return Response(serializer.data)   
        
    def post(self, request, format=None):
        serializer = Custom_Field_Serializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
>>>>>>> a8d6e7518efad3d049a65198e1966e519d9dfeef
    
class APICustomFieldModify(APIView):

    def delete(self, request, pk, format=None):
        field = Custom_Field.objects.get(id = pk)
        field.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    