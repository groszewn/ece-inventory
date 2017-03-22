from datetime import datetime
import uuid

from django.db import models
from django.utils import timezone


class Tag(models.Model):
    tag = models.CharField(max_length=200)
    def __str__(self):
        return self.tag
    

class Item(models.Model):
    item_id = models.CharField(primary_key=True, max_length=200, unique=True, default=uuid.uuid4)
    item_name = models.CharField(unique=True, max_length=200)
    quantity = models.SmallIntegerField(null=False)
    model_number = models.CharField(max_length=200, null=True)
    description = models.CharField(max_length=1000, null=True)
    tags = models.ManyToManyField(Tag, related_name='items', blank=True)
    def __str__(self):
        return self.item_name
 
class Instance(models.Model):
    item = models.ForeignKey(Item, null=True, on_delete=models.CASCADE) 
    instance_id = models.CharField(primary_key=True, max_length=200)
    status = models.CharField(max_length=200)
    available = models.CharField(max_length=200)
    def __str__(self):
        return self.item.item_name + " #" + self.instance_id
 
class Request(models.Model):
    request_id = models.CharField(primary_key=True, max_length=200, unique=True, default=uuid.uuid4)
    user_id = models.CharField(max_length=200, null=False)
    item_name = models.ForeignKey(Item, null=True, related_name='requests', on_delete=models.CASCADE) 
    request_quantity = models.IntegerField(null=False)
    CHOICES = (
        ('Pending', 'Pending'),
        ('Approved', 'Approved'),
        ('Denied', 'Denied'),
    )
    status = models.CharField(max_length=200, null=False, choices=CHOICES, default='Pending')
    comment = models.CharField(max_length=200, null=True, default = '') # comment left by admin, can be null, used for denial 
    reason = models.CharField(max_length=200, null=False) # reason given by user
    time_requested = models.DateTimeField(default=timezone.now)
    TYPES = (
        ( 'Dispersal','Dispersal'),
        ('Loan','Loan'),
    )
    type = models.CharField(max_length=200, null=False, choices=TYPES, default='Dispersal')
    def __str__(self):
        return "Request for " + str(self.request_quantity) + " " + self.item_name.item_name + " by " + self.user_id  + " (ID: " + self.request_id + ")"
        
class Disbursement(models.Model):   
    disburse_id = models.CharField(primary_key=True, max_length=200, unique=True, default=uuid.uuid4)
    admin_name = models.CharField(max_length=200, null=False)
    user_name = models.CharField(max_length=200, null=False)
    item_name = models.ForeignKey(Item, null=True, on_delete=models.CASCADE)
    orig_request = models.ForeignKey(Request, null=True, on_delete=models.CASCADE) 
    total_quantity = models.IntegerField(null=False)
    comment = models.CharField(max_length=200, null=False) # comment left by admin, can be null
    time_disbursed = models.DateTimeField(default=timezone.now)
    def __str__(self):
        return "Disbursement for " + self.item_name.item_name + " from " + self.admin_name + " to " + self.user_name
    
class Loan(models.Model):
    loan_id = models.CharField(primary_key=True, max_length=200, unique=True, default=uuid.uuid4)
    admin_name = models.CharField(max_length=200, null=False)
    user_name = models.CharField(max_length=200, null=False)
    item_name = models.ForeignKey(Item, null=True, on_delete=models.CASCADE) 
    orig_request = models.ForeignKey(Request, null=True, on_delete=models.CASCADE) 
    total_quantity = models.IntegerField(null=False)
    comment = models.CharField(max_length=200, null=False) # comment left by admin, can be null
    time_loaned = models.DateTimeField(default=timezone.now)
    CHOICES = (
        ('Checked Out', 'Checked Out'),
        ('Checked In', 'Checked In'),
    )
    status = models.CharField(max_length=200, null=False, choices=CHOICES, default='Checked Out')
    def __str__(self):
        return "Loan of " + self.item_name.item_name + " from " + self.admin_name + " to " + self.user_name
    
class ShoppingCartInstance(models.Model):
    cart_id = models.CharField(primary_key=True, max_length=200, unique=True, default=uuid.uuid4)
    user_id = models.CharField(max_length=200, null=False)
    item = models.ForeignKey(Item, null = True, on_delete=models.CASCADE)
    quantity = models.SmallIntegerField(null=False)
    TYPES = (
        ( 'Dispersal','Dispersal'),
        ('Loan','Loan'),
    )
    type = models.CharField(max_length=200, null=False, choices=TYPES)
    reason = models.CharField(max_length=200, null=False, default="")

class Item_Log(models.Model):
    item_name = models.ForeignKey(Item, null=True)
    item_change_status = models.CharField(max_length=400, null=True)
    item_amount = models.SmallIntegerField(null=False)
    
class Custom_Field(models.Model):
    field_name = models.CharField(max_length=400, null=False, unique=True)
    is_private = models.BooleanField(default = False)
    CHOICES = (
        ('Short','Short-Form Text'),
        ('Long','Long-Form Text'),
        ('Int','Integer'),
        ('Float','Floating-Point Number'),
    )
    field_type = models.CharField(max_length=200, null=False, choices=CHOICES, default='Short') 
    
class Custom_Field_Value(models.Model):
    item = models.ForeignKey(Item, null=False, on_delete=models.CASCADE)
    field = models.ForeignKey(Custom_Field, null=False, on_delete=models.CASCADE)
    field_value_short_text = models.CharField(max_length=400,null=True)
    field_value_long_text = models.TextField(max_length=1000,null=True)
    field_value_integer = models.IntegerField(null=True, blank=True)
    field_value_floating = models.FloatField(null=True, blank=True)
    
    class Meta:
       unique_together = (("item", "field"),)

class Log(models.Model):
    request_id = models.CharField(max_length=200, null=True, default=None)
    item_id = models.CharField(max_length=200, null=True, default=None)
    item_name = models.CharField(max_length=200, null=True)
    initiating_user = models.CharField(max_length=200, null=False)
    CHOICES = (
        ('Create', 'Create'),
        ('Delete', 'Delete'),
        ('Request', 'Request'),
        ('Disburse', 'Disburse'), 
        ('Approve', 'Approve'),
        ('Deny', 'Deny'), 
        ('Edit', 'Edit'),
        ('Override', 'Override'), 
        ('Acquire', 'Acquire'), 
        ('Lost', 'Lost'), 
        ('Broken', 'Broken'),
        ('Loan', 'Loan'),
        ('Check In', 'Check In')
    )
    nature_of_event = models.CharField(max_length=200, null=False, choices=CHOICES)
    time_occurred = models.DateTimeField(default=timezone.now)
    affected_user = models.CharField(max_length=200, null=True, default='')
    change_occurred = models.CharField(max_length=200, null=False)
    
class SubscribedUsers(models.Model):
    user = models.CharField(max_length=200)
    email = models.CharField(max_length=200)
    
class EmailPrependValue(models.Model):
    prepend_text = models.CharField(max_length=200, default='')
   
class LoanReminderEmailBody(models.Model):
    body = models.TextField() 
    
class LoanSendDates(models.Model):
    date = models.DateField()
    