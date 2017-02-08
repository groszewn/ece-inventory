import uuid
from django.db import models
 
class Item(models.Model):
    item_id = models.CharField(primary_key=True, max_length=200, unique=True, default=uuid.uuid4)
    item_name = models.CharField(unique=True, max_length=200)
    quantity = models.SmallIntegerField(null=False)
    location = models.CharField(max_length=200, null=True)
    model_number = models.CharField(max_length=200, null=True)
    description = models.CharField(max_length=400, null=True)
    def __str__(self):
        return self.item_name
    
class Tag(models.Model):
    item_name = models.ForeignKey(Item, on_delete=models.CASCADE) 
    tag = models.CharField(max_length=200)
    def __str__(self):
        return self.tag
 
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
    item_name = models.ForeignKey(Item, null=True, on_delete=models.CASCADE) 
#     item_name = models.CharField(max_length=200, null=False)
    request_quantity = models.SmallIntegerField(null=False)
    CHOICES = (
        ('Pending', 'Pending'),
        ('Approved', 'Approved'),
        ('Denied', 'Denied'),
    )
    status = models.CharField(max_length=200, null=False, choices=CHOICES, default='Pending')
    comment = models.CharField(max_length=200, null=False) # comment left by admin, can be null, used for denial 
    reason = models.CharField(max_length=200, null=False) # reason given by user
    time_requested = models.TimeField()
    def __str__(self):
        return self.item_name.item_name + " " + self.request_id
 
class Disbursement(models.Model):
    disburse_id = models.CharField(primary_key=True, max_length=200, unique=True, default=uuid.uuid4)
    admin_name = models.CharField(max_length=200, null=False)
    user_name = models.CharField(max_length=200, null=False)
    item_name = models.ForeignKey(Item, null=True, on_delete=models.CASCADE) 
    total_quantity = models.SmallIntegerField(null=False)
    comment = models.CharField(max_length=200, null=False) # comment left by admin, can be null
    time_disbursed = models.TimeField()
    def __str__(self):
        return self.item_name.item_name + " from " + self.admin_name + " to " + self.user_name

class ShoppingCartInstance(models.Model):
    cart_id = models.CharField(primary_key=True, max_length=200, unique=True, default=uuid.uuid4)
    user_id = models.CharField(max_length=200, null=False)
    item = models.ForeignKey(Item, null = True, on_delete=models.CASCADE)
    quantity = models.SmallIntegerField(null=False)

class Item_Log(models.Model):
    item_name = models.ForeignKey(Item, null=True)
    item_change_status = models.CharField(max_length=400, null=True)
    item_amount = models.SmallIntegerField(null=False)
 

############################## FROM THE DJANGO TUTORIAL #############################
class Question(models.Model):
    question_text = models.CharField(max_length=200)
    pub_date = models.DateTimeField('date published') 
    def __str__(self):
        return self.question_text
 
class Choice(models.Model):
    #as you can see, this is adding the field "question" to "choice" 
    question = models.ForeignKey(Question, on_delete=models.CASCADE) 
    choice_text = models.CharField(max_length=200)  #tells Django that this is a Character Field
    votes = models.IntegerField(default=0)  #tells Django that this is a Integer Field
    def __str__(self):
        return self.choice_text
     