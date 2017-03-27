from datetime import date, time, datetime, timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist
from django.core.mail import EmailMessage
from django.db.models.expressions import F
from django.db.models.signals import post_save
from django.dispatch.dispatcher import receiver
from django.forms.formsets import formset_factory
from django.forms.models import inlineformset_factory, modelformset_factory, ModelMultipleChoiceField
from django.http import HttpResponseRedirect
from django.http.response import Http404
from django.shortcuts import render, redirect, render_to_response
from django.template import Context
from django.template.loader import render_to_string, get_template
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from django.views import generic
from django.views.generic.base import View, TemplateResponseMixin
from django.views.generic.edit import FormMixin, ModelFormMixin, ProcessFormView
import django_filters
from django_filters.filters import ModelChoiceFilter, ModelMultipleChoiceFilter
from django_filters.rest_framework.filterset import FilterSet
import requests, json, urllib, subprocess
from rest_framework import status, permissions, viewsets
import rest_framework
from rest_framework.authtoken.models import Token
from rest_framework.generics import ListCreateAPIView, ListAPIView
from rest_framework.renderers import TemplateHTMLRenderer
from rest_framework.response import Response
from rest_framework.views import APIView

from MeeseeksInc.celery import app
from custom_admin.forms import AdminRequestEditForm, DisburseForm
from custom_admin.tasks import loan_reminder_email as task_email
from inventory.forms import EditCartAndAddRequestForm
from inventory.permissions import IsAdminOrUser, IsOwnerOrAdmin, IsAtLeastUser, \
    IsAdminOrManager, AdminAllManagerNoDelete, IsAdmin
from inventory.serializers import ItemSerializer, RequestSerializer, \
    RequestUpdateSerializer, RequestAcceptDenySerializer, RequestPostSerializer, \
    DisbursementSerializer, DisbursementPostSerializer, UserSerializer, \
    GetItemSerializer, TagSerializer, CustomFieldSerializer, CustomValueSerializer, \
    LogSerializer, MultipleRequestPostSerializer, LoanSerializer, FullLoanSerializer, \
    SubscribeSerializer, LoanPostSerializer, LoanReminderBodySerializer, LoanSendDatesSerializer
from .forms import RequestForm, RequestSpecificForm, AddToCartForm, RequestEditForm
from .models import Instance, Request, Item, Disbursement, Custom_Field, Custom_Field_Value, Tag, ShoppingCartInstance, Log, Loan, SubscribedUsers, EmailPrependValue, \
    LoanReminderEmailBody, LoanSendDates
from custom_admin.tasks import loan_reminder_email as task_email
from MeeseeksInc.celery import app as celery_app
from django.core.exceptions import ObjectDoesNotExist


class TagsMultipleChoiceFilter(django_filters.ModelMultipleChoiceFilter):
    def filter(self, qs, value): # way to pass through data
        return qs

class ItemFilter(FilterSet):
    included_tags = TagsMultipleChoiceFilter(
        queryset = Tag.objects.distinct('tag'),
        name="tags", 
    )
    excluded_tags = TagsMultipleChoiceFilter(
        queryset = Tag.objects.distinct('tag'),
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
    custom_value_serializer = CustomValueSerializer
    filter_class = ItemFilter
    
    def get_queryset(self):
        """ allow rest api to filter by submissions """
        queryset = Item.objects.all()
        included_temp = self.request.query_params.getlist('included_tags')
        excluded_temp = self.request.query_params.getlist('excluded_tags')
        # now find all included/excluded tags with the same tag name
        included=[]
        excluded=[]
        for inc in included_temp:
            tag_name = Tag.objects.get(id=inc).tag
            for same_name_tag in Tag.objects.filter(tag=tag_name):
                included.append(same_name_tag.id)

        for exc in excluded_temp:
            tag_name = Tag.objects.get(id=exc).tag
            for same_name_tag in Tag.objects.filter(tag=tag_name):
                excluded.append(same_name_tag.id)

        if not included and excluded:
            queryset = queryset.exclude(tags__in=excluded)
        elif not excluded and included:
            queryset = queryset.filter(tags__in=included).distinct()
        elif excluded and included:
            included_queryset = queryset.filter(tags__in=included)
            excluded_queryset = queryset.filter(tags__in=excluded)
            queryset = included_queryset.exclude(item_id__in=excluded_queryset).distinct()
        return queryset
    
    def get(self, request, format=None):
        items = self.filter_queryset(self.get_queryset())
        context = {
            "request": self.request,
        }
        serializer = ItemSerializer(items, many=True, context=context)
        return Response(serializer.data)

    def post(self, request, format=None):
        context = {
            "request": self.request,
        }
        serializer = ItemSerializer(data=request.data, context=context)
        if serializer.is_valid():
            serializer.save()
            data=serializer.data
            item_id=data['item_id']
            item_name=data['item_name']
            Log.objects.create(request_id=None, item_id=item_id, item_name = item_name, initiating_user=request.user, nature_of_event="Create", 
                       affected_user='', change_occurred="Created item " + str(item_name))
            name = request.data.get('item_name',None)
            item = Item.objects.get(item_name = name)
            custom_field_values = request.data.get('values_custom_field')
            if custom_field_values is not None:
                for field in Custom_Field.objects.all():
                    value = next((x for x in custom_field_values if x['field']['field_name'] == field.field_name), None) 
                    if value is not None:
                        custom_val = Custom_Field_Value(item=item, field=field)
                        if field.field_type == 'Short':    
                            custom_val.field_value_short_text = value['field_value_short_text']
                        if field.field_type == 'Long':
                            custom_val.field_value_long_text = value['field_value_long_text']
                        if field.field_type == 'Int':
                            if value != '':
                                custom_val.field_value_integer = value['field_value_integer']
                            else:
                                custom_val.field_value_integer = None
                        if field.field_type == 'Float':
                            if value != '':
                                custom_val.field_value_floating = value['field_value_floating'] 
                            else:
                                custom_val.field_value_floating = None
                        custom_val.save()  
            context = {
            "request": self.request,
            "pk": item.item_id,
            }        
            serializer =  ItemSerializer(item, data=request.data, partial=True, context=context)
            if serializer.is_valid():
                return Response(serializer.data,status=status.HTTP_201_CREATED)
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)        
            
        return Response(serializer.errors,status=status.HTTP_400_BAD_REQUEST)

class APIItemDetail(APIView):
    """
    Retrieve, update or delete an item instance.
    """
    permission_classes = (AdminAllManagerNoDelete,)
    serializer_class = ItemSerializer
    
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
        serializer = ItemSerializer(item, context=context)
        return Response(serializer.data)

    def put(self, request, pk, format=None):
        item = self.get_object(pk)
        starting_quantity = item.quantity
        context = {
            "request": self.request,
            "pk": pk,
        }
        if 'tag' in request.data:
            tag_ids = request.data['tags']
            tags = Tag.objects.filter(id__in=tag_ids)
            item.tags.set(tags)
        
        serializer = ItemSerializer(item, data=request.data, context=context, partial=True)
        if serializer.is_valid():
            serializer.save()
            data = serializer.data
            
            quantity=data['quantity']
            if quantity!=starting_quantity:    
                Log.objects.create(request_id=None, item_id=item.item_id, item_name=item.item_name, initiating_user=request.user, nature_of_event='Override', 
                                         affected_user='', change_occurred="Change quantity from " + str(starting_quantity) + ' to ' + str(quantity))
            else:
                Log.objects.create(request_id=None, item_id=item.item_id, item_name=item.item_name, initiating_user=request.user, nature_of_event='Edit', 
                                         affected_user='', change_occurred="Edited " + str(item.item_name))
            custom_field_values = request.data.get('values_custom_field')
            if custom_field_values is not None:
                for field in Custom_Field.objects.all():
                    value = next((x for x in custom_field_values if x['field']['field_name'] == field.field_name), None) 
                    if value is not None:
                        if Custom_Field_Value.objects.filter(item = item, field = field).exists():
                            custom_val = Custom_Field_Value.objects.get(item = item, field = field)
                        else:
                            custom_val = Custom_Field_Value(item=item, field=field)
                        if field.field_type == 'Short':    
                            custom_val.field_value_short_text = value['field_value_short_text']
                        if field.field_type == 'Long':
                            custom_val.field_value_long_text = value['field_value_long_text']
                        if field.field_type == 'Int':
                            if value != '':
                                custom_val.field_value_integer = value['field_value_integer']
                            else:
                                custom_val.field_value_integer = None
                        if field.field_type == 'Float':
                            if value != '':
                                custom_val.field_value_floating = value['field_value_floating'] 
                            else:
                                custom_val.field_value_floating = None
                        custom_val.save()
            context = {
            "request": self.request,
            "pk": pk,
            }        
            serializer = ItemSerializer(item, data=request.data, partial=True, context=context)
            
            if serializer.is_valid():
                return Response(serializer.data)
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk, format=None):
        item = self.get_object(pk)
        Log.objects.create(request_id=None, item_id=item.item_id, item_name = item.item_name, initiating_user=request.user, nature_of_event="Delete", 
                       affected_user='', change_occurred="Deleted item " + str(item.item_name))
        item.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

########################################## Request ########################################
class RequestFilter(FilterSet):
    class Meta:
        model = Request
        fields = ['status']
       
class APIRequestList(ListAPIView):  
    """
    List all Requests (for yourself if user, all if admin/manager)
    """
    permission_classes = (IsAdminOrUser,)
    serializer_class = RequestSerializer
    filter_class = RequestFilter
    model = Request
    queryset = Request.objects.all()
    
    def get(self, request, format=None):
        requests = [];
        if User.objects.get(username=request.user.username).is_staff:
            requests = self.filter_queryset(Request.objects.all())
        else:
            requests = self.filter_queryset(Request.objects.filter(user_id=request.user.username))
        serializer = RequestSerializer(requests, many=True)
        return Response(serializer.data)
    
class APIRequestDetail(APIView):
    """
    Retrieve, update or delete a request instance (for yourself if user, all if admin/manager)
    """
    permission_classes = (IsAtLeastUser,)
    serializer_class = RequestUpdateSerializer
    
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
            change_list=[]
            if serializer.is_valid():
                
                if int(serializer.validated_data['request_quantity']) != int(indiv_request.request_quantity):
                    change_list.append(('request quantity', indiv_request.request_quantity, serializer.validated_data['request_quantity']))
                if serializer.validated_data['reason'] != indiv_request.reason:
                    change_list.append(('reason', indiv_request.reason, serializer.validated_data['reason']))
                if serializer.validated_data['type'] != indiv_request.type:
                    change_list.append(('type', indiv_request.type, serializer.validated_data['type']))
                serializer.save(time_requested=timezone.now())
                Log.objects.create(request_id=indiv_request.request_id, item_id=indiv_request.item_name.item_id, item_name=indiv_request.item_name, initiating_user=str(request.user), nature_of_event='Edit', 
                                         affected_user='', change_occurred="Edited request for " + str(indiv_request.item_name))
                try:
                    prepend = EmailPrependValue.objects.all()[0].prepend_text+ ' '
                except (ObjectDoesNotExist, IndexError) as e:
                    prepend = ''
                subject = prepend + 'Request edit'
                to = [User.objects.get(username=indiv_request.user_id).email]
                from_email='noreply@duke.edu'
                ctx = {
                    'user':request.user,
                    'changes':change_list,
                }
                message=render_to_string('inventory/request_edit_email.txt', ctx)
                if len(change_list)>0:
                    EmailMessage(subject, message, bcc=to, from_email=from_email).send()
                return Response(serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)     
        return Response("Need valid authentication", status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk, format=None):
        indiv_request = self.get_object(pk)
        if indiv_request.user_id == request.user.username or User.objects.get(username=request.user.username).is_staff:
            Log.objects.create(request_id=indiv_request.request_id, item_id=indiv_request.item_name.item_id, item_name = indiv_request.item_name, initiating_user=request.user, nature_of_event="Delete", 
                       affected_user='', change_occurred="Cancelled request for " + str(indiv_request.item_name))
            try:
                prepend = EmailPrependValue.objects.all()[0].prepend_text+ ' '
            except (ObjectDoesNotExist, IndexError) as e:
                prepend = ''
            subject = prepend + 'Request cancel'
            to = [User.objects.get(username=indiv_request.user_id).email]
            from_email='noreply@duke.edu'
            ctx = {
                'user':request.user,
                'item':indiv_request.item_name,
                'quantity':indiv_request.request_quantity,
            }
            message=render_to_string('inventory/request_cancel_email.txt', ctx)
            EmailMessage(subject, message, bcc=to, from_email=from_email).send()
            indiv_request.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response("Need valid authentication", status=status.HTTP_400_BAD_REQUEST) 

class APIRequestThroughItem(APIView):
    """
    Create an item request
    """
    permission_classes = (IsAtLeastUser,)
    serializer_class = RequestPostSerializer
    
    def post(self, request, pk, format=None):
        context = {
            "request": self.request,
        }
        serializer = RequestPostSerializer(data=request.data, context=context)
        request_list=[]
        if serializer.is_valid():
            serializer.save(item_name=Item.objects.get(item_id=pk))
            item = Item.objects.get(item_id=pk)
            data=serializer.data
            id=data['request_id']
            quantity=data['request_quantity']
            request_list.append((item.item_name, quantity))
            Log.objects.create(request_id=id, item_id=pk, item_name = item.item_name, initiating_user=request.user, nature_of_event="Request", 
                       affected_user='', change_occurred="Requested " + str(quantity))
            try:
                prepend = EmailPrependValue.objects.all()[0].prepend_text+ ' '
            except (ObjectDoesNotExist, IndexError):
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
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class APIMultipleRequests(APIView):
    """
    Create item requests for multiple items
    """
    permission_classes = (IsAtLeastUser,)
    
    def post(self, request, item_list, format=None):
        context = {
            "request": self.request,
        }
        if item_list:
            item_id_list = item_list.split(',')
            if len(request.data)>len(item_id_list):
                del request.data[len(item_id_list):]
            for i, item_id in enumerate(item_id_list):
                if i>=len(request.data):
                    item_name_dict = {'item_name':item_id}
                    request.data.append(dict(item_name_dict))
                else:
                    request.data[i]['item_name']=item_id
        print(request.data)
        serializer = MultipleRequestPostSerializer(data=request.data, many=True, context=context)
        request_list=[]
        if serializer.is_valid():
            serializer.save()
            dataDict=serializer.data
            for data in dataDict:
                id=data['request_id']
                quantity=data['request_quantity']
                item = Item.objects.get(item_id=data['item_name'])
                request_list.append((item.item_name, quantity))
                Log.objects.create(request_id=id, item_id=data['item_name'], item_name = item.item_name, initiating_user=request.user, nature_of_event="Request", 
                            affected_user='', change_occurred="Requested " + str(quantity))
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
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
class APIApproveRequest(APIView):
    """
    Approve a request with an optional reason.
    """
    permission_classes = (IsAdminOrUser,)
    serializer_class = RequestAcceptDenySerializer
        
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
        item = Item.objects.get(item_name = indiv_request.item_name.item_name)
        comment = request.data['comment']
        if item.quantity >= indiv_request.request_quantity:
            # decrement quantity in item
            item.quantity = F('quantity')-indiv_request.request_quantity
            item.save()
            if indiv_request.type == "Dispersal": 
                # add new disbursement item to table
                disbursement = Disbursement(admin_name=request.user.username, orig_request=indiv_request, user_name=indiv_request.user_id, item_name=item, 
                                            total_quantity=indiv_request.request_quantity, comment=comment, time_disbursed=timezone.localtime(timezone.now()))
                disbursement.save() 
                Log.objects.create(request_id=disbursement.disburse_id, item_id= item.item_id, item_name = item.item_name, initiating_user=request.user, 
                                   nature_of_event="Approve", affected_user=indiv_request.user_id, change_occurred="Disbursed " + str(indiv_request.request_quantity))
            elif indiv_request.type == "Loan":
                # add new loan item to table
                loan = Loan(admin_name=request.user.username, orig_request=indiv_request, user_name=indiv_request.user_id, item_name=item, 
                                            total_quantity=indiv_request.request_quantity, comment=comment, time_loaned=timezone.localtime(timezone.now()))    
                loan.save()
                Log.objects.create(request_id=loan.loan_id, item_id= item.item_id, item_name = item.item_name, initiating_user=request.user, 
                                   nature_of_event="Approve", affected_user=indiv_request.user_id, change_occurred="Loaned " + str(indiv_request.request_quantity))
            # change status of request to approved
            if serializer.is_valid():
                serializer.save(status="Approved")
                Log.objects.create(request_id=indiv_request.request_id, item_id=item.item_id, item_name = item.item_name, initiating_user=request.user, nature_of_event="Approve", 
                       affected_user=indiv_request.user_id, change_occurred="Disbursed " + str(indiv_request.request_quantity))
                try:
                    prepend = EmailPrependValue.objects.all()[0].prepend_text+ ' '
                except (ObjectDoesNotExist, IndexError) as e:
                    prepend = ''
                subject = prepend + 'Request approval'
                to = [self.request.user.email]
                from_email='noreply@duke.edu'
                ctx = {
                    'user':self.request.user,
                    'item':item.item_name,
                    'quantity':indiv_request.request_quantity,
                }
                message=render_to_string('inventory/request_approval_email.txt', ctx)
                EmailMessage(subject, message, bcc=to, from_email=from_email).send()
                return Response(serializer.data, status=status.HTTP_201_CREATED)
        else:
            return Response("Not enough stock available", status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class APIDenyRequest(APIView):
    """
    Deny a request with an optional reason.
    """
    permission_classes = (IsAdminOrUser,)
    serializer_class = RequestAcceptDenySerializer
    
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
            Log.objects.create(request_id=indiv_request.request_id, item_id=indiv_request.item_name_id, item_name = indiv_request.item_name, initiating_user=request.user, nature_of_event="Deny", 
                       affected_user=indiv_request.user_id, change_occurred="Denied request for " + str(indiv_request.item_name))
            try:
                prepend = EmailPrependValue.objects.all()[0].prepend_text+ ' '
            except (ObjectDoesNotExist, IndexError) as e:
                prepend = ''
            subject = prepend + 'Request denial'
            to = [self.request.user.email]
            from_email='noreply@duke.edu'
            ctx = {
                'user':self.request.user,
                'item':indiv_request.item_name,
                'quantity':indiv_request.request_quantity,
                'comment': serializer.data.get('comment'),
            }
            message=render_to_string('inventory/request_denial_email.txt', ctx)
            EmailMessage(subject, message, bcc=to, from_email=from_email).send()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

########################################## Disbursement ###########################################
class APIDisbursementList(APIView):
    """
    List all Disbursements (for yourself if user, all if admin)
    """
    permission_classes = (IsAdminOrUser,)
    serializer_class = DisbursementSerializer
    
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
    Create a direct disbursement (Admin/manager)
    """
    permission_classes = (IsAdminOrUser,)
    serializer_class = DisbursementPostSerializer
    
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
        serializer = None
        if request.data.get('type') == "Dispersal":
            serializer = DisbursementPostSerializer(data=request.data, context=context)
        if request.data.get('type') == "Loan":
            serializer = LoanPostSerializer(data=request.data, context=context)
        if serializer.is_valid():
            if item_to_disburse.quantity >= int(request.data.get('total_quantity')):
                # decrement quantity in item
                item_to_disburse.quantity = F('quantity')-int(request.data.get('total_quantity'))
                item_to_disburse.save()
                serializer.save(item_name=Item.objects.get(item_id=pk))
                data = serializer.data
                recipient=data['user_name']
                quantity = data['total_quantity']
                if request.data.get('type') == "Dispersal":
                    Log.objects.create(request_id=None, item_id=item_to_disburse.item_id, item_name = item_to_disburse.item_name, initiating_user=request.user, nature_of_event="Disburse", 
                                       affected_user=recipient, change_occurred="Disbursed " + str(quantity))
                if request.data.get('type') == "Loan":
                    Log.objects.create(request_id=None, item_id=item_to_disburse.item_id, item_name=item_to_disburse.item_name, initiating_user=request.user, nature_of_event='Loan', 
                                       affected_user=recipient, change_occurred="Loaned " + str(quantity))
                try:
                    prepend = EmailPrependValue.objects.all()[0].prepend_text+ ' '
                except (ObjectDoesNotExist, IndexError) as e:
                    prepend = ''
                subject = prepend + 'Direct Dispersal'
                to = [User.objects.get(username=recipient).email]
                from_email='noreply@duke.edu'
                ctx = {
                    'user':recipient,
                    'item':item_to_disburse.item_name,
                    'quantity':item_to_disburse.quantity, # shouldn't this be quantity given? so int(request.data.get('total_quantity'))
                    'disburser':request.user.username,
                    'type': 'disbursed',
                }
                message=render_to_string('inventory/disbursement_email.txt', ctx)
                EmailMessage(subject, message, bcc=to, from_email=from_email).send()
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            else:
                return Response("Not enough stock available", status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

########################################## Users ###########################################
class APIUserList(APIView):
    """
    List all users (admin)
    """
    permission_classes = (IsAdminOrUser,)
    
    def get(self, request, format=None):
        if User.objects.get(username=request.user.username).is_superuser:
            serializer = UserSerializer(User.objects.all(), many=True)
            return Response(serializer.data)
        return Response("Need valid authentication", status=status.HTTP_400_BAD_REQUEST) 
    
    def post(self, request, format=None):
        serializer = UserSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            username=serializer.data['username']
            Log.objects.create(request_id=None, item_id=None, item_name = '', initiating_user=request.user, nature_of_event="Create", 
                       affected_user=username, change_occurred="Created user")
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
class APIUserDetail(APIView):
    """
    Create new user as an admin 
    """
    permission_classes = (IsAdmin,)
    
    def get_object(self, pk):
        try:
            return User.objects.get(username=pk)
        except User.DoesNotExist:
            raise Http404

    def get(self, request, pk, format=None):
        if User.objects.get(username=request.user.username).is_superuser:
            user = self.get_object(pk)
            serializer = UserSerializer(user)
            return Response(serializer.data)
        return Response("Need valid authentication", status=status.HTTP_400_BAD_REQUEST) 
    
    def put(self, request, pk, format=None):
        user = self.get_object(pk)
        serializer = UserSerializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            Log.objects.create(request_id=None, item_id=None, item_name='', initiating_user=request.user, nature_of_event="Edit",
                               affected_user=serializer.data['username'], change_occurred="Changed permissions for " + str(serializer.data['username']))
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

########################################### Tags ##################################################
class APITagList(APIView):
    """
    List all Tags
    """
    permission_classes = (IsAdminOrUser,)
    serializer_class = TagSerializer
    
    def get(self, request, format=None):
        serializer = TagSerializer(Tag.objects.all(), many=True)
        return Response(serializer.data)

class APITagDetail(APIView):
    """
    edit tag
    """
    permission_classes = (IsAdminOrUser,)
    serializer_class = TagSerializer
    
    def get(self, request, format=None):
        serializer = TagSerializer(Tag.objects.all(), many=True)
        return Response(serializer.data)

########################################### Logs ##################################################
class LogFilter(FilterSet):
    item_name = ModelChoiceFilter(
        queryset = Item.objects.all(),
        name="item_name", 
    )
#     time_occurred = DateTimeFilter(
#         name="time_occurred"
#     )
    class Meta:
        model = Log
        fields = ['item_name', 'initiating_user', 'nature_of_event', 'time_occurred', 'affected_user', 'change_occurred']
        
class APILogList(ListAPIView):
    """
    List all Logs (admin / manager)
    """
    permission_classes = (IsAdminOrManager,)
#     pagination_class = rest_framework.pagination.PageNumberPagination
    pagination_class = rest_framework.pagination.LimitOffsetPagination
    model = Log
    filter_class = LogFilter
    queryset = Log.objects.all()
    serializer_class = LogSerializer
     
    def get(self, request, format=None):
        page = self.paginate_queryset(self.filter_queryset(Log.objects.all()))
        if page is not None:
            serializer = LogSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = LogSerializer(Log.objects.all(), many=True)
        return Response(serializer.data)
    
    @property
    def paginator(self):
        """
        The paginator instance associated with the view, or `None`.
        """
        if not hasattr(self, '_paginator'):
            if self.pagination_class is None:
                self._paginator = None
            else:
                self._paginator = self.pagination_class()
        return self._paginator

    def paginate_queryset(self, queryset):
        """
        Return a single page of results, or `None` if pagination is disabled.
        """
        if self.paginator is None:
            return None
        return self.paginator.paginate_queryset(queryset, self.request, view=self)

    def get_paginated_response(self, data):
        """
        Return a paginated style `Response` object for the given output data.
        """
        assert self.paginator is not None
        return self.paginator.get_paginated_response(data)

########################################## Custom Field ###########################################    
class APICustomField(APIView):
    """
    List custom fields (w/ private fields for admin/manager) and create custom fields (admin)
    """
    permission_classes = (IsAdmin,)
    serializer_class = CustomFieldSerializer
    
    def get(self, request, format=None):
        if self.request.user.is_staff:
            fields = Custom_Field.objects.all()
            serializer = CustomFieldSerializer(fields, many=True)
            return Response(serializer.data)
        else:
            fields = Custom_Field.objects.filter(is_private = False)
            serializer = CustomFieldSerializer(fields, many=True)
            return Response(serializer.data)   
        
    def post(self, request, format=None):
        serializer = CustomFieldSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            data=serializer.data
            field=data['field_name']
            Log.objects.create(request_id=None, item_id=None, item_name="-", initiating_user = request.user, nature_of_event="Create", 
                               affected_user='', change_occurred='Added custom field ' + str(field))
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class APICustomFieldModify(APIView):
    """
    Delete specific custom field
    """
    permission_classes = (IsAdminOrUser,)
    
    def get_object(self, pk):
        try:
            return Custom_Field.objects.get(id=pk)
        except Custom_Field.DoesNotExist:
            raise Http404
        
    def get(self, request, pk, format=None):
        if self.request.user.is_staff:
            field = self.get_object(pk)
            serializer = CustomFieldSerializer(field)
            return Response(serializer.data)
        else:
            field = self.get_object(pk)
            if not field.is_private:
                serializer = CustomFieldSerializer(field, many=True)
                return Response(serializer.data)   
            return Response("Need valid authentication", status=status.HTTP_400_BAD_REQUEST) 
        
    def delete(self, request, pk, format=None):
        field = Custom_Field.objects.get(id = pk)
        Log.objects.create(request_id=None,item_id=None,  item_name="-", initiating_user = request.user, nature_of_event="Delete", 
                                       affected_user='', change_occurred='Deleted custom field ' + str(field.field_name))
        field.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

########################################## Bulk Upload ########################################### 
class ItemUpload(APIView):
    """
    Uploading items via API
    """
    def errorHandling(self, request, message, createdItems):
        for createdItem in createdItems:
            createdItem.delete()
        messages.error(request._request, message)
        return Response(message, status=status.HTTP_400_BAD_REQUEST)
        
    def post(self, request, *args, **kwargs):
        csvData = request.POST.getlist('data[]')
        headerMap = {}
        customFieldMap = {}
        headers = csvData[0].split(',')
        custom_fields = Custom_Field.objects.all()
        for i, header in enumerate(headers):
            if not (header.lower() == "item name" or header.lower() == "quantity" or header.lower() == "model number" or header.lower() =="description" or header.lower() == "tags"):
                # ERROR CHECK, make sure the custom field names are correct 
                if not any(field.field_name == header for field in custom_fields):
                    messages.error(request._request, 
                                 'field ' + header + ' does not exist')
                    return Response('field ' + header + ' does not exist', status=status.HTTP_400_BAD_REQUEST) 
                customFieldMap[header.lower()] = i
            else:
                headerMap[header.lower()] = i    
            
        # ERROR CHECK, make sure that item name and quantity headers exist
        if not "item name" in headerMap:
            messages.error(request._request, 
                                 'Item Name does not exist in header')
            return Response("Make sure item name exists in header", status=status.HTTP_400_BAD_REQUEST) 
        if not "quantity" in headerMap:
            messages.error(request._request, 
                                 'Quantity does not exist in header')
            return Response("Make sure quantity exists in header", status=status.HTTP_400_BAD_REQUEST) 
        
        createdItems = []
        for i, csvRow in enumerate(csvData[1:]):
            row = csvRow.split(',')
            if row[headerMap["item name"]]=='':
                messages.error(request._request, 
                                 'item name does not exist in row ' + str(i+1))
                return Response('item name does not exist in row ' + str(i+1), status=status.HTTP_400_BAD_REQUEST) 
            if row[headerMap["quantity"]]=='':
                messages.error(request._request, 
                                 'quantity does not exist in row ' + str(i+1))
                return Response('quantity does not exist in row ' + str(i+1), status=status.HTTP_400_BAD_REQUEST) 
            item, created = Item.objects.get_or_create(item_name=row[headerMap["item name"]], quantity=row[headerMap["quantity"]], model_number=row[headerMap["model number"]], description=row[headerMap["description"]])
            if not created:
                return self.errorHandling(request, "Item " + row[headerMap["item name"]] + " already exists", createdItems)

            item.save()
            createdItems.append(item)
            # add to tags
            for tag in row[headerMap["tags"]].split('/'):
                t = Tag(tag=tag)
                t.save(force_insert=True)
                item.tags.add(t)
                item.save()
            # add custom fields
            for custom_field, j in customFieldMap.items():
                actual_field = next((x for x in custom_fields if x.field_name.lower() == custom_field), None)
                if actual_field.field_type == "Short":
                    if len(row[j])<=400:
                        value = Custom_Field_Value(item=item, field=actual_field, field_value_short_text=row[j])
                        value.save()
                    else:
                        return self.errorHandling(request, "custom_field at row " + str(i+1) + " is not short text. Length is too long", createdItems) 
                elif actual_field.field_type == "Long":
                    if len(row[j])<=1000:
                        value = Custom_Field_Value(item=item, field=actual_field, field_value_long_text=row[j])
                        value.save()
                    else:
                        return self.errorHandling(request, "custom_field at row " + str(i+1) + " is not long text. Length is too long", createdItems)  
                elif actual_field.field_type == "Int":
                    try:
                        int(row[j])
                        value = Custom_Field_Value(item=item, field=actual_field, field_value_integer=int(row[j]))
                        value.save()
                    except ValueError:
                        if row[j] == "":
                            continue
                        else:
                            return self.errorHandling(request,"custom_field at row " + str(i+1) + " is not a int", createdItems) 
                elif actual_field.field_type == "Float":
                    try:
                        float(row[j])
                        value = Custom_Field_Value(item=item, field=actual_field, field_value_floating=float(row[j]))
                        value.save()
                    except ValueError:
                        if row[j] == "":
                            continue
                        else:
                            return self.errorHandling(request, "custom_field at row " + str(i+1) + " is not a float", createdItems)
        items = {}
#         pk_list = [5, 7, 1, 3, 4]  
#         clauses = ' '.join(['WHEN id=%s THEN %s' % (pk, i) for i, pk in enumerate(pk_list)])  
#         ordering = 'CASE %s END' % clauses  
#         items = Article.objects.filter(pk__in=pk_list).extra(  
#                    select={'ordering': ordering}, order_by=('ordering',))
        serializer = ItemSerializer(items, many=True)
        messages.success(request._request, 
                                 'CSV file successfully uploaded')
        return Response(serializer.data)


########################################## LOAN ###########################################    
class APILoanList(APIView):
    permission_classes = (IsAdminOrUser,)
    
    def get(self, request, format=None):
        if 'item_name' in request.data: # these nested ifs allow for a user to filter based on a regular item_name string (not an item_id) using the item_name field, use item_name_id to filter by id
            request.data['item_name'] = Item.objects.get(item_name=request.data['item_name'])
        loans = Loan.objects.filter(**request.data)
        if not User.objects.get(username=request.user.username).is_staff:
            loans = Loan.objects.filter(user_name = request.user.username,**request.data)
        serializer = FullLoanSerializer(loans, many=True)
        return Response(serializer.data)

class APILoan(APIView):
    permission_classes = (IsAdmin,)
    serializer_class = LoanSerializer
    
    def put(self, request, pk, format=None): # edit loan
        loan = Loan.objects.get(loan_id=pk)
        orig_quant = loan.total_quantity
        new_quant = int(request.data['total_quantity'])
        item = loan.item_name
        quantity_changed = new_quant - orig_quant
        item_quant = item.quantity - quantity_changed
        serializer = LoanSerializer(loan, data=request.data, partial=True)
        if item_quant < 0 or new_quant < 1:
            return Response(status=status.HTTP_304_NOT_MODIFIED)
        item.quantity = item_quant
        item.save()
        if serializer.is_valid():
            serializer.save()
            Log.objects.create(request_id=loan.loan_id, item_id= item.item_id, item_name = item.item_name, initiating_user=request.user.username, 
                                   nature_of_event="Edit", affected_user=loan.user_name, change_occurred="Edited loan for " + item.item_name + ".")
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
    def delete(self, request, pk, format=None): # check in loan
        loan = Loan.objects.get(loan_id=pk)
        requested_quant = int(request.data['check_in'])   
        if requested_quant > 0 and requested_quant <= loan.total_quantity:
            loan.total_quantity = loan.total_quantity - requested_quant
            item = loan.item_name
            item.quantity = item.quantity + requested_quant
            loan.save()
            item.save()
            Log.objects.create(request_id=loan.loan_id, item_id= item.item_id, item_name = item.item_name, initiating_user=request.user.username, 
                                   nature_of_event="Check In", affected_user=loan.user_name, change_occurred="Checked in " + str(requested_quant) + " instances.")
            serializer = LoanSerializer(loan, data={'total_quantity':loan.total_quantity}, partial=True)
            if serializer.is_valid():
                serializer.save()
                if loan.total_quantity == 0:
                    loan.delete()
                return Response(serializer.data)
        return Response(status=status.HTTP_400_BAD_REQUEST)
        
    def post(self, request, pk, format=None): # convert loan
        loan = Loan.objects.get(loan_id=pk)
        admin_name = request.user.username
        user_name = loan.user_name
        item = loan.item_name
        comment = loan.comment
        time_disbursed = timezone.localtime(timezone.now())
        quantity_disbursed = int(request.data['convert'])
        if quantity_disbursed <= loan.total_quantity and quantity_disbursed > 0:
            loan.total_quantity = loan.total_quantity - quantity_disbursed
            loan.save()
            disbursement = Disbursement(admin_name=admin_name, user_name=user_name, orig_request=loan.orig_request, item_name=item, comment=comment, total_quantity=quantity_disbursed, time_disbursed=time_disbursed)
            disbursement.save()
            Log.objects.create(request_id=disbursement.disburse_id, item_id= item.item_id, item_name = item.item_name, initiating_user=request.user.username, 
                                   nature_of_event="Disburse", affected_user=loan.user_name, change_occurred="Converted loan of " + str(quantity_disbursed) + " items to disburse.")
            if loan.total_quantity == 0:
                loan.delete()
            serializer = DisbursementSerializer(disbursement, data={'admin_name':admin_name,'comment':comment, 'total_quantity':quantity_disbursed, 'time_disbursed':time_disbursed}, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(status=status.HTTP_400_BAD_REQUEST)
        
########################################## Subscription ###########################################    

class APISubscriptionDetail(APIView):
    """
    Subscribe to emails
    """
    permission_classes = (IsAdminOrManager,)
    
    def get_object(self, pk):
        try:
            return SubscribedUsers.objects.get_or_create(user=pk)
        except User.DoesNotExist:
            raise Http404
    
    def post(self, request, pk, format=None):
        user, created = self.get_object(pk)
        serializer = SubscribeSerializer(user, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def delete(self, request, pk, format=None):
        user, created = self.get_object(pk)
        user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    
########################################## Email Body ###########################################    

class APILoanEmailBody(APIView):
    """
    Loan body 
    """
    permission_classes = (IsAdminOrManager,)
    
    def post(self, request, format=None):
        LoanReminderEmailBody.objects.all().delete()
        serializer = LoanReminderBodySerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def delete(self, request, format=None):
        LoanReminderEmailBody.objects.all().delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    
class APILoanEmailConfigureDates(APIView):
    """
    Loan send dates 
    """
    permission_classes = (IsAdminOrManager,)
    
    def get(self, request, format=None):
        serializer = LoanSendDatesSerializer(LoanSendDates.objects.all(), many=True)
        return Response(serializer.data)
    
    def post(self, request, format=None):
        #LoanSendDates.objects.all().delete()
        serializer = LoanSendDatesSerializer(data=request.data, many=True)
        if serializer.is_valid():
            serializer.save()
            for date in serializer.data:
                day = datetime.strptime(date['date'], "%Y-%m-%d")
                task_email.apply_async(eta=day+timedelta(hours=12))
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class APILoanEmailClearDates(APIView):
    """
    Clear all loan dates
    """
    def delete(self, request, format=None):
        celery_app.control.purge()
        LoanSendDates.objects.all().delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
        
    
    