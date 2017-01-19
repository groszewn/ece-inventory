from django.db import models


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