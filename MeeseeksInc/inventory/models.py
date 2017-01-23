from django.db import models
# create table item_table ( 
# item_name varchar PRIMARY KEY, 
# quantity smallint NOT NULL, 
# price float(2) );

class Item(models.Model):
    item_name = models.CharField(primary_key=True, max_length=200)
    quantity = models.SmallIntegerField(null=False);
    price = models.FloatField(2);
    def __str__(self):
        return self.item_name
    
# create table tag_table ( 
# item_name varchar NOT NULL, 
# tag varchar NOT NULL );

class Tag(models.Model):
    item_name = models.CharField(max_length=200, null=False)
    tag = models.CharField(max_length=200, null=False)
    def __str__(self):
        return self.item_name + " " + self.tag
    
# create table item_table ( 
# instance_id varchar PRIMARY KEY, 
# location varchar, 
# status varchar, 
# available varchar, 
# model_number varchar, 
# item_name varchar NOT NULL );

class Instance(models.Model):
    instance_id = models.CharField(primary_key=True, max_length=200)
    location = models.CharField(max_length=200)
    status = models.CharField(max_length=200)
    available = models.CharField(max_length=200)
    model_number = models.CharField(max_length=200)
    item_name = models.CharField(max_length=200, null=False)
    
    def __str__(self):
        return self.item_name + " " + self.instance_id

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

class Question(models.Model):
    question_text = models.CharField(max_length=200)
    pub_date = models.DateTimeField('date published') 
    #tells Django that this is a Data Time Field
    def __str__(self):
        return self.question_text

class Choice(models.Model):
    #as you can see, this is adding the field "question" to "choice" 
    question = models.ForeignKey(Question, on_delete=models.CASCADE) 
    choice_text = models.CharField(max_length=200)  #tells Django that this is a Character Field
    votes = models.IntegerField(default=0)  #tells Django that this is a Integer Field
    def __str__(self):
        return self.choice_text
    