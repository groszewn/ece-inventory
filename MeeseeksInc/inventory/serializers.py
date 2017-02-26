import re

from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework import serializers

from inventory.models import Item, Tag, Request, Disbursement, Custom_Field, Custom_Field_Value


class UserSerializer(serializers.ModelSerializer):
    email = serializers.CharField(allow_blank = True)
    class Meta:
        model = User
        fields = ('username', 'password', 'email', 'is_staff')
    def validate_email(self, value):
        """
        Check that the email is valid
        """
        pattern = re.compile("(^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$)")
        
        if not pattern.match(value):
            raise serializers.ValidationError("Enter a valid email address.")
        return value
    
    def create(self, validated_data):
        user = User()
        user.email = validated_data.get('email')
        user.username = validated_data.get('username')
        try:
            user.is_staff = validated_data.get('is_staff')
            if not validated_data.get('is_staff'):
                user.is_staff = False
        except:
            user.is_staff= False
        user.set_password(validated_data['password'])
        user.save()
        return user
    
class GetItemSerializer(serializers.ModelSerializer):
    requests_outstanding = serializers.SerializerMethodField('get_outstanding_requests')
    values_custom_field = serializers.SerializerMethodField('get_custom_field_values')
    def get_outstanding_requests(self, obj):
        user = self.context['request'].user
        item_id = self.context['pk']
        outstanding_requests=[]
        if User.objects.get(username=user).is_staff:
            outstanding_requests = Request.objects.filter(item_name=item_id, status="Pending")
        else:
            outstanding_requests = Request.objects.filter(item_name=item_id, user_id=user.username, status="Pending")
        serializer = RequestSerializer(outstanding_requests, many=True)
        return serializer.data
     
    def get_custom_field_values(self, obj):
        item_id = self.context['pk']
        item = Item.objects.get(item_id = item_id)
        user = self.context['request'].user
        custom_values = []
        if User.objects.get(username=user).is_staff:
            custom_values = Custom_Field_Value.objects.filter(item = item)
        else:
            all_vals = Custom_Field_Value.objects.filter(item = item)
            for val in all_vals:
                if val.field.is_private:
                    all_vals.remove(val)
            custom_values = all_vals
        serializer = CustomValueSerializerNoItem(custom_values, many=True)
        return serializer.data

    class Meta:
        model = Item
        fields = ('item_id', 'item_name', 'quantity', 'model_number', 'description', 'requests_outstanding','values_custom_field','tags')

class ItemSerializer(serializers.ModelSerializer):
    values_custom_field = serializers.SerializerMethodField('get_custom_field_values')
    
    class Meta:
        model = Item
        fields = ('item_id', 'item_name', 'quantity', 'model_number', 'description', 'tags', 'values_custom_field')
    
    def get_custom_field_values(self, obj):
        item = Item.objects.get(item_name = obj)
        user = self.context['request'].user
        custom_values = []
        if User.objects.get(username=user).is_staff:
            custom_values = Custom_Field_Value.objects.filter(item = item)
        else:
            custom_values = Custom_Field_Value.objects.filter(item = item, field__is_private = False)
        serializer = CustomValueSerializerNoItem(custom_values, many=True)
        return serializer.data
    
    def validate_quantity(self, value):
        """
        Check that the item quantity is positive
        """
        if value<0:
            raise serializers.ValidationError("Item quantity needs to be greater than 0")
        return value

class CustomFieldSerializer(serializers.ModelSerializer):
    class Meta:
        model = Custom_Field
        fields = ('id','field_name','is_private','field_type')
        
class CustomValueSerializer(serializers.ModelSerializer):
    class Meta:
        model = Custom_Field_Value
        fields = ('item','field','field_value_short_text','field_value_long_text', 'field_value_integer', 'field_value_floating')      
        depth = 1
        
class CustomValueSerializerNoItem(serializers.ModelSerializer):
    class Meta:
        model = Custom_Field_Value
        fields = ('field','field_value_short_text','field_value_long_text', 'field_value_integer', 'field_value_floating')      
        depth = 1

class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ('tag',)
        
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
        fields = ('request_id', 'user_id', 'time_requested', 'item_name', 'request_quantity', 'status', 'comment', 'reason')    
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
        fields = ('user_id', 'time_requested', 'item_name', 'request_quantity', 'reason', 'request_id')    
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
    comment = serializers.CharField(required=False, allow_blank=True)
    class Meta:
        model = Request
        fields = ('comment',)
        
class DisbursementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Disbursement
        fields = ('admin_name', 'user_name', 'item_name', 'total_quantity', 'comment', 'time_disbursed')
        
class DisbursementPostSerializer(serializers.ModelSerializer):
    time_disbursed = serializers.DateTimeField(
        default=serializers.CreateOnlyDefault(timezone.localtime(timezone.now()))
    )
    admin_name = serializers.CharField(
        default=serializers.CurrentUserDefault(), 
        read_only=True
    )
    comment = serializers.CharField(required=False, allow_blank=True)
    
    class Meta:
        model = Disbursement
        fields = ('admin_name', 'user_name', 'item_name', 'total_quantity', 'comment', 'time_disbursed')    
    def validate_total_quantity(self, value):
        """
        Check that the request is positive
        """
        if value<0:
            raise serializers.ValidationError("Request quantity needs to be greater than 0")
        return value
        