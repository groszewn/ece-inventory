from django.contrib import admin

from .models import Item, Instance, Request, Tag, UserQuery, Disbursement
# from .models import Item, Instance, Request, UserQuery, Disbursement
from .models import Choice, Question #don't forget to import from the models so you can access them


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
