

from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework import serializers

from inventory.models import Item, Tag, Request, Disbursement


class ItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = Item
        fields = ('item_name', 'quantity', 'location', 'model_number', 'description')

class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ('item_name', 'tag')
        
class RequestSerializer(serializers.ModelSerializer):
    time_requested = serializers.DateTimeField(
        default=serializers.CreateOnlyDefault(timezone.localtime(timezone.now()))
    )
    user_id = serializers.CharField(
        default=serializers.CurrentUserDefault(), 
        read_only=True
    )
    
    status = serializers.CharField(read_only=True)
    class Meta:
        model = Request
        fields = ('user_id', 'time_requested', 'item_name', 'request_quantity', 'status', 'comment', 'reason')    
    def validate_request_quantity(self, value):
        """
        Check that the request is positive
        """
        if value<0:
            raise serializers.ValidationError("Request quantity needs to be greater than 0")
        return value
    
class RequestPostSerializer(serializers.ModelSerializer):
    time_requested = serializers.DateTimeField(
        default=serializers.CreateOnlyDefault(timezone.localtime(timezone.now()))
    )
    user_id = serializers.CharField(
        default=serializers.CurrentUserDefault(), 
        read_only=True
    )
    
    class Meta:
        model = Request
        fields = ('user_id', 'time_requested', 'item_name', 'request_quantity', 'reason')    
    def validate_request_quantity(self, value):
        """
        Check that the request is positive
        """
        if value<0:
            raise serializers.ValidationError("Request quantity needs to be greater than 0")
        return value
    
class RequestUpdateSerializer(serializers.ModelSerializer):
    time_requested = serializers.HiddenField(
        default=serializers.CreateOnlyDefault(timezone.localtime(timezone.now()))
    )
    class Meta:
        model = Request
        fields = ('time_requested', 'request_quantity', 'reason')    
    def validate_request_quantity(self, value):
        """
        Check that the request is positive
        """
        if value<0:
            raise serializers.ValidationError("Request quantity needs to be greater than 0")
        return value

class RequestAcceptDenySerializer(serializers.ModelSerializer):
    comment = serializers.CharField(required=False)
    class Meta:
        model = Request
        fields = ('comment',)
        
class DisbursementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Disbursement
        fields = ('admin_name', 'user_name', 'item_name', 'total_quantity', 'comment', 'time_disbursed')
        