from django import template
register = template.Library()

@register.filter(name='klass')
def klass(ob):
    return str(ob.__class__.__name__)