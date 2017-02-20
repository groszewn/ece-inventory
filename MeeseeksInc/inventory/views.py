
############################# IMPORTS FOR ORIGINAL DJANGO ####################
from datetime import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from django.contrib.auth.models import User
from django.db.models.expressions import F
from django.http import HttpResponseRedirect
from django.http.response import Http404
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils import timezone
from django.views import generic
from django.views.generic.edit import FormMixin
from rest_framework import status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from inventory.permissions import IsAdminOrUser, IsOwnerOrAdmin
from inventory.serializers import ItemSerializer, RequestSerializer, \
    RequestUpdateSerializer, RequestAcceptDenySerializer, RequestPostSerializer, \
    DisbursementSerializer

from .forms import RequestForm, RequestEditForm, RequestSpecificForm, SearchForm, AddToCartForm, FilterTagForm
from .models import Instance, Request, Item, Disbursement, Tag, ShoppingCartInstance


########################### IMPORTS FOR API ##############################
########################## ORIGINAL DJANGO VIEW CLASSES ###################################
###########################################################################################
################ DEFINE VIEWS AND RESPECTIVE FILES ##################
class IndexView(LoginRequiredMixin, generic.ListView):  ## ListView to display a list of objects
    login_url = "/login/"
    form_class = FilterTagForm
    template_name = 'inventory/index.html'
    context_object_name = 'item_list'
    model = Tag
    
    def get_context_data(self, **kwargs):
        context = super(IndexView, self).get_context_data(**kwargs)
        context['request_list'] = Request.objects.filter(user_id=self.request.user.username)
        context['approved_request_list'] = Request.objects.filter(user_id=self.request.user.username, status="Approved")
        context['pending_request_list'] = Request.objects.filter(user_id=self.request.user.username, status="Pending")
        context['denied_request_list'] = Request.objects.filter(user_id=self.request.user.username, status="Denied")
        context['item_list'] = Item.objects.all()
        context['disbursed_list'] = Disbursement.objects.filter(user_name=self.request.user.username)
        context['form'] = self.form_class
        return context
    def get_queryset(self):
        """Return the last five published questions."""
        return Instance.objects.order_by('item')[:5]

    def post(self, request, *args, **kwargs):
        form = self.form_class(request.POST)
        if form.is_valid():
            # <process form cleaned data>
            Tag2Include = form.cleaned_data.get('Tag2Include')
            Tag2Exclude = form.cleaned_data.get('Tag2Exclude')
            keyword_list = []
            for item in Item.objects.all():
                if  (item.description is not None) or (item.model_number is not None)  or (item.location is not None) or (item.model_number is not None): 
                    keyword_list.append(item)
             
            excluded_list = []
            for excludedTag in Tag2Exclude:
                tagQSEx = Tag.objects.filter(tag = excludedTag)
                for oneTag in tagQSEx:
                    excluded_list.append(Item.objects.get(item_name = oneTag.item_name))
#              have list of all excluded items
            included_list = []
            for pickedTag in Tag2Include:
                tagQSIn = Tag.objects.filter(tag = pickedTag)
                for oneTag in tagQSIn:
                    included_list.append(Item.objects.get(item_name = oneTag.item_name))
            # have list of all included items
             
            final_list = []
            item_list = Item.objects.all()
            if not Tag2Include:
                if Tag2Exclude:
                    final_list = [x for x in item_list if x not in excluded_list]
            else:
                final_list = [x for x in included_list if x not in excluded_list]
             
            # for a more constrained search
#             if not final_list:
#                 search_list = keyword_list
#             elif not keyword_list:
#                 search_list = final_list
#             else:
#                 search_list = [x for x in final_list if x in keyword_list]
            # for a less constrained search
            search_list = final_list 
            
            request_list = Request.objects.all()
            return render(request,'inventory/filter_result.html', {'form': form, 'item_list': item_list,'request_list': request_list,'search_list': set(search_list)})
        else: 
            return render(request, self.template_name, {'form': form})
    
class SearchResultView(FormMixin, LoginRequiredMixin, generic.ListView):  ## ListView to display a list of objects
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
      
class DetailView(FormMixin, LoginRequiredMixin, generic.DetailView): ## DetailView to display detail for the object
    login_url = "/login/"
    model = Item
    context_object_name = 'tag_list'
    context_object_name = 'item'
    context_object_name = 'request_list'
    template_name = 'inventory/detail.html' # w/o this line, default would've been inventory/<model_name>.html
    form_class = AddToCartForm
        
    def get_context_data(self, **kwargs):
        context = super(DetailView, self).get_context_data(**kwargs)
        context['form'] = self.get_form()
        context['item'] = self.get_object()
        tags = Tag.objects.filter(item_name=self.get_object())
        if tags:
            context['tag_list'] = tags
        user = User.objects.get(username=self.request.user.username)
        # if admin / not admin
        if(not user.is_staff):
            context['request_list'] = Request.objects.filter(user_id=self.request.user.username, item_name=self.get_object().item_id , status = "Pending")
        else:
            context['request_list'] = Request.objects.filter(item_name=self.get_object().item_id , status = "Pending")
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

class CartListView(LoginRequiredMixin, generic.ListView): ## DetailView to display detail for the object
    login_url = "/login/"
    context_object_name = 'cart_list'
    template_name = 'inventory/inventory_cart.html' # w/o this line, default would've been inventory/<model_name>.html
        
    def get_context_data(self, **kwargs):
        context = super(CartListView, self).get_context_data(**kwargs)
        context['cart_list'] = ShoppingCartInstance.objects.filter(user_id=self.request.user.username)
        return context
    
    def get_queryset(self):
        """Return the last five published questions."""
        return ShoppingCartInstance.objects.filter(user_id=self.request.user.username)

def edit_quantity_cart(request, pk):
    instance = Request.objects.get(request_id=pk)
    if request.method == "POST":
        form = RequestEditForm(request.POST, instance=instance, initial = {'item_field': instance.item_name})
        if form.is_valid():
            messages.success(request, 'You just edited the request successfully.')
            post = form.save(commit=False)
            post.item_id = form['item_field'].value()
            post.item_name = Item.objects.get(item_id = post.item_id)
            post.status = "Pending"
            post.time_requested = timezone.now()
            post.save()
            return redirect('/')
    else:
        form = RequestEditForm(instance=instance, initial = {'item_field': instance.item_name})
    return render(request, 'inventory/request_edit.html', {'form': form})
  
def check_login(request):
    if request.user.is_staff:
        return HttpResponseRedirect(reverse('custom_admin:index'))
    else:
        return HttpResponseRedirect(reverse('inventory:index'))
      
def search_form(request):
    if request.method == "POST":
        tags = Tag.objects.all()
        form = SearchForm(tags, request.POST)
        if form.is_valid():
            picked = form.cleaned_data.get('tags1')
            excluded = form.cleaned_data.get('tags2')
            keyword = form.cleaned_data.get('keyword')
            modelnum = form.cleaned_data.get('model_number')
            itemname = form.cleaned_data.get('item_name')
             
            keyword_list = []
            for item in Item.objects.all():
                if ((keyword is "") or ((keyword in item.item_name) or ((item.description is not None) and (keyword in item.description)) \
                    or ((item.model_number is not None) and (keyword in item.model_number)) or ((item.location is not None) and (keyword in item.location)))) \
                    and ((modelnum is "") or ((item.model_number is not None) and (modelnum in item.model_number))) \
                    and ((itemname is "") or (itemname in item.item_name)) \
                    and ((itemname is not "") or (modelnum is not "") or (keyword is not "")): 
                    keyword_list.append(item)
             
            excluded_list = []
            for excludedTag in excluded:
                tagQSEx = Tag.objects.filter(tag = excludedTag)
                for oneTag in tagQSEx:
                    excluded_list.append(Item.objects.get(item_name = oneTag.item_name))
#              have list of all excluded items
            included_list = []
            for pickedTag in picked:
                tagQSIn = Tag.objects.filter(tag = pickedTag)
                for oneTag in tagQSIn:
                    included_list.append(Item.objects.get(item_name = oneTag.item_name))
            # have list of all included items
             
            final_list = []
            item_list = Item.objects.all()
            if not picked:
                if excluded:
                    final_list = [x for x in item_list if x not in excluded_list]
            else:
                final_list = [x for x in included_list if x not in excluded_list]
             
            # for a more constrained search
            if not final_list:
                search_list = keyword_list
            elif not keyword_list:
                search_list = final_list
            else:
                search_list = [x for x in final_list if x in keyword_list]
            # for a less constrained search
            # search_list = final_list + keyword_list
            request_list = Request.objects.all()
            return render(request,'inventory/search_result.html', {'item_list': item_list,'request_list': request_list,'search_list': set(search_list)})
    else:
        tags = Tag.objects.all()
        form = SearchForm(tags)
    return render(request, 'inventory/search.html', {'form': form})
  
def edit_request(request, pk):
    instance = Request.objects.get(request_id=pk)
    if request.method == "POST":
        form = RequestEditForm(request.POST, instance=instance, initial = {'item_field': instance.item_name})
        if form.is_valid():
            messages.success(request, 'You just edited the request successfully.')
            post = form.save(commit=False)
            post.item_id = form['item_field'].value()
            post.item_name = Item.objects.get(item_id = post.item_id)
            post.status = "Pending"
            post.time_requested = timezone.now()
            post.save()
            return redirect('/')
    else:
        form = RequestEditForm(instance=instance, initial = {'item_field': instance.item_name})
    return render(request, 'inventory/request_edit.html', {'form': form})
  
# class ResultsView(LoginRequiredMixin, generic.DetailView):
#     login_url = "/login/"
#     model = Question
#     template_name = 'inventory/results.html' # w/o this line, default would've been inventory/<model_name>.html  

@login_required(login_url='/login/')
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
            return redirect('/')
    else:
        form = RequestForm() # blank request form with no data yet
    return render(request, 'inventory/request_create.html', {'form': form})
  
class request_detail(generic.DetailView):
    model = Request
    template_name = 'inventory/request_detail.html'
      
class request_cancel_view(generic.DetailView):
    model = Request
    template_name = 'inventory/request_cancel.html'
    
class filter_result_view(generic.DetailView):
    model = Item
    template_name = 'inventory/filter_result.html'
      
def cancel_request(self, pk):
    Request.objects.get(request_id=pk).delete()
    return redirect('/')

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
            return redirect(reverse('inventory:detail', kwargs={'pk':item.item_id}))  
    else:
        form = RequestSpecificForm(initial={'available_quantity': Item.objects.get(item_id=pk).quantity}) # blank request form with no data yet
    return render(request, 'inventory/request_specific_item_inner.html', {'form': form, 'pk':pk})




#################################### API VIEW CLASSES #####################################
###########################################################################################
###########################################################################################

########################################## Item ###########################################
class APIItemList(APIView):
    """
    List all Items, or create a new item (for admin only)
    """
    permission_classes = (IsAdminOrUser,)
    
    def get(self, request, format=None):
        items = Item.objects.all()
        serializer = ItemSerializer(items, many=True)
        return Response(serializer.data)

    def post(self, request, format=None):
        serializer = ItemSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
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
        serializer = ItemSerializer(item)
        return Response(serializer.data)

    def put(self, request, pk, format=None):
        item = self.get_object(pk)
        serializer = ItemSerializer(item, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk, format=None):
        item = self.get_object(pk)
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
        if self.request.user == []:
            return Response(status=status.HTTP_400_BAD_REQUEST)
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
                return Response(serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
                
        return Response("Need valid authentication", status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk, format=None):
        indiv_request = self.get_object(pk)
        if indiv_request.user_id == request.user.username or User.objects.get(username=request.user.username).is_staff:
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
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

########################################## Disbursement ###########################################
class APIDisbursementList(APIView):
    """
    List all Requests (for yourself if user, all if admin), or create a new request 
    """
    permission_classes = (IsAdminOrUser,)
    
    def get(self, request, format=None):
        requests = [];
        if not request.user.username:
            return Response("Not logged in", status=status.HTTP_400_BAD_REQUEST)
        
        if User.objects.get(username=request.user.username).is_staff:
            requests = Disbursement.objects.all()
        else:
            requests = Disbursement.objects.filter(user_name=request.user.username)
        serializer = DisbursementSerializer(requests, many=True)
        return Response(serializer.data)
    
    