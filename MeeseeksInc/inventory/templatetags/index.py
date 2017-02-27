from django import template
register = template.Library()

@register.filter
def index(List, i):
    return List[int(i)]

@register.filter
def length(List):
    return len(List)

@register.simple_tag
def indexOfFieldProperty(fieldList, obj):
    index = -1
    for i, field in enumerate(fieldList):
        print(field.field_name)
        print(obj)
        if field.field_name == obj:
            index = i
    return i