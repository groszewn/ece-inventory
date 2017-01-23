from django.db import models
# create table item_table ( 
# item_name varchar PRIMARY KEY, 
# quantity smallint NOT NULL, 
# price float(2) );

class Item(models.Model):
    item_name = models.CharField(primary_key=True, max_length=200)
    quantity = models.SmallIntegerField(null=False);
    tag = models.CharField(null=True, max_length=200)
    price = models.DecimalField(max_digits=8, decimal_places=2);
    def __str__(self):
        return self.item_name
    
# create table item_table ( 
# instance_id varchar PRIMARY KEY, 
# location varchar, 
# status varchar, 
# available varchar, 
# model_number varchar, 
# item_name varchar NOT NULL );

class Instance(models.Model):
    item = models.ForeignKey(Item, null=True, on_delete=models.CASCADE) 
    instance_id = models.CharField(primary_key=True, max_length=200)
    location = models.CharField(max_length=200)
    status = models.CharField(max_length=200)
    available = models.CharField(max_length=200)
    model_number = models.CharField(max_length=200)
#     item_name = models.CharField(max_length=200, null=False)
    
    def __str__(self):
        return self.item.item_name + " #" + self.instance_id

# create table request_table (
# request_id serial PRIMARY KEY, 
# user_id varchar NOT NULL, 
# item_name varchar NOT NULL, 
# request_quantity smallint NOT NULL, 
# status varchar NOT NULL, 
# comment varchar, 
# time_requested timestamp );

class Request(models.Model):
    request_id = models.CharField(primary_key=True, max_length=200)
    user_id = models.CharField(max_length=200, null=False)
    item_name = models.CharField(max_length=200, null=False)
    request_quantity = models.SmallIntegerField(null=False)
    status = models.CharField(max_length=200, null=False)
    comment = models.CharField(max_length=200, null=False)
    time_requested = models.TimeField()
    def __str__(self):
        return self.item_name + " " + self.request_id

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
    