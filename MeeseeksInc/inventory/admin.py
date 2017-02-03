from django.contrib import admin
 
from .models import Item, Instance, Tag, Request, Disbursement
# from .models import Item, Instance, Request, Disbursement
 
# Register your models here.
 
class QuestionAdmin(admin.ModelAdmin):
    fieldsets = [
        (None,               {'fields': ['question_text']}),
        ('Date information', {'fields': ['pub_date']}),
    ]
 
# admin.site.register(Question, QuestionAdmin)
# admin.site.register(Choice)
admin.site.register(Item)
admin.site.register(Instance)
admin.site.register(Request)
admin.site.register(Tag)
admin.site.register(Disbursement)
