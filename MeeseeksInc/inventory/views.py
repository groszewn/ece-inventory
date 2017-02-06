import random
  
from django.db.models import F
from django.db import connection, transaction
from django.http import HttpResponseRedirect
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views import generic
from django.views.generic.edit import FormMixin
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from .forms import RequestForm
from .forms import RequestEditForm
from .forms import SearchForm
# from .models import Question, Choice, Instance, Request, Item, Disbursement
from .models import Question, Choice, Instance, Request, Item, Tag, Disbursement
#   
################ DEFINE VIEWS AND RESPECTIVE FILES ##################
class IndexView(FormMixin, LoginRequiredMixin, generic.ListView):  ## ListView to display a list of objects
    login_url = "/login/"
    template_name = 'inventory/index.html'
    context_object_name = 'item_list'
#     form_class = SearchForm
  
    def get_context_data(self, **kwargs):
        context = super(IndexView, self).get_context_data(**kwargs)
        context['request_list'] = Request.objects.filter(user_id=self.request.user.username)
        context['item_list'] = Item.objects.all()
        context['disbursed_list'] = Disbursement.objects.filter(user_name=self.request.user.username)
        return context
    def get_queryset(self):
        """Return the last five published questions."""
        return Instance.objects.order_by('item')[:5]
        
class SearchResultView(FormMixin, LoginRequiredMixin, generic.ListView):  ## ListView to display a list of objects
    login_url = "/login/"
    template_name = 'inventory/search_result.html'
    context_object_name = 'item_list'
   
    def get_context_data(self, **kwargs):
        context = super(IndexView, self).get_context_data(**kwargs)
        context['request_list'] = Request.objects.filter(user_id=self.request.user.username)
        context['item_list'] = Item.objects.all()
        context['disbursed_list'] = Disbursement.objects.filter(user_name=self.request.user.username)
        return context
    def get_queryset(self):
        """Return the last five published questions."""
        return Instance.objects.order_by('item')[:5]
      
class DetailView(LoginRequiredMixin, generic.DetailView): ## DetailView to display detail for the object
    login_url = "/login/"
    model = Item
    context_object_name = 'tag_list'
    context_object_name = 'item'
    context_object_name = 'request_list'
    template_name = 'inventory/detail.html' # w/o this line, default would've been inventory/<model_name>.html
       
    def get_context_data(self, **kwargs):
        context = super(DetailView, self).get_context_data(**kwargs)
        context['item'] = self.get_object()
        tags = Tag.objects.filter(item_name=self.get_object().item_name)
        context['last_tag'] = tags.reverse()[0]
        tags = tags.reverse()[1:]
        context['tag_list'] = tags
        context['request_list'] = Request.objects.filter(user_id=self.request.user.username, item_name=self.get_object().item_name, status = "Pending")
        return context
      
def check_login(request):
    if request.user.is_staff:
        return HttpResponseRedirect(reverse('custom_admin:index'))
    else:
        return HttpResponseRedirect(reverse('inventory:index'))
      
def search_form(request):
    if request.method == "POST":
        form = SearchForm(request.POST)
        if form.is_valid():
            picked = form.cleaned_data.get('tags')
            keyword = form.cleaned_data.get('keyword')
            tag_list = []
            keyword_list = []
            for item in Item.objects.all():
                if (keyword is not "") and (keyword in item.item_name) or ((item.description is not None) and (keyword in item.description)) \
                    or ((item.model_number is not None) and (keyword in item.model_number)) or ((item.location is not None) and (keyword in item.location)): 
                    keyword_list.append(item)
            for pickedTag in picked:
                tagQS = Tag.objects.filter(tag = pickedTag)
                for oneTag in tagQS:
                    tag_list.append(Item.objects.get(pk = oneTag.item_name))
            search_list = tag_list + keyword_list
            item_list = Item.objects.all()
            request_list = Request.objects.all()
            return render(request,'inventory/search_result.html', {'item_list': item_list,'request_list': request_list,'search_list': set(search_list)})
    else:
        form = SearchForm()
    return render(request, 'inventory/search.html', {'form': form})
  
def edit_request(request, pk):
    instance = Request.objects.get(request_id=pk)
    if request.method == "POST":
        form = RequestEditForm(request.POST, instance=instance, initial = {'item_field': instance.item_name})
        if form.is_valid():
            messages.success(request, 'You just edited the request successfully.')
            post = form.save(commit=False)
<<<<<<< HEAD
            post.item_name = form['item_field'].value()
#             name_requested = form['item_field'].value()
#             item_requested = Item.objects.get(item_name = name_requested)
#             post.item_name = item_requested
=======
            post.item_id = form['item_field'].value()
#             post.item_name = Item.objects.get(item_id = post.item_id).item_name
            post.item_name = Item.objects.get(item_id = post.item_id)
>>>>>>> origin/Kei
            post.status = "Pending"
            post.time_requested = timezone.localtime(timezone.now())
            post.save()
            return redirect('/')
    else:
        form = RequestEditForm(instance=instance, initial = {'item_field': instance.item_name})
    return render(request, 'inventory/request_edit.html', {'form': form})
  
class ResultsView(LoginRequiredMixin, generic.DetailView):
    login_url = "/login/"
    model = Question
    template_name = 'inventory/results.html' # w/o this line, default would've been inventory/<model_name>.html
  
@login_required(login_url='/login/')
def post_new_request(request):
    if request.method == "POST":
        form = RequestForm(request.POST) # create request-form with the data from the request 
        if form.is_valid():
            post = form.save(commit=False)
            post.item_id = form['item_field'].value()
#             post.item_name = Item.objects.get(item_id = post.item_id).item_name
            post.item_name = Item.objects.get(item_id = post.item_id)
            post.user_id = request.user.username
            post.status = "Pending"
            post.time_requested = timezone.localtime(timezone.now())
            post.save()
            return redirect('/')
    else:
        form = RequestForm() # blank request form with no data yet
    return render(request, 'inventory/request_create.html', {'form': form})
  
class request_detail(generic.DetailView):
    model = Request
    template_name = 'inventory/request_detail.html'
      
class request_cancel_view(generic.DetailView):
    model = Request
    template_name = 'inventory/request_cancel.html'
      
def cancel_request(self, pk):
    Request.objects.get(request_id=pk).delete()
    return redirect('/')
