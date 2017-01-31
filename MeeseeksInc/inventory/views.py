import random

from django.db.models import F
from django.http import HttpResponseRedirect
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views import generic
from django.views.generic.edit import FormMixin
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin

from .forms import RequestForm
from .forms import RequestEditForm
from .forms import SearchForm
from .models import Question, Choice, Instance, Request, Item, Tag


################ DEFINE VIEWS AND RESPECTIVE FILES ##################
class IndexView(FormMixin, LoginRequiredMixin, generic.ListView):  ## ListView to display a list of objects
    login_url = "/login/"
    template_name = 'inventory/index.html'
    context_object_name = 'item_list'
    form_class = SearchForm

    def get_context_data(self, **kwargs):
        context = super(IndexView, self).get_context_data(**kwargs)
        context['request_list'] = Request.objects.all()
        context['item_list'] = Item.objects.all()
        #content['search_list'] = Item.objects.all()
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
        context['request_list'] = Request.objects.all()
        context['item_list'] = Item.objects.all()
        return context
    def get_queryset(self):
        """Return the last five published questions."""
        return Instance.objects.order_by('item')[:5]
    
class DetailView(LoginRequiredMixin, generic.DetailView): ## DetailView to display detail for the object
    login_url = "/login/"
    model = Item
    template_name = 'inventory/detail.html' # w/o this line, default would've been inventory/<model_name>.html

def search_form(request):
    if request.method == "POST":
        form = SearchForm(request.POST)
        if form.is_valid():
            picked = form.cleaned_data.get('tags')
            tag_list = []
            search_list = []
            for pickedTag in picked:
                tagQS = Tag.objects.filter(tag = pickedTag)
                for oneTag in tagQS:
                    search_list.append(Item.objects.get(pk = oneTag.item_name))
            item_list = Item.objects.all()
            request_list = Request.objects.all()
            return render(request,'inventory/search_result.html', {'picked': picked,'item_list': item_list,'request_list': request_list,'search_list': set(search_list)})
    else:
        form = SearchForm()
    return render(request, 'inventory/search.html', {'form': form})

def edit_request(request, pk):
    instance = Request.objects.get(request_id=pk)
    if request.method == "POST":
        form = RequestEditForm(request.POST, instance=instance, initial = {'item_field': instance.item_name})
        if form.is_valid():
            post = form.save(commit=False)
            post.item_name = form['item_field'].value()
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
            post.item_name = form['item_field'].value()
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
    
## FROM THE DJANGO TUTORIAL ##
@login_required(login_url='/login/')
def vote(request, question_id):
    question = get_object_or_404(Question, pk=question_id)
    try:
        selected_choice = question.choice_set.get(pk=request.POST['choice'])
    except (KeyError, Choice.DoesNotExist):
        # Redisplay the question voting form.
        return render(request, 'inventory/detail.html', {
            'question': question,
            'error_message': "You didn't select a choice.",
        })
    else:
#         selected_choice.update(votes=F('votes') + 1)

        selected_choice.votes = F('votes') + 1
        selected_choice.save()
        # Always return an HttpResponseRedirect after successfully dealing
        # with POST data. This prevents data from being posted twice if a
        # user hits the Back button.
        return HttpResponseRedirect(reverse('inventory:results', args=(question.id,)))
