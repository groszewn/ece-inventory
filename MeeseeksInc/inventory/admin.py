from django.contrib import admin

from .models import Item, Instance, Tag, Request, Disbursement, Item_Log, Custom_Field, Custom_Field_Value, ShoppingCartInstance
 
# Register your models here.
 
admin.site.register(Item)
admin.site.register(Instance)
admin.site.register(Request)
admin.site.register(Tag)
admin.site.register(Disbursement)
admin.site.register(Item_Log)
admin.site.register(Custom_Field)
admin.site.register(Custom_Field_Value)
admin.site.register(ShoppingCartInstance)

