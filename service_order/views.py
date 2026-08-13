from django.shortcuts import render, redirect, get_object_or_404
from service_order.models import Client, Scale, ServiceOrder, Part, TimeService, Company
from service_order.forms import NewClientModelForm, NewScaleModelForm, ServiceOrderForm, PartFormset, TimeFormset
from django.views import View
from django.views.generic import ListView, CreateView, DetailView, UpdateView, DeleteView
from django.db.models import Q
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator


@method_decorator(login_required(login_url='login'), name='dispatch')
class ClientListView(ListView):

    model = Client
    template_name = 'search_client.html'
    context_object_name = 'clients'
    
    def get_queryset(self):
        clients =  super().get_queryset().order_by('name')
        search = self.request.GET.get('search')

        if search:
            clients = clients.filter(document__icontains=search)
        return clients
    

@method_decorator(login_required(login_url='login'), name='dispatch')
class NewClientCreateView(CreateView):

    model = Client
    form_class = NewClientModelForm
    template_name = 'new_client.html'
    success_url = '/search_client/'

@method_decorator(login_required(login_url='login'), name='dispatch')
class NewScaleCreateView(CreateView):

    model = Scale
    form_class = NewScaleModelForm
    template_name = 'new_scale.html'
    success_url = '/new_scale/'


@method_decorator(login_required(login_url='login'), name='dispatch')
class ScaleListView(ListView):
    model = Scale
    template_name = 'search_scale.html'
    context_object_name = 'scales'

    def get_queryset(self):
        scales = super().get_queryset()
        search = self.request.GET.get('search')

        if search:
            scales = scales.filter(serie__icontains=search)
        return scales
 

@method_decorator(login_required(login_url='login'), name='dispatch')
class ScaleDetailView(DetailView):
    model = Scale
    template_name = 'scale_detail.html'
    context_object_name = 'scale'


@method_decorator(login_required(login_url='login'), name='dispatch')
class ServiceOrderView(View):


    def get(self, request, id_client, id_scale):

        client = get_object_or_404(Client, id=id_client)
        scale = get_object_or_404(Scale, id=id_scale)

        service_order_form = ServiceOrderForm(user=request.user)
        parts_useds_form = PartFormset()
        time_service_order_form = TimeFormset()

        return render(request, 'service_order.html', {'form':service_order_form, 'parts_useds':parts_useds_form, 'time_service':time_service_order_form, 'client':client, 'scale':scale})
    
    def post(self, request, id_client, id_scale):

        client = get_object_or_404(Client, id=id_client)
        scale = get_object_or_404(Scale, id=id_scale)

        service_order_form = ServiceOrderForm(request.POST, user=request.user)
        parts_useds_form = PartFormset(request.POST)
        time_service_order_form = TimeFormset(request.POST)

        if service_order_form.is_valid() and parts_useds_form.is_valid() and time_service_order_form.is_valid():
            stamp = service_order_form.cleaned_data['stamp']
            if stamp:
                stamp.status = 'UTILIZADO'
                stamp.save()

            service_order = service_order_form.save(commit=False)
            service_order.client = client
            service_order.scale = scale
            service_order.date = timezone.now()
            service_order.user = request.user
            signature_text = request.POST.get('client_signature')
            if signature_text:
                service_order.signature = signature_text
            service_order.save()
    
            parts_useds_form.instance = service_order
            parts_useds_form.save()

            time_service_order_form.instance = service_order
            time_service_order_form.save()

            return redirect('client_detail',id_client)

        return render(request, 'service_order.html', {'form':service_order_form, 'parts_useds':parts_useds_form, 'time_service': time_service_order_form ,'client':client, 'scale':scale})


@method_decorator(login_required(login_url='login'), name='dispatch')
class ServiceOrderListView(ListView):

    model = ServiceOrder
    template_name = 'list_service_order.html'
    context_object_name = 'service_order'

    def get_queryset(self):
        service_order_list = super().get_queryset().order_by('-date')
        search = self.request.GET.get('search')
        date_filter = self.request.GET.get('date_filter')

        if not self.request.user.is_superuser:
        
            service_order_list = service_order_list.filter(user=self.request.user.id).order_by('-date')


        if date_filter:
            service_order_list = service_order_list.filter(date__date=date_filter)

        if search:
            if search.isdigit():
                service_order_list=service_order_list.filter(id=search)
            else:
                service_order_list = service_order_list.filter(Q(client__name__icontains=search) | Q(client__city__icontains=search) | Q(client__document=search))
        return service_order_list
    

@method_decorator(login_required(login_url='login'), name='dispatch')
class ServiceOrderDetailView(DetailView):

    model = ServiceOrder
    template_name = 'service_order_detail.html'
    context_object_name = 'os'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        service_order = context['os']
        context['parts_useds'] = Part.objects.filter(service_order=service_order )
        context['time_service'] = TimeService.objects.filter(service_order=service_order)
        context['company'] = Company.objects.first()
        return context
    
@method_decorator(login_required(login_url='login'), name='dispatch')
class ClientDetailView(DetailView):

    model = Client
    template_name = 'client_detail.html'
    context_object_name = 'client'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        client = context['client']
        context['scales'] = Scale.objects.filter(client=client)

        return context

@method_decorator(login_required(login_url='login'), name='dispatch')
class ClientUpdateView(UpdateView):
    model = Client
    form_class = NewClientModelForm
    template_name = 'client_update.html'
    success_url = '/search_client/'

@method_decorator(login_required(login_url='login'), name='dispatch')
class ScaleUpdateView(UpdateView):
    model = Scale
    form_class = NewScaleModelForm
    template_name = 'scale_update.html'
    success_url = '/search_scale/'

@method_decorator(login_required(login_url='login'), name='dispatch')
class ServiceOrderUpdateView(UpdateView):
    model = ServiceOrder
    form_class = ServiceOrderForm
    template_name = 'os_update.html'
    context_object_name = 'os'
    success_url = '/list_os/'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['company'] = Company.objects.first()
        if self.request.method == 'POST':
            context['parts_useds'] = PartFormset(self.request.POST, instance=self.object)
            context['time_service'] = TimeFormset(self.request.POST, instance=self.object)
        else:
            context['parts_useds'] = PartFormset(instance = self.object)
            context['time_service'] = TimeFormset(instance=self.object)
        
        return context
    
    def form_valid(self, form):
        context = self.get_context_data()
        parts_useds = context['parts_useds']
        time_service = context['time_service']
        self.object = form.save()
        if parts_useds.is_valid() and time_service.is_valid():
            parts_useds.instance = self.object
            parts_useds.save()
            time_service.instace = self.object
            time_service.save()
        return super().form_valid(form)
    

@method_decorator(login_required(login_url='login'), name='dispatch')
class ScaleDeleteView(DeleteView):
    model = Scale
    template_name = 'scale_delete.html'
    success_url = '/search_scale/'
    context_object_name = 'scale'


@method_decorator(login_required(login_url='login'), name='dispatch')
class HomeView(View):
    def get(self, request):
        return render(request, 'home.html')



    

