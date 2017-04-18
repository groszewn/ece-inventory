import re

from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework import serializers

from inventory.models import Item, Tag, Request, Disbursement, Custom_Field, Custom_Field_Value, \
    Log, Loan, SubscribedUsers, LoanReminderEmailBody, LoanSendDates, Asset


class UserSerializer(serializers.ModelSerializer):
    email = serializers.CharField(allow_blank = False)
    class Meta:
        model = User
        fields = ('username', 'password', 'email', 'is_staff', 'is_superuser', 'is_active')
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
            if validated_data.get('is_superuser'):
                user.is_staff=True
                user.is_superuser = True
            elif validated_data.get('is_staff'):
                user.is_staff=True
            else:
                user.is_staff = False
                user.is_superuser = False
        except:
            user.is_staff= False
            user.is_superuser = False
        user.set_password(validated_data['password'])
        user.save()
        return user

class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ('tag',)
          
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
        fields = ('item_id', 'item_name', 'quantity' ,'threshold_quantity', 'threshold_enabled','model_number', 
                  'description', 'requests_outstanding','values_custom_field','tags')

class ItemSerializer(serializers.ModelSerializer):
    values_custom_field = serializers.SerializerMethodField('get_custom_field_values')
    model_number = serializers.CharField(required=False, allow_blank=True)
    description = serializers.CharField(required=False, allow_blank=True)
    item_id = serializers.CharField(read_only=True)
    class Meta:
        model = Item
        fields = ('item_id', 'item_name', 'quantity', 'model_number', 'description', 'tags', 'values_custom_field' ,'threshold_quantity', 
    'threshold_enabled', 'is_asset')
    
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
        
class AssetCustomFieldSerializer(serializers.ModelSerializer):
    class Meta:
        model = Custom_Field
        fields = ('id','field_name','is_private','field_type')
        
class FullCustomFieldSerializer(serializers.ModelSerializer):
    class Meta:
        model = Custom_Field
        fields = ('id','field_name','is_private','field_type','field_kind')

class CustomValueSerializer(serializers.ModelSerializer):
    class Meta:
        model = Custom_Field_Value
        fields = ('item','field','field_value_short_text','field_value_long_text', 'field_value_integer', 'field_value_floating')      
        depth = 1
        
class CustomValueSerializerNoItem(serializers.ModelSerializer):
    
    id = serializers.ReadOnlyField(source='field.id')
    field_name = serializers.ReadOnlyField(source='field.field_name')
    is_private = serializers.ReadOnlyField(source='field.is_private')
    field_type = serializers.ReadOnlyField(source='field.field_type')
    
    class Meta:
        model = Custom_Field_Value
        fields = ('id','field_name', 'is_private', 'field_type', 'value')      
        depth = 1

class LogSerializer(serializers.ModelSerializer):
    class Meta:
        model = Log
        fields = ('item_name', 'initiating_user', 'nature_of_event', 'time_occurred', 'affected_user', 'change_occurred',)
    
class RequestSerializer(serializers.ModelSerializer):
    time_requested = serializers.DateTimeField(
        default=timezone.localtime(timezone.now())
    )
    user_id = serializers.CharField(
        default=serializers.CurrentUserDefault(), 
        read_only=True
    )
    status = serializers.CharField(read_only=True)
    class Meta:
        model = Request
        fields = ('request_id', 'user_id', 'time_requested', 'item_name', 'request_quantity', 'status', 'comment', 'reason', 'type')    
    def validate_request_quantity(self, value):
        """
        Check that the request is positive
        """
        if value<0:
            raise serializers.ValidationError("Request quantity needs to be greater than 0")
        return value
    
class RequestPostSerializer(serializers.ModelSerializer):
    time_requested = serializers.DateTimeField(
        default=timezone.localtime(timezone.now()),
        read_only=True
    )
    user_id = serializers.CharField(
        default=serializers.CurrentUserDefault(), 
        read_only=True
    )
    item_name = ItemSerializer(read_only=True)
    request_id = serializers.CharField(read_only=True)
    class Meta:
        model = Request
        fields = ('user_id', 'time_requested', 'item_name', 'request_quantity', 'reason', 'request_id', 'type')    
    def validate_request_quantity(self, value):
        """
        Check that the request is positive
        """
        if value<0:
            raise serializers.ValidationError("Request quantity needs to be greater than 0")
        return value

class MultipleRequestPostSerializer(serializers.ModelSerializer):
    time_requested = serializers.DateTimeField(
        default=timezone.localtime(timezone.now()),
        read_only=True
    )
    user_id = serializers.CharField(
        default=serializers.CurrentUserDefault(), 
        read_only=True
    )

    class Meta:
        model = Request
        fields = ('user_id', 'time_requested', 'item_name', 'request_quantity', 'type', 'reason', 'request_id')    
    
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
        fields = ('time_requested', 'request_quantity', 'reason','type')    
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
        fields = ('admin_name', 'user_name', 'item_name', 'total_quantity', 'comment', 'orig_request','time_disbursed')
        
class DisbursementPostSerializer(serializers.ModelSerializer):
    time_disbursed = serializers.DateTimeField(
        default=timezone.localtime(timezone.now()),
        read_only=True
    )
    admin_name = serializers.CharField(
        default=serializers.CurrentUserDefault(), 
        read_only=True
    )
    item_name = ItemSerializer(read_only=True)
    
    comment = serializers.CharField(required=False, allow_blank=True)
    
    class Meta:
        model = Disbursement
        fields = ('admin_name', 'user_name', 'item_name', 'total_quantity', 'comment', 'time_disbursed')    
    def validate_total_quantity(self, value):
        """
        Check that the request is positive
        """
        if value<=0:
            raise serializers.ValidationError("Request quantity needs to be greater than 0")
        return value
    def validate_user_name(self, value):
        """
        Check that the user is real
        """
        try:
            return User.objects.get(username=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("User does not exist")
        return value
 
class FullLoanSerializer(serializers.ModelSerializer):
    backfill_pdf = serializers.FileField(max_length=200, use_url=True)
    class Meta:
        model = Loan
        fields = ('loan_id','admin_name','user_name','item_name','orig_request','total_quantity', 'comment','time_loaned', 'status', 'backfill_pdf', 'backfill_status', 'backfill_quantity', 'backfill_notes') 
    
class LoanUpdateSerializer(serializers.ModelSerializer):
    comment = serializers.CharField(required=False, allow_blank=True)
    time_loaned = serializers.DateTimeField(
        default=timezone.localtime(timezone.now()),
        read_only=True
    )
    admin_name = serializers.CharField(
        default=serializers.CurrentUserDefault(), 
        read_only=True
    )
    user_name = serializers.CharField(
        read_only=True
        )
    item_name = serializers.CharField(read_only=True)
    total_quantity = serializers.IntegerField(required=True)
    class Meta:
        model = Loan
        fields = ('admin_name', 'user_name', 'item_name', 'total_quantity', 'comment', 'time_loaned')
        
class LoanCheckInSerializer(serializers.Serializer):
    check_in = serializers.IntegerField(required=True)
    
class LoanCheckInWithAssetSerializer(serializers.Serializer):
    class Meta:
        model = Asset
        fields = ('asset_id')
    
class LoanConvertSerializer(serializers.Serializer):
    number_to_convert = serializers.IntegerField(required=True)
        
class LoanPostSerializer(serializers.ModelSerializer):
    time_loaned = serializers.DateTimeField(
        default=timezone.localtime(timezone.now()),
        read_only=True
    )
    admin_name = serializers.CharField(
        default=serializers.CurrentUserDefault(), 
        read_only=True
    )
    item_name = ItemSerializer(read_only=True)
    
    comment = serializers.CharField(required=False, allow_blank=True)
    
    class Meta:
        model = Loan
        fields = ('admin_name', 'user_name', 'item_name', 'total_quantity', 'comment', 'time_loaned')    
    def validate_total_quantity(self, value):
        """
        Check that the request is positive
        """
        if value<=0:
            raise serializers.ValidationError("Request quantity needs to be greater than 0")
        return value
    def validate_user_name(self, value):
        """
        Check that the user is real
        """
        try:
            return User.objects.get(username=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("User does not exist")
        return value
        
class SubscribeSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscribedUsers
        fields = ('user','email',)
        
    def validate_email(self, value):
        """
        Check that the email is valid
        """
        pattern = re.compile("(^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$)")
        
        if not pattern.match(value):
            raise serializers.ValidationError("Enter a valid email address.")
        return value
        
class LoanReminderBodySerializer(serializers.ModelSerializer):
    class Meta:
        model = LoanReminderEmailBody
        fields = ('body',)
        
class LoanSendDatesSerializer(serializers.ModelSerializer):
    class Meta:
        model = LoanSendDates
        fields = ('date',)
        
class AssetSerializer(serializers.ModelSerializer):
    class Meta:
        model = Asset
        fields = ('asset_id','asset_tag','item')
        
class AddAssetsSerializer(serializers.Serializer):
    num_assets = serializers.IntegerField(required=True)
      
class AssetWithCustomFieldSerializer(serializers.Serializer):
    def __init__(self, custom_values=None, asset_tag=None, *args, **kwargs):
        super(AssetWithCustomFieldSerializer, self).__init__(*args, **kwargs)
        self.fields['asset_tag'] = serializers.CharField(required=False,allow_blank=True)
        if asset_tag is not None:
            self.fields['asset_tag'] = serializers.CharField(initial = asset_tag, required=False,allow_blank=True)
        for field in Custom_Field.objects.filter(field_kind='Asset'):
            if field.field_type == 'Short':
                self.fields["%s" % field.field_name] = serializers.CharField(required=False,allow_blank=True)                    
            if field.field_type == 'Long':
                self.fields["%s" % field.field_name] = serializers.CharField(required=False,allow_blank=True) 
            if field.field_type == 'Int':
                self.fields["%s" % field.field_name] = serializers.IntegerField(required=False,allow_null=True) 
            if field.field_type == 'Float':
                self.fields["%s" % field.field_name] = serializers.FloatField(required=False,allow_null=True)
            if custom_values is not None:
                for val in custom_values:
                    if val.field == field:
                        if field.field_type == 'Short':
                            self.fields["%s" % field.field_name] = serializers.CharField(initial = val.value,required=False,allow_blank=True)                    
                        if field.field_type == 'Long':
                            self.fields["%s" % field.field_name] = serializers.CharField(initial = val.value,required=False,allow_blank=True) 
                        if field.field_type == 'Int':
                            self.fields["%s" % field.field_name] = serializers.IntegerField(initial = val.value,required=False,allow_null=True) 
                        if field.field_type == 'Float':
                            self.fields["%s" % field.field_name] = serializers.FloatField(initial = val.value,required=False,allow_null=True)
        
class MultipleAssetCustomFieldSerializer(serializers.ModelSerializer):
    time_requested = serializers.DateTimeField(
        default=timezone.localtime(timezone.now()),
        read_only=True
    )
    user_id = serializers.CharField(
        default=serializers.CurrentUserDefault(), 
        read_only=True
    )

    class Meta:
        model = Request
        fields = ('user_id', 'time_requested', 'item_name', 'request_quantity', 'type', 'reason', 'request_id')    
    
            
class LoanBackfillPostSerializer(serializers.ModelSerializer):
    backfill_pdf = serializers.FileField(max_length=200, use_url=True)
    backfill_quantity = serializers.IntegerField(required=True)
    loan_id = serializers.CharField(read_only=True)
    backfill_status = serializers.CharField(read_only=True)
    backfill_time_requested = serializers.DateTimeField(read_only=True)
    class Meta:
        model = Loan
        fields = ('loan_id', 'backfill_pdf', 'backfill_status', 'backfill_quantity', 'backfill_time_requested')
        
    def validate_backfill_quantity(self, value):
        """
        Check that the quantity is positive and less than the total loan quantity
        
        """
        loan = Loan.objects.get(loan_id=self.instance)
        if (value <=0):
            raise serializers.ValidationError("Backfill quantity needs to be greater than 0")
        elif (value > loan.total_quantity):
            raise serializers.ValidationError("Backfill quantity can't be more than the loan quantity")
        return value
    
    def validate_backfill_time_requested(self, value):
        return timezone.localtime(timezone.now())
    
class BackfillAcceptDenySerializer(serializers.ModelSerializer):
    backfill_notes = serializers.CharField(required=False, allow_blank=True)
    class Meta:
        model = Loan
        fields = ('backfill_notes',)
        
        
        
