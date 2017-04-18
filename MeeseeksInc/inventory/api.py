from datetime import date, datetime, timedelta
import json
import sys

from django.contrib import messages
from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist
from django.core.mail import EmailMessage
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models.expressions import F
from django.db.models.query_utils import Q
from django.http.response import Http404, HttpResponse
from django.shortcuts import render, redirect, render_to_response
from django.template.loader import render_to_string
from django.utils import timezone
from django.views.generic.base import View
import django_filters
from django_filters.filters import ModelChoiceFilter
from django_filters.rest_framework.filterset import FilterSet
from rest_framework import status
import rest_framework
from rest_framework.generics import ListCreateAPIView, ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from MeeseeksInc.celery import app as celery_app
from custom_admin.tasks import loan_reminder_email as task_email
from inventory.models import Asset
from inventory.permissions import IsAdminOrUser, IsAtLeastUser, \
    IsAdminOrManager, AdminAllManagerNoDelete, IsAdmin
from inventory.serializers import ItemSerializer, RequestSerializer, \
    RequestUpdateSerializer, RequestAcceptDenySerializer, RequestPostSerializer, \
    DisbursementSerializer, DisbursementPostSerializer, UserSerializer, \
    GetItemSerializer, TagSerializer, CustomFieldSerializer, CustomValueSerializer, \
    LogSerializer, MultipleRequestPostSerializer, LoanUpdateSerializer, FullLoanSerializer, LoanConvertSerializer, \
    SubscribeSerializer, LoanPostSerializer, LoanReminderBodySerializer, LoanSendDatesSerializer, LoanCheckInSerializer, \
    LoanCheckInWithAssetSerializer, AddAssetsSerializer, AssetSerializer, LoanBackfillPostSerializer, BackfillAcceptDenySerializer, AssetCustomFieldSerializer, AssetWithCustomFieldSerializer, FullCustomFieldSerializer

from .models import Request, Item, Disbursement, Custom_Field, Custom_Field_Value, Tag, Log, Loan, SubscribedUsers, EmailPrependValue, \
    LoanReminderEmailBody, LoanSendDates, Asset_Custom_Field_Value


def get_host(request):
    return 'http://' + request.META.get('HTTP_HOST')

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
#         print('post of api item list')
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
                for field in Custom_Field.objects.filter(field_kind='Item'):
                    value = next((x for x in custom_field_values if x['field_name'] == field.field_name), None) 
                    if value is not None:
                        custom_val = Custom_Field_Value(item=item, field=field)
                        if value['value']=='':
                            continue
                        if field.field_type == 'Short' and len(value['value'])<=400 or \
                            field.field_type == 'Long' and len(value['value'])<=1000:
                            custom_val.value = value['value']
                        if field.field_type == 'Int':
                            try:
                                int(value['value'])
                                custom_val.value = value['value']
                            except ValueError:
                                return Response("value needs to be an integer", status=status.HTTP_400_BAD_REQUEST)
                        if field.field_type == 'Float':
                            try:
                                float(value['value'])
                                custom_val.value = value['value']
                            except ValueError:
                                return Response("value needs to be a float", status=status.HTTP_400_BAD_REQUEST)
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
        print('item detail put')
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
            print(request.data)
            if custom_field_values is not None:
                for field in Custom_Field.objects.filter(field_kind='Item'):
                    value = next((x for x in custom_field_values if x['field_name'] == field.field_name), None) 
                    if value is not None:
                        if Custom_Field_Value.objects.filter(item = item, field = field).exists():
                            custom_val = Custom_Field_Value.objects.get(item = item, field = field)
                        else:
                            custom_val = Custom_Field_Value(item=item, field=field)
                        if value['value']=='':
                            continue
                        if field.field_type == 'Short' and len(value['value'])<=400 or \
                            field.field_type == 'Long' and len(value['value'])<=1000:
                            custom_val.value = value['value']
                        if field.field_type == 'Int':
                            try:
                                int(value['value'])
                                custom_val.value = value['value']
                            except ValueError:
                                return Response("value needs to be an integer", status=status.HTTP_400_BAD_REQUEST)
                        if field.field_type == 'Float':
                            try:
                                float(value['value'])
                                custom_val.value = value['value']
                            except ValueError:
                                return Response("value needs to be a float", status=status.HTTP_400_BAD_REQUEST)
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
        fields = ['status', 'type']
       
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
            item = Item.objects.get(item_name = indiv_request.item_name.item_name)
                # check if stock less than minimum stock 
            if (item.threshold_enabled and item.threshold_quantity > item.quantity):
                #send email
                try:
                    prepend = EmailPrependValue.objects.all()[0].prepend_text+ ' '
                except (ObjectDoesNotExist, IndexError) as e:
                    prepend = ''
                subject = prepend + 'Below Minimum Stock'
                to = []
                for user in SubscribedUsers.objects.all():
                    to.append(user.email)
                from_email='noreply@duke.edu'
                ctx = {
                    'user':'user',
                    'item':item.item_name,
                    'quantity':item.quantity, 
                }
                message=render_to_string('inventory/belowthreshold_email.txt', ctx)
                EmailMessage(subject, message, bcc=to, from_email=from_email).send()  
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
                                            total_quantity=indiv_request.request_quantity, comment=comment, time_loaned=timezone.localtime(timezone.now()), )    
                loan.save()
                Log.objects.create(request_id=loan.loan_id, item_id= item.item_id, item_name = item.item_name, initiating_user=request.user, 
                                   nature_of_event="Approve", affected_user=indiv_request.user_id, change_occurred="Loaned " + str(indiv_request.request_quantity))
            # change status of request to approved
            if serializer.is_valid():
                serializer.save(status="Approved")
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


class APIApproveRequestWithAssets(APIView):
    """
    approve a request with assets and an additional comment.
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
        serializer = RequestAcceptDenySerializer(indiv_request, data={'comment': request.data['comment']}, partial=True)
        item = Item.objects.get(item_name = indiv_request.item_name.item_name)
        comment = request.data['comment']
        asset_ids = request.data['asset_ids']
        if item.quantity >= indiv_request.request_quantity:
            # decrement quantity in item
            item.quantity = F('quantity')-indiv_request.request_quantity
            item.save()
            if indiv_request.type == 'Dispersal':
                disbursement = Disbursement(orig_request=indiv_request, admin_name=request.user.username, user_name=indiv_request.user_id, item_name=indiv_request.item_name, comment=comment,
                                            total_quantity=indiv_request.request_quantity, time_disbursed=timezone.localtime(timezone.now()))
                disbursement.save()
                for asset_id in asset_ids:
                    asset = Asset.objects.get(asset_id=asset_id)
                    asset.disbursement = disbursement
                    asset.save()
                    Log.objects.create(request_id=disbursement.disburse_id, item_id= item.item_id, item_name = item.item_name, initiating_user=request.user, 
                                   nature_of_event="Approve", affected_user=indiv_request.user_id, change_occurred="Disbursed asset tag " + asset_id)        
            else:
                loan = Loan(orig_request=indiv_request, admin_name=request.user.username, user_name=indiv_request.user_id, item_name=indiv_request.item_name, comment=comment,
                                            total_quantity=indiv_request.request_quantity, time_loaned=timezone.localtime(timezone.now()))
                loan.save()
                for asset_id in asset_ids:
                    asset = Asset.objects.get(asset_id=asset_id)
                    asset.loan = loan
                    asset.save()
                    Log.objects.create(request_id=loan.loan_id, item_id= item.item_id, item_name = item.item_name, initiating_user=request.user, 
                                   nature_of_event="Approve", affected_user=indiv_request.user_id, change_occurred="Loaned asset tag " + asset_id)
            if serializer.is_valid():
                serializer.save(status="Approved")
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
                item_to_disburse.quantity = item_to_disburse.quantity-int(request.data.get('total_quantity'))
                item_to_disburse.save()
                item_to_disburse = self.get_object(pk)
                # check if stock less than minimum stock 
                if (item_to_disburse.threshold_enabled and item_to_disburse.threshold_quantity > item_to_disburse.quantity):
                    #send email
                    try:
                        prepend = EmailPrependValue.objects.all()[0].prepend_text+ ' '
                    except (ObjectDoesNotExist, IndexError) as e:
                        prepend = ''
                    subject = prepend + 'Below Minimum Stock'
                    to = []
                    for user in SubscribedUsers.objects.all():
                            to.append(user.email)
                    from_email='noreply@duke.edu'
                    ctx = {
                        'user':'user',
                        'item':item_to_disburse.item_name,
                        'quantity':item_to_disburse.quantity, # shouldn't this be quantity given? so int(request.data.get('total_quantity'))
                    }
                    message=render_to_string('inventory/belowthreshold_email.txt', ctx)
                    EmailMessage(subject, message, bcc=to, from_email=from_email).send() 
                serializer.save(item_name=Item.objects.get(item_id=pk))
                data = serializer.data
                recipient = data['user_name']
                quantity  = data['total_quantity']
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
                to = [User.objects.get(username = recipient).email]
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
    serializer_class = FullCustomFieldSerializer
    
    def get(self, request, format=None):
        if self.request.user.is_staff:
            fields = Custom_Field.objects.all()
            serializer = FullCustomFieldSerializer(fields, many=True)
            return Response(serializer.data)
        else:
            fields = Custom_Field.objects.filter(is_private = False)
            serializer = FullCustomFieldSerializer(fields, many=True)
            return Response(serializer.data)   
        
    def post(self, request, format=None):
        serializer = FullCustomFieldSerializer(data=request.data)
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
    serializer_class = FullCustomFieldSerializer
    
    def get_object(self, pk):
        try:
            return Custom_Field.objects.get(id=pk)
        except Custom_Field.DoesNotExist:
            raise Http404
        
    def get(self, request, pk, format=None):
        if self.request.user.is_staff:
            field = self.get_object(pk)
            serializer = FullCustomFieldSerializer(field)
            return Response(serializer.data)
        else:
            field = self.get_object(pk)
            if not field.is_private:
                serializer = FullCustomFieldSerializer(field, many=True)
                return Response(serializer.data)   
            return Response("Need valid authentication", status=status.HTTP_400_BAD_REQUEST) 
        
    def delete(self, request, pk, format=None):
        field = Custom_Field.objects.get(id = pk)
        Log.objects.create(request_id=None,item_id=None,  item_name="-", initiating_user = request.user, nature_of_event="Delete", 
                                       affected_user='', change_occurred='Deleted ' + field.field_kind + ' Custom Field ' + str(field.field_name))
        field.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    def put(self, request, pk, format=None):            
        if self.request.user.is_staff:
            field = self.get_object(pk)
            orig_type = field.field_type
            serializer = FullCustomFieldSerializer(field,data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                if orig_type != serializer.data['field_type']:
                    field = self.get_object(pk)
                    for value in Asset_Custom_Field_Value.objects.filter(field=field):
                        value.delete()
                    for value in Custom_Field_Value.objects.filter(field=field):
                        value.delete()    
                Log.objects.create(request_id=None, item_id=None,  item_name="-", initiating_user = request.user, nature_of_event="Edit", 
                                       affected_user='', change_occurred='Edited ' + field.field_kind + ' Custom Field ' + str(field.field_name))
                return Response(serializer.data)
            else:
                return Response(serializer.data,status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response(status=status.HTTP_400_BAD_REQUEST)

########################################## Bulk Upload ########################################### 
class ItemUpload(APIView):
    """
    Uploading items via API
    """
    def errorHandling(self, request, message, createdItems):
        if createdItems:
            for createdItem in createdItems:
                createdItem.delete()
        messages.error(request._request, message)
        return Response(message, status=status.HTTP_400_BAD_REQUEST)
    
    
    ## CHECK asset status. if N then just item, if F then first in asset 
    ## if no F but has assets, check if item already exists. if not then throw error
    ## if F check is OK and Y is there, then this is an asset - only item name & asset tag & per-asset custom fields can be filled
    ## if something else is filled in this situation, throw error
    def post(self, request, *args, **kwargs):
        print(request.POST)
        csvData = request.POST.getlist('data[]')
        headerMap = {}
        customFieldMap = {}
        headers = csvData[0].split(',')
        custom_fields = Custom_Field.objects.filter(field_kind='Item')
        for i, header in enumerate(headers):
            if not (header.lower() == "item name" or header.lower() == "quantity" or header.lower() == "model number" or header.lower() =="description" or header.lower() == "tags"):
                # ERROR CHECK, make sure the custom field names are correct 
                if not any(field.field_name == header for field in custom_fields):
                    if header=='':
                        return self.errorHandling(request, 'field (empty string) does not exist. make sure you don\'t have an extra comma', [])
                    return self.errorHandling(request, 'field ' + header + ' does not exist. check the header', [])
                customFieldMap[header.lower()] = i
            else:
                headerMap[header.lower()] = i    
            
        # ERROR CHECK, make sure that item name and quantity headers exist
        if not "item name" in headerMap:
            return self.errorHandling(request, '"Item Name" does not exist in header', [])
        if not "quantity" in headerMap:
            return self.errorHandling(request, '"Quantity" does not exist in header', [])
        
        createdItems = []
        for i, csvRow in enumerate(csvData[1:]):
            row = csvRow.split(',')
            if headerMap["item name"] >= len(row) or row[headerMap["item name"]]=='':
                return self.errorHandling(request, 'value of "Item Name" does not exist in row ' + str(i+1), createdItems)
            if headerMap["quantity"] >= len(row) or row[headerMap["quantity"]]=='':
                return self.errorHandling(request, 'value of "Quantity" does not exist in row ' + str(i+1), createdItems)
            if not row[headerMap["quantity"]].isdigit():
                return self.errorHandling(request, 'value of "Quantity" is not an integer in row' + str(i+1), createdItems)          
            if int(row[headerMap["quantity"]])<0:
                return self.errorHandling(request, 'value of "Quantity" is less than 0 in row ' + str(i+1), createdItems)           
            if "model number" in headerMap and headerMap["model number"] >= len(row):
                return self.errorHandling(request, 'value of "Model Number" does not exist in row ' + str(i+1), createdItems)
            if "description" in headerMap and headerMap["description"] >= len(row):
                return self.errorHandling(request, 'value of "Description" does not exist in row ' + str(i+1), createdItems)
            
            existingItem = Item.objects.filter(item_name=row[headerMap["item name"]]).count()
            if existingItem>0:
                return self.errorHandling(request, "Item " + row[headerMap["item name"]] + " already exists", createdItems)
            item = Item(item_name=row[headerMap["item name"]], quantity=row[headerMap["quantity"]], model_number=row[headerMap["model number"]] if "model number" in headerMap else "", description=row[headerMap["description"]] if "description" in headerMap else "")
            
            item.save()
            createdItems.append(item)
            # add to tags
            if "tags" in headerMap:
                if headerMap["tags"] >= len(row):
                    return self.errorHandling(request, 'value of "tags" does not exist in row ' + str(i+1), createdItems)
                for tag in row[headerMap["tags"]].split('/'):
                    if not tag == '':
                        t = Tag(tag=tag)
                        t.save(force_insert=True)
                        item.tags.add(t)
                        item.save()
            # add custom fields
            for custom_field, j in customFieldMap.items():
                actual_field = next((x for x in custom_fields if x.field_name.lower() == custom_field), None)
                if j >= len(row):
                    return self.errorHandling(request, 'value of ' + actual_field.field_name + ' does not exist in row ' + str(i+1), createdItems)
                if actual_field.field_type == "Short":
                    if len(row[j])<=400:
                        value = Custom_Field_Value(item=item, field=actual_field, value=row[j])
                        value.save()
                    else:
                        return self.errorHandling(request, actual_field.field_name + " at row " + str(i+1) + " is not short text. Length is too long", createdItems) 
                elif actual_field.field_type == "Long":
                    if len(row[j])<=1000:
                        value = Custom_Field_Value(item=item, field=actual_field, value=row[j])
                        value.save()
                    else:
                        return self.errorHandling(request, actual_field.field_name + " at row " + str(i+1) + " is not long text. Length is too long", createdItems)  
                elif actual_field.field_type == "Int":
                    try:
                        int(row[j])
                        value = Custom_Field_Value(item=item, field=actual_field, value=int(row[j]))
                        value.save()
                    except ValueError:
                        if row[j] == "":
                            continue
                        else:
                            return self.errorHandling(request, actual_field.field_name + " at row " + str(i+1) + " is not an integer", createdItems) 
                elif actual_field.field_type == "Float":
                    try:
                        float(row[j])
                        value = Custom_Field_Value(item=item, field=actual_field, value=float(row[j]))
                        value.save()
                    except ValueError:
                        if row[j] == "":
                            continue
                        else:
                            return self.errorHandling(request, actual_field.field_name + " at row " + str(i+1) + " is not a float", createdItems)
        items = {}
        for item in createdItems:
            Log.objects.create(request_id=None, item_id=item.item_id, item_name = item.item_name, initiating_user=request.user, nature_of_event="Create", 
                       affected_user='', change_occurred="Created item " + str(item.item_name))
        serializer = ItemSerializer(items, many=True)
        messages.success(request._request, 
                                 'CSV file successfully uploaded')
        return Response(serializer.data)

class AssetUpload(APIView):
    """
    Uploading assets via API
    """
    def errorHandling(self, request, message, item, createdAssets):
        if item:
            item.delete()
        if createdAssets:
            for createdAsset in createdAssets:
                createdAsset.delete()
        messages.error(request._request, message)
        return Response(message, status=status.HTTP_400_BAD_REQUEST)
    
    
    ## CHECK asset status. if N then just item, if F then first in asset 
    ## if no F but has assets, check if item already exists. if not then throw error
    ## if F check is OK and Y is there, then this is an asset - only item name & asset tag & per-asset custom fields can be filled
    ## if something else is filled in this situation, throw error
    def post(self, request, *args, **kwargs):
        csvData = request.POST.getlist('data[]')
        item_name = request.POST.get('item_name')
        headerMap = {}
        customFieldMap = {}
        headers = csvData[0].split(',')
        custom_fields = Custom_Field.objects.filter(field_kind="Asset")
        for i, header in enumerate(headers):
            if not (header.lower() == "asset tag"):
                # ERROR CHECK, make sure the custom field names are correct 
                if not any(field.field_name == header for field in custom_fields):
                    if header=='':
                        return self.errorHandling(request, 'field (empty string) does not exist. make sure you don\'t have an extra comma', [])
                    return self.errorHandling(request, 'field ' + header + ' does not exist. check the header', [])
                customFieldMap[header.lower()] = i
            else:
                headerMap[header.lower()] = i    
            
        # ERROR CHECK, make sure that item name and quantity headers exist
        if not "asset tag" in headerMap:
            return self.errorHandling(request, '"Asset Tag" does not exist in header', [])
        
        item = []
        newItem = False
        createdAssets = []
        # CHECK IF ITEM EXISTS, IF NOT CREATE THE ITEM WITH THE # OF ASSETS
        if not Item.objects.filter(item_name = item_name).count()>0:
            item = Item(item_name=item_name, quantity=len(csvData[1:]), is_asset=True)
            item.save()
            newItem = True
        else:
            item = Item.objects.get(item_name = item_name)
            if not item.is_asset:
                return self.errorHandling(request, 'This item does not track assets.', None)
        
        for i, csvRow in enumerate(csvData[1:]):
            row = csvRow.split(',')
            if headerMap["asset tag"] >= len(row) or row[headerMap["asset tag"]]=='':
                return self.errorHandling(request, 'value of "Asset Tag" does not exist in row ' + str(i+1), item, createdAssets)
            
            existingAsset = Asset.objects.filter(item=item, asset_id=row[headerMap["asset tag"]]).count()
            if existingAsset>0:
                return self.errorHandling(request, "Asset " + row[headerMap["asset tag"]] + " already exists", item, createdAssets)
            asset = Asset(asset_tag=row[headerMap["asset tag"]],item=item)
            asset.save()
            createdAssets.append(asset)

            # add asset custom fields
            for custom_field, j in customFieldMap.items():
                actual_field = next((x for x in custom_fields if x.field_name.lower() == custom_field), None)
                if j >= len(row):
                    return self.errorHandling(request, 'value of ' + actual_field.field_name + ' does not exist in row ' + str(i+1), item, createdAssets)
                if actual_field.field_type == "Short":
                    if len(row[j])<=400:
                        value = Asset_Custom_Field_Value(asset=asset, field=actual_field, value=row[j])
                        value.save()
                    else:
                        return self.errorHandling(request, actual_field.field_name + " at row " + str(i+1) + " is not short text. Length is too long", item, createdAssets) 
                elif actual_field.field_type == "Long":
                    if len(row[j])<=1000:
                        value = Asset_Custom_Field_Value(asset=asset, field=actual_field, value=row[j])
                        value.save()
                    else:
                        return self.errorHandling(request, actual_field.field_name + " at row " + str(i+1) + " is not long text. Length is too long", item, createdAssets)  
                elif actual_field.field_type == "Int":
                    try:
                        int(row[j])
                        value = Asset_Custom_Field_Value(asset=asset, field=actual_field, value=int(row[j]))
                        value.save()
                    except ValueError:
                        if row[j] == "":
                            continue
                        else:
                            return self.errorHandling(request, actual_field.field_name + " at row " + str(i+1) + " is not an integer", item, createdAssets) 
                elif actual_field.field_type == "Float":
                    try:
                        float(row[j])
                        value = Asset_Custom_Field_Value(asset=asset, field=actual_field, value=float(row[j]))
                        value.save()
                    except ValueError:
                        if row[j] == "":
                            continue
                        else:
                            return self.errorHandling(request, actual_field.field_name + " at row " + str(i+1) + " is not a float", item, createdAssets)
        
        if not newItem:
            item.quantity = item.quantity + len(csvData[1:]) # add to item quantity
            item.save()
        for asset in createdAssets:
            Log.objects.create(request_id=None, item_id=asset.item.item_id, item_name = asset.item.item_name, initiating_user=request.user, nature_of_event="Create", 
                       affected_user='', change_occurred="Created asset with asset tag " + str(asset.asset_tag) + " for " + str(asset.item.item_name))
        serializer = AssetSerializer(createdAssets, many=True)
        messages.success(request._request, 
                                 'CSV file successfully uploaded')
        return Response(serializer.data)
########################################## LOAN ###########################################    
class LoanFilter(FilterSet):
    class Meta:
        model = Loan
        fields = ['loan_id','admin_name', 'user_name','item_name','orig_request','total_quantity','comment','time_loaned','status']

class APILoanList(ListAPIView): #FILTER LOANS
    permission_classes = (IsAdminOrUser,)
    serializer_class = FullLoanSerializer
    filter_class = LoanFilter
    model = Loan
    queryset = Loan.objects.all()
    
    def get(self, request, format=None):
        loans = [];
        if User.objects.get(username=request.user.username).is_staff:
            loans = self.filter_queryset(Loan.objects.all())
        else:
            loans = self.filter_queryset(Loan.objects.filter(user_id=request.user.username))
        serializer = FullLoanSerializer(loans, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

class APILoanUpdate(APIView): #EDIT LOAN
    permission_classes = (IsAdminOrManager,)
    serializer_class = LoanUpdateSerializer
    
    def get(self, request, pk, format=None):
        loan = Loan.objects.get(loan_id = pk)
        serializer = FullLoanSerializer(loan)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    def put(self, request, pk, format=None): #find way to allow no total quant, check on gui, apigui, and command line
        loan = Loan.objects.get(loan_id=pk)
        serializer = LoanUpdateSerializer(loan,data=request.data, partial=True)
        if serializer.is_valid():
            orig_quant = loan.total_quantity
            new_requested_quant = int(request.data['total_quantity'])
            quantity_changed = new_requested_quant - orig_quant
            item = loan.item_name
            new_item_quant = item.quantity - quantity_changed
            if new_item_quant < 0:
                return Response(status=status.HTTP_304_NOT_MODIFIED)
            if new_requested_quant < 1:
                return Response(status=status.HTTP_400_BAD_REQUEST)
            item.quantity = new_item_quant
            item.save()
            change_list=[]
            if int(serializer.validated_data['total_quantity']) != int(loan.total_quantity):
                change_list.append(('total quantity', loan.total_quantity, serializer.validated_data['total_quantity']))
            if serializer.validated_data['comment'] != loan.comment:
                change_list.append(('comment', loan.comment, serializer.validated_data['comment']))
            serializer.save()
            Log.objects.create(request_id=loan.loan_id, item_id= item.item_id, item_name = item.item_name, initiating_user=request.user.username, 
                                   nature_of_event="Edit", affected_user=loan.user_name, change_occurred="Edited loan for " + item.item_name + ".")
            
            try:
                prepend = EmailPrependValue.objects.all()[0].prepend_text+ ' '
            except (ObjectDoesNotExist, IndexError) as e:
                prepend = ''
            subject = prepend + 'Loan edit'
            to = [User.objects.get(username=loan.user_name).email]
            from_email='noreply@duke.edu'
            ctx = {
                'user':request.user,
                'changes':change_list,
            }
            message=render_to_string('inventory/request_edit_email.txt', ctx)
            if len(change_list)>0:
                EmailMessage(subject, message, bcc=to, from_email=from_email).send()
                
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
class APILoanCheckIn(APIView): #CHECK IN LOAN
    permission_classes = (IsAdminOrManager,)
    serializer_class = LoanCheckInSerializer
    
    def get(self, request, pk, format=None):
        loan = Loan.objects.get(loan_id = pk)
        serializer = FullLoanSerializer(loan)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    def post(self, request, pk, format=None):
        loan = Loan.objects.get(loan_id=pk)
        serializer = LoanCheckInSerializer(data=request.data) 
        if serializer.is_valid():
            requested_checkin_quant = int(request.data['check_in'])   
            original_quantity = loan.total_quantity
            if requested_checkin_quant > 0 and requested_checkin_quant <= loan.total_quantity:
                loan.total_quantity = loan.total_quantity - requested_checkin_quant
                item = loan.item_name
                item.quantity = item.quantity + requested_checkin_quant
                item.save()
                loan.save()
                Log.objects.create(request_id=loan.loan_id, item_id= item.item_id, item_name = item.item_name, initiating_user=request.user.username, 
                                       nature_of_event="Check In", affected_user=loan.user_name, change_occurred="Checked in " + str(requested_checkin_quant) + " instances.")
                    
                try:
                    prepend = EmailPrependValue.objects.all()[0].prepend_text+ ' '
                except (ObjectDoesNotExist, IndexError) as e:
                    prepend = ''
                subject = prepend + 'Loan checkin'
                to = [User.objects.get(username=loan.user_name).email]
                from_email='noreply@duke.edu'
                checked_in = [(loan.item_name, requested_checkin_quant, original_quantity)]
                ctx = {
                    'user':request.user,
                    'checked_in':checked_in,
                }
                message=render_to_string('inventory/loan_checkin_email.txt', ctx)
                EmailMessage(subject, message, bcc=to, from_email=from_email).send()

                if loan.total_quantity == 0:
                    loan.status = 'Checked In'
                    loan.save()
                return redirect(get_host(request)+'/api/loan/checkin/'+pk+'/') # redirect to original url in order to have laon data returned with check in serializer to fill in
        return Response(status=status.HTTP_400_BAD_REQUEST)

class APILoanCheckInWithAssets(APIView): #CHECK IN LOAN
    permission_classes = (IsAdminOrManager,)
    serializer_class = LoanCheckInWithAssetSerializer
    
    def post(self, request, pk, format=None):
        loan = Loan.objects.get(loan_id=pk)
        checked_in_assets = [x for x in request.data['asset_ids'] if x]
        original_quantity = loan.total_quantity
        if len(checked_in_assets) > 0 and len(checked_in_assets) <= loan.total_quantity:
            loan.total_quantity = loan.total_quantity - len(checked_in_assets)
            item = loan.item_name
            item.quantity = item.quantity + len(checked_in_assets)
            item.save()
            loan.save()
            for asset_id in checked_in_assets:
                asset = Asset.objects.get(asset_id=asset_id)
                asset.loan = None
                asset.save()
            Log.objects.create(request_id=loan.loan_id, item_id= item.item_id, item_name = item.item_name, initiating_user=request.user.username, 
                                   nature_of_event="Check In", affected_user=loan.user_name, change_occurred="Checked in " + str(len(checked_in_assets)) + " instances.")
            try:
                prepend = EmailPrependValue.objects.all()[0].prepend_text+ ' '
            except (ObjectDoesNotExist, IndexError) as e:
                prepend = ''
            subject = prepend + 'Loan checkin'
            to = [User.objects.get(username=loan.user_name).email]
            from_email='noreply@duke.edu'
            checked_in = [(loan.item_name, len(checked_in_assets), original_quantity)]
            ctx = {
                'user':request.user,
                'checked_in':checked_in,
            }
            message=render_to_string('inventory/loan_checkin_email.txt', ctx)
            EmailMessage(subject, message, bcc=to, from_email=from_email).send()

            if loan.total_quantity == 0:
                loan.status = 'Checked In'
                loan.save()
            return redirect(get_host(request)+'/api/loan/checkin/'+pk+'/') # redirect to original url in order to have laon data returned with check in serializer to fill in
        return Response(status=status.HTTP_400_BAD_REQUEST)
    

class APILoanConvert(APIView): #CONVERT LOAN
    permission_classes = (IsAdminOrManager,)
    serializer_class = LoanConvertSerializer  
    
    def get(self, request, pk, format=None):
        loan = Loan.objects.get(loan_id = pk)
        serializer = FullLoanSerializer(loan)
        return Response(serializer.data, status=status.HTTP_200_OK)  
  
    def post(self, request, pk, format=None): 
        loan = Loan.objects.get(loan_id=pk)
        admin_name = request.user.username
        user_name = loan.user_name
        item = loan.item_name
        comment = loan.comment
        time_disbursed = timezone.localtime(timezone.now())
        serializer = LoanConvertSerializer(data=request.data) 
        print(request.data)
        if serializer.is_valid():
            quantity_disbursed = int(request.data['number_to_convert'])
            if quantity_disbursed <= loan.total_quantity and quantity_disbursed > 0:
                original_quantity = loan.total_quantity
                loan.total_quantity = loan.total_quantity - quantity_disbursed
                loan.save()
                disbursement = Disbursement(admin_name=admin_name, user_name=user_name, orig_request=loan.orig_request, item_name=item, comment=comment, total_quantity=quantity_disbursed, time_disbursed=time_disbursed)
                disbursement.save()
                Log.objects.create(request_id=disbursement.disburse_id, item_id= item.item_id, item_name = item.item_name, initiating_user=request.user.username, 
                                   nature_of_event="Disburse", affected_user=loan.user_name, change_occurred="Converted loan of " + str(quantity_disbursed) + " items to disburse.")
                if loan.total_quantity == 0:
                    loan.status = 'Checked In'
                    loan.save()

                try:
                    prepend = EmailPrependValue.objects.all()[0].prepend_text+ ' '
                except (ObjectDoesNotExist, IndexError) as e:
                    prepend = ''
                subject = prepend + 'Loan convert'
                to = [User.objects.get(username=loan.user_name).email]
                from_email='noreply@duke.edu'
                convert=[(loan.item_name, quantity_disbursed, original_quantity)]
                ctx = {
                    'user':request.user,
                    'convert':convert,
                }
                message=render_to_string('inventory/convert_email.txt', ctx)
                EmailMessage(subject, message, bcc=to, from_email=from_email).send()
           
                return redirect(get_host(request)+'/api/loan/convert/'+pk+'/') # redirect to original url in order to have laon data returned with check in serializer to fill in
        else:
            print(serializer.errors)
        return Response(status=status.HTTP_400_BAD_REQUEST)
    
class APILoanConvertWithAssets(APIView): #CONVERT LOAN
    permission_classes = (IsAdminOrManager,)
    serializer_class = LoanConvertSerializer  
    
    def post(self, request, pk, format=None): 
        loan = Loan.objects.get(loan_id=pk)
        admin_name = request.user.username
        user_name = loan.user_name
        item = loan.item_name
        comment = loan.comment
        time_disbursed = timezone.localtime(timezone.now())
        converted_assets = [x for x in request.data['asset_ids'] if x]
        quantity_disbursed = len(converted_assets)
        if quantity_disbursed <= loan.total_quantity and quantity_disbursed > 0:
            original_quantity = loan.total_quantity
            loan.total_quantity = loan.total_quantity - quantity_disbursed
            loan.save()
            disbursement = Disbursement(admin_name=admin_name, user_name=user_name, orig_request=loan.orig_request, item_name=item, comment=comment, total_quantity=quantity_disbursed, time_disbursed=time_disbursed)
            disbursement.save()
            for asset_id in converted_assets:
                asset = Asset.objects.get(asset_id=asset_id)
                asset.loan = None
                asset.disbursement = disbursement
                asset.save()
            Log.objects.create(request_id=disbursement.disburse_id, item_id= item.item_id, item_name = item.item_name, initiating_user=request.user.username, 
                               nature_of_event="Disburse", affected_user=loan.user_name, change_occurred="Converted loan of " + str(quantity_disbursed) + " items to disburse.")
            if loan.total_quantity == 0:
                loan.status = 'Checked In'
                loan.save()

            try:
                prepend = EmailPrependValue.objects.all()[0].prepend_text+ ' '
            except (ObjectDoesNotExist, IndexError) as e:
                prepend = ''
            subject = prepend + 'Loan convert'
            to = [User.objects.get(username=loan.user_name).email]
            from_email='noreply@duke.edu'
            convert=[(loan.item_name, quantity_disbursed, original_quantity)]
            ctx = {
                'user':request.user,
                'convert':convert,
            }
            message=render_to_string('inventory/convert_email.txt', ctx)
            EmailMessage(subject, message, bcc=to, from_email=from_email).send()
       
            return redirect(get_host(request)+'/api/loan/convert/'+pk+'/') # redirect to original url in order to have laon data returned with check in serializer to fill in
        return Response(status=status.HTTP_400_BAD_REQUEST)
    
class APILoanBackfillPost(ListCreateAPIView):
    '''
    Create a backfill request
    '''
    permission_classes = (IsAtLeastUser,)
    model = Loan
    queryset = Loan.objects.all().exclude(backfill_status="None")
    serializer_class = LoanBackfillPostSerializer
    
    def post(self, request, pk,  format=None):
        loan = Loan.objects.get(loan_id=pk)
        data = request.data.copy()
        serializer = LoanBackfillPostSerializer(loan, data=data, partial=True)
        if serializer.is_valid():
            serializer.save(backfill_status="Requested", backfill_time_requested=timezone.localtime(timezone.now()))
            Log.objects.create(request_id=None, item_id=loan.item_name.item_id, item_name=loan.item_name.item_name, initiating_user=request.user, nature_of_event="Create",
                               affected_user="", change_occurred="Created backfill request for " + str(loan.item_name.item_name))
            try:
                prepend = EmailPrependValue.objects.all()[0].prepend_text+ ' '
            except (ObjectDoesNotExist, IndexError) as e:
                prepend = ''
            subject = prepend + 'Backfill Request'
            to = [User.objects.get(username=loan.user_name).email]
            from_email='noreply@duke.edu'
            ctx = {
                'user':loan.user_name,
                'item_name':loan.item_name.item_name,
                'backfill_quantity':loan.backfill_quantity,
                'loan_quantity':loan.total_quantity, 
            }
            for user in SubscribedUsers.objects.all():
                to.append(user.email)
            message=render_to_string('inventory/backfill_create_email.txt', ctx)
            EmailMessage(subject, message, bcc=to, from_email=from_email).send()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
class APIBackfillNotes(APIView):
    """
    Approve a backfill with optional notes.
    """
    
    permission_classes = (IsAdminOrManager,)
    serializer_class = BackfillAcceptDenySerializer
    
    def get(self, request, pk, format=None):
        loan = Loan.objects.get(loan_id = pk)
        serializer = FullLoanSerializer(loan)
        return Response(serializer.data, status=status.HTTP_200_OK)  
    
    def get_object(self, pk):
        try:
            return Loan.objects.get(loan_id=pk)
        except Loan.DoesNotExist:
            raise Http404
        
    def put(self, request, pk, format=None):
        loan = self.get_object(pk)
        serializer = BackfillAcceptDenySerializer(loan, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_202_ACCEPTED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
class APIApproveBackfill(APIView):
    """
    Approve a backfill with optional notes.
    """
    
    permission_classes = (IsAdminOrManager,)
    serializer_class = BackfillAcceptDenySerializer
    
    def get_object(self, pk):
        try:
            return Loan.objects.get(loan_id=pk)
        except Loan.DoesNotExist:
            raise Http404
        
    def put(self, request, pk, format=None):
        loan = self.get_object(pk)
        if not loan.backfill_status=='Requested':
            return Response("Already approved or denied.", status=status.HTTP_400_BAD_REQUEST)
        serializer = BackfillAcceptDenySerializer(loan, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save(backfill_status="In Transit", backfill_time_requested=timezone.localtime(timezone.now()))
            Log.objects.create(request_id='', item_id=loan.item_name.item_id, item_name = loan.item_name.item_name, initiating_user=request.user, nature_of_event="Approve", 
                       affected_user=loan.user_name, change_occurred="Backfill in transit")
            try:
                prepend = EmailPrependValue.objects.all()[0].prepend_text+ ' '
            except (ObjectDoesNotExist, IndexError) as e:
                prepend = ''
            subject = prepend + 'Backfill Awaiting Arrival'
            to = [User.objects.get(username=loan.user_name).email]
            from_email='noreply@duke.edu'
            ctx = {
                'user':loan.user_name,
                'item_name':loan.item_name.item_name,
                'backfill_quantity':loan.backfill_quantity,
                'loan_quantity':loan.total_quantity, 
            }
            for user in SubscribedUsers.objects.all():
                to.append(user.email)
            message=render_to_string('inventory/backfill_approve_email.txt', ctx)
            EmailMessage(subject, message, bcc=to, from_email=from_email).send()
            return Response(serializer.data, status=status.HTTP_202_ACCEPTED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    
class APIDenyBackfill(APIView):
    """
    Deny a backfill with optional notes.
    """
    permission_classes = (IsAdminOrManager,)
    serializer_class = BackfillAcceptDenySerializer
    
    def get_object(self, pk):
        try:
            return Loan.objects.get(loan_id=pk)
        except Loan.DoesNotExist:
            raise Http404
        
    def put(self, request, pk, format=None):
        loan = self.get_object(pk)
        if not loan.backfill_status=='Requested':
            return Response("Already approved or denied.", status=status.HTTP_400_BAD_REQUEST)
        serializer = BackfillAcceptDenySerializer(loan, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save(backfill_status="Denied", backfill_time_requested=timezone.localtime(timezone.now()))
            Log.objects.create(request_id='', item_id=loan.item_name.item_id, item_name = loan.item_name.item_name, initiating_user=request.user, nature_of_event="Deny", 
                       affected_user=loan.user_name, change_occurred="Backfill denied")
            try:
                prepend = EmailPrependValue.objects.all()[0].prepend_text+ ' '
            except (ObjectDoesNotExist, IndexError) as e:
                prepend = ''
            subject = prepend + 'Backfill Request Denied'
            to = [User.objects.get(username=loan.user_name).email]
            from_email='noreply@duke.edu'
            ctx = {
                'user':loan.user_name,
                'reason':serializer.data['backfill_notes'],
            }
            for user in SubscribedUsers.objects.all():
                to.append(user.email)
            message=render_to_string('inventory/backfill_deny_email.txt', ctx)
            EmailMessage(subject, message, bcc=to, from_email=from_email).send()
            return Response(serializer.data, status=status.HTTP_202_ACCEPTED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    
class APICompleteBackfill(APIView):
    """
    Complete a backfill and disburse the appropriate number of items
    """
    permission_classes = (IsAdminOrManager,)
    serializer_class = BackfillAcceptDenySerializer
    
    def get_object(self, pk):
        try:
            return Loan.objects.get(loan_id=pk)
        except Loan.DoesNotExist:
            raise Http404
        
    def put(self, request, pk, format=None):
        loan = self.get_object(pk)
        if not loan.backfill_status=='In Transit':
            return Response("Must be in transit to complete.", status=status.HTTP_400_BAD_REQUEST)
        serializer = BackfillAcceptDenySerializer(loan, data=request.data, partial=True)
        if serializer.is_valid():
            loan.total_quantity = loan.total_quantity - loan.backfill_quantity
            if loan.total_quantity == 0:
                loan.status = "Backfilled"
            disbursement = Disbursement(admin_name=request.user.username, user_name=loan.user_name, orig_request=loan.orig_request, item_name=loan.item_name, comment="Backfilled Disburse", total_quantity=loan.backfill_quantity, time_disbursed=timezone.localtime(timezone.now()))
            disbursement.save()
            serializer.save(backfill_status="Completed", backfill_time_requested=timezone.localtime(timezone.now()))
            Log.objects.create(request_id='', item_id=loan.item_name.item_id, item_name = loan.item_name.item_name, initiating_user=request.user, nature_of_event="Backfilled", 
                       affected_user=loan.user_name, change_occurred="Backfill completed")
            Log.objects.create(request_id='', item_id=loan.item_name.item_id, item_name = loan.item_name.item_name, initiating_user=request.user, nature_of_event="Disburse", 
                       affected_user=loan.user_name, change_occurred="Disbursed " + str(loan.backfill_quantity) + " due to backfill")
            try:
                prepend = EmailPrependValue.objects.all()[0].prepend_text+ ' '
            except (ObjectDoesNotExist, IndexError) as e:
                prepend = ''
            subject = prepend + 'Backfill Completed'
            to = [User.objects.get(username=loan.user_name).email]
            from_email='noreply@duke.edu'
            ctx = {
                'user':loan.user_name,
                'item_name':loan.item_name.item_name,
                'backfill_quantity':loan.backfill_quantity,
                'loan_quantity':loan.total_quantity, 
            }
            for user in SubscribedUsers.objects.all():
                to.append(user.email)
            message=render_to_string('inventory/backfill_completed_email.txt', ctx)
            EmailMessage(subject, message, bcc=to, from_email=from_email).send()
            return Response(serializer.data, status=status.HTTP_202_ACCEPTED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
class APIFailBackfill(APIView):
    """
    Complete a backfill and disburse the appropriate number of items
    """
    permission_classes = (IsAdminOrManager,)
    serializer_class = BackfillAcceptDenySerializer
    
    def get_object(self, pk):
        try:
            return Loan.objects.get(loan_id=pk)
        except Loan.DoesNotExist:
            raise Http404
        
    def put(self, request, pk, format=None):
        loan = self.get_object(pk)
        if not loan.backfill_status=='In Transit':
            return Response("Must be in transit to complete.", status=status.HTTP_400_BAD_REQUEST)
        serializer = BackfillAcceptDenySerializer(loan, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save(backfill_status="None", backfill_time_requested=timezone.localtime(timezone.now()))
            Log.objects.create(request_id='', item_id=loan.item_name.item_id, item_name = loan.item_name.item_name, initiating_user=request.user, nature_of_event="Deny", 
                       affected_user=loan.user_name, change_occurred="Backfill failed")
            try:
                prepend = EmailPrependValue.objects.all()[0].prepend_text+ ' '
            except (ObjectDoesNotExist, IndexError) as e:
                prepend = ''
            subject = prepend + 'Backfill Failed'
            to = [User.objects.get(username=loan.user_name).email]
            from_email='noreply@duke.edu'
            ctx = {
                'user':loan.user_name,
                'reason':serializer.data['backfill_notes'],
            }
            for user in SubscribedUsers.objects.all():
                to.append(user.email)
            message=render_to_string('inventory/backfill_fail_email.txt', ctx)
            EmailMessage(subject, message, bcc=to, from_email=from_email).send()
            return Response(serializer.data, status=status.HTTP_202_ACCEPTED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class APICompleteBackfillWithAssets(APIView):
    """
    Complete a backfill and disburse the appropriate number of assets
    """
    permission_classes = (IsAdminOrManager,)
    serializer_class = BackfillAcceptDenySerializer
    
    def get_object(self, pk):
        try:
            return Loan.objects.get(loan_id=pk)
        except Loan.DoesNotExist:
            raise Http404
        
    def put(self, request, pk, format=None):
        loan = self.get_object(pk)
        assets = Asset.objects.filter(loan=loan.loan_id)
        if not loan.backfill_status=='In Transit':
            return Response("Must be in transit to complete.", status=status.HTTP_400_BAD_REQUEST)
        serializer = BackfillAcceptDenySerializer(loan, data=request.data, partial=True)
        if serializer.is_valid():
            loan.total_quantity = loan.total_quantity - loan.backfill_quantity
            if loan.total_quantity == 0:
                loan.status = "Backfilled"
            disbursement = Disbursement(admin_name=request.user.username, user_name=loan.user_name, orig_request=loan.orig_request, item_name=loan.item_name, comment="Backfilled Disburse", total_quantity=loan.backfill_quantity, time_disbursed=timezone.localtime(timezone.now()))
            disbursement.save()
            for asset in assets[:loan.backfill_quantity]:
                asset.disbursement = disbursement
                asset.save()
                Log.objects.create(request_id='', item_id=loan.item_name.item_id, item_name = loan.item_name.item_name, initiating_user=request.user, nature_of_event="Disburse", 
                       affected_user=loan.user_name, change_occurred="Disbursed " + str(asset.asset_id) + " due to backfill")
            serializer.save(backfill_status="Completed", backfill_time_requested=timezone.localtime(timezone.now()))
            Log.objects.create(request_id='', item_id=loan.item_name.item_id, item_name = loan.item_name.item_name, initiating_user=request.user, nature_of_event="Backfilled", 
                       affected_user=loan.user_name, change_occurred="Backfill completed")
            try:
                prepend = EmailPrependValue.objects.all()[0].prepend_text+ ' '
            except (ObjectDoesNotExist, IndexError) as e:
                prepend = ''
            subject = prepend + 'Backfill Completed'
            to = [User.objects.get(username=loan.user_name).email]
            from_email='noreply@duke.edu'
            ctx = {
                'user':loan.user_name,
                'item_name':loan.item_name.item_name,
                'backfill_quantity':loan.backfill_quantity,
                'loan_quantity':loan.total_quantity, 
            }
            for user in SubscribedUsers.objects.all():
                to.append(user.email)
            message=render_to_string('inventory/backfill_completed_email.txt', ctx)
            EmailMessage(subject, message, bcc=to, from_email=from_email).send()
            return Response(serializer.data, status=status.HTTP_202_ACCEPTED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)        

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
        else:
            user.delete()
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

########################################## Asset-tracking ###########################################   
class APIItemToAsset(APIView):
    """
    Converts an item to per-asset
    """
    permission_classes = (IsAdmin,)
    
    def get(self, request, pk, format=None):
        item = Item.objects.get(item_id=pk)
        if not Asset.objects.filter(item=pk):
            item.is_asset = True
            item.save()
            for i in range(item.quantity):
                print('asset creating')
                asset = Asset(item=item)
                asset.save()
        serializer = AssetSerializer(Asset.objects.filter(item=item.item_id), many=True)
        Log.objects.create(request_id='', item_id= item.item_id, item_name = item.item_name, initiating_user=request.user, nature_of_event="Edit", 
                       affected_user='', change_occurred="Changed " + item.item_name + " to track by asset.")
        return Response(serializer.data)
    
class APIAssetToItem(APIView):
    """
    Converts an item back to non-per-asset
    """
    permission_classes = (IsAdmin,)
    
    def get(self, request, pk, format=None):
        # what should happen when an item is converted back to non-per-asset
        # assets should be deleted, loans/disbursements with assets should be converted back into item w/ number
        item = Item.objects.get(item_id=pk)
        if Asset.objects.filter(item=pk):
            item.is_asset = False
            item.save()
            for asset in Asset.objects.filter(item=pk):
                asset.delete()
        context = {
            "request": self.request,
            "pk": pk,
        }
        serializer = ItemSerializer(item, context=context)
        Log.objects.create(request_id='', item_id= item.item_id, item_name = item.item_name, initiating_user=request.user, nature_of_event="Edit", 
                       affected_user='', change_occurred="Changed " + item.item_name + " to no longer track by asset.")
        return Response(serializer.data)
 
class APIAddAsset(APIView): 
    permission_classes = (IsAdmin,)
    serializer_class = AddAssetsSerializer
    
    def get(self, request, pk, format=None):
        item = Item.objects.get(item_id=pk)
        serializer = AssetSerializer(Asset.objects.filter(item=item.item_id), many=True)
        return Response(serializer.data)
    
    def post(self,request,pk,format=None):
        assets_to_add = request.data['num_assets']
        item = Item.objects.get(item_id=pk)
        item.quantity = item.quantity + int(assets_to_add)
        for i in range(int(assets_to_add)):
                asset = Asset(item=item)
                asset.save()
        item.save()
        serializer = AssetSerializer(Asset.objects.filter(item=item.item_id), many=True)
        Log.objects.create(request_id='', item_id= item.item_id, item_name = item.item_name, initiating_user=request.user, nature_of_event="Edit", 
                       affected_user='', change_occurred= "Added " + assets_to_add + " assets to " + item.item_name + ".")
        return Response(serializer.data)
    
class APIAsset(APIView):
    permission_classes = (IsAdmin,)
    serializer_class = AssetWithCustomFieldSerializer 
    
    def get(self, request, pk, format=None):
        if (Asset.objects.filter(asset_id=pk).exists()):
            asset = Asset.objects.get(asset_id=pk)
            custom_values = Asset_Custom_Field_Value.objects.filter(asset = asset)
            serializer = AssetWithCustomFieldSerializer(custom_values,asset.asset_tag)
            return Response(serializer.data)
        else:
            return Response(status=status.HTTP_400_BAD_REQUEST)
        
    def delete(self,request,pk,format=None):
        if (Asset.objects.filter(asset_id=pk).exists()):
            asset = Asset.objects.get(asset_id=pk)
            asset_id = asset.asset_id
            asset_tag = asset.asset_tag
            if asset.loan != None:
                asset.loan.total_quantity = asset.loan.total_quantity - 1;
                asset.loan.save()
            item = asset.item
            asset.delete()
            item.quantity = item.quantity - 1
            item.save()
            Log.objects.create(request_id='', item_id= item.item_id, item_name = item.item_name, initiating_user=request.user, nature_of_event="Delete", 
                       affected_user='', change_occurred="Deleted asset with tag " + asset_tag + " from the " + item.item_name + " item (asset id: " +asset_id+ ").")
            return Response(status=status.HTTP_204_NO_CONTENT)
        else:
            return Response(status=status.HTTP_400_BAD_REQUEST)
        
    def put(self, request, pk, format=None):
        asset = Asset.objects.get(asset_id=pk)
        custom_fields = Custom_Field.objects.filter(field_kind='Asset')
        custom_values = Asset_Custom_Field_Value.objects.filter(asset = asset)
        for field in custom_fields:
            if request.data[field.field_name] is '' and (field.field_type == 'Int' or field.field_type == 'Float'):
                request.data[field.field_name] = None
        serializer = AssetWithCustomFieldSerializer(custom_values,asset.asset_tag,data=request.data, partial=True)
        if serializer.is_valid():
            data = serializer.data
            if 'asset_tag' in data:
                new_tag = data['asset_tag']
                if new_tag is not '' and not Asset.objects.filter(asset_tag=new_tag).exists():
                    asset.asset_tag = new_tag
                    asset.save()
            fields = Custom_Field.objects.filter(field_kind='Asset')
            for field in fields:
                if field.field_name in data:
                    value = data[field.field_name]  
                    if Asset_Custom_Field_Value.objects.filter(asset = asset, field = field).exists():
                        custom_val = Asset_Custom_Field_Value.objects.get(asset = asset, field = field)
                    else:
                        custom_val = Asset_Custom_Field_Value(asset=asset, field=field)
                    if field.field_type == 'Short' and len(value)<=400 or \
                        field.field_type == 'Long' and len(value)<=1000:
                        custom_val.value = value
                    if field.field_type == 'Int':
                        try:
                            if value is not None:
                                int(value)
                            custom_val.value = value
                        except ValueError:
                            return Response("a certain field value needs to be an integer since it is an integer type field", status=status.HTTP_400_BAD_REQUEST)
                    if field.field_type == 'Float':
                        try:
                            if value is not None:
                                float(value)
                            custom_val.value = value
                        except ValueError:
                            return Response("a certain field value needs to be a float since it is a float type field", status=status.HTTP_400_BAD_REQUEST)
                    custom_val.save()
            Log.objects.create(request_id='', item_id= asset.item.item_id, item_name = asset.item.item_name, initiating_user=request.user, nature_of_event="Edit", 
                       affected_user='', change_occurred="Edited asset with (new) tag " + asset.asset_tag + " from the " + asset.item.item_name + " item (asset id: " +asset.asset_id+ ").")          
            return self.get(request, asset.asset_id)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
       
########################################## Server-side processing ###########################################         
class JSONResponse(HttpResponse):
    """
    Return a JSON serialized HTTP response
    """
    def __init__(self, request, data, status=200):
        # pass DjangoJSONEncoder to handle Decimal fields
        json_data = json.dumps(data, cls=DjangoJSONEncoder)
        super(JSONResponse, self).__init__(
            content=json_data,
            content_type='application/json',
            status=status,
        )
 
class JSONViewMixin(object):
    """
    Return JSON data. Add to a class-based view.
    """
    def json_response(self, data, status=200):
        return JSONResponse(self.request, data, status=status)  

 
# API
 
# define a map from json column name to model field name
# this would be better placed in the model
col_name_map = {
    'nature_of_event': 'nature_of_event',
    'initiating_user': 'initiating_user',
    'item_name': 'item_name',
    'affected_user': 'affected_user',
    'change_occurred': 'change_occurred',
    'time_occurred': 'time_occurred',
                
               }
class MyAPI(JSONViewMixin, View):
    "Return the JSON representation of the objects"
    def get(self, request, *args, **kwargs):
        class_name = kwargs.get('cls_name')
        params = request.GET
        # make this api general enough to handle different classes
        klass = getattr(sys.modules['inventory.models'], class_name)
 
        # TODO: this only pays attention to the first sorting column
        sort_col_num = params.get('iSortCol_0', 0)
        # default to value column
        sort_col_name = params.get('mDataProp_{0}'.format(sort_col_num), 'value')
        search_text = params.get('sSearch', '').lower()
        sort_dir = params.get('sSortDir_0', 'asc')
        start_num = int(params.get('iDisplayStart', 0))
        num = int(params.get('iDisplayLength', 25))
        start_date = params.get('datetime')
        
        obj_list = klass.objects.all()
       
        sort_dir_prefix = (sort_dir=='desc' and '-' or '')
        if sort_col_name in col_name_map:
            sort_col = col_name_map[sort_col_name]
            obj_list = obj_list.order_by('{0}{1}'.format(sort_dir_prefix, sort_col))
            
        filtered_obj_list = obj_list
        
        if start_date:
            obj_list = obj_list.filter(time_occurred__gte=start_date)
        if search_text or start_date:
            filtered_obj_list = obj_list.filter(
                Q(item_name__icontains=search_text) | Q(initiating_user__icontains=search_text) |
                Q(nature_of_event__icontains=search_text) | Q(affected_user__icontains=search_text) | Q(change_occurred__icontains=search_text))
        
        d = {"iTotalRecords": obj_list.count(),                # num records before applying any filters
            "iTotalDisplayRecords": filtered_obj_list.count(), # num records after applying filters
            "sEcho":params.get('sEcho',1),                     # unaltered from query
            "aaData": [obj.as_dict() for obj in filtered_obj_list[start_num:(start_num+num)]] # the data
        }
        
        return self.json_response(d)
    
