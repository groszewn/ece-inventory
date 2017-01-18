from django.contrib import admin

from .models import Question #don't forget to import from the models so you can access them
# Register your models here.
admin.site.register(Question)