from django.shortcuts import render, redirect, get_object_or_404
import csv
import io

from service_order.models import (
    Client,
    EccentricityTest,
    FidelityTest,
    Scale,
    ServiceOrder,
    Part,
    Stamp,
    StampDelivery,
    TechnicalReport,
    TimeService,
    WeighingTest,
)
from service_order.forms import (
    NewClientModelForm,
    NewScaleModelForm,
    ServiceOrderForm,
    PartFormset,
    TimeFormset,
    TechnicalReportForm,
    TechnicalMeasurementForm,
    FidelityTestFormset,
    EccentricityTestFormset,
    WeighingTestFormset,
)
from service_order.forms_stamps import StampBulkDeliveryForm, StampCreateForm, StampDeliveryForm
from service_order.services import (
    consume_stamp_for_os,
    damage_delivery,
    distribute_stamp,
    delete_service_order,
    complete_technical_report,
    cancel_technical_report,
    ensure_technical_report_rows,
    next_os_number,
    snapshot_technical_report,
    next_technical_report_number,
)
from django.views import View
from django.views.generic import ListView, CreateView, DetailView, UpdateView, DeleteView, TemplateView
from django.db import transaction
from django.db.models import Count, Q
from django.forms import inlineformset_factory
from django.utils import timezone
from django.templatetags.static import static
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.http import HttpResponse, HttpResponseRedirect

from core.emails import send_os_signed_email
from core.audit import record_audit
from core.models import AuditLog
from core.permissions import AdminRequiredMixin, StaffRequiredMixin, TenantRequiredMixin
from tenants.services import (
    RESOURCE_OSES,
    get_plan,
    period_bounds,
    plan_limit_decorator,
)


class TenantQuerysetMixin:
    """Escopo por tenant; superuser enxerga tudo."""

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_superuser:
            return qs
        tenant = getattr(user, 'tenant', None)
        if tenant is None:
            return qs.none()
        return qs.filter(tenant=tenant)


def _tenant_of(user):
    if user.is_superuser:
        return None
    return getattr(user, 'tenant', None)


@method_decorator(login_required(login_url='login'), name='dispatch')
class ClientListView(TenantQuerysetMixin, ListView):

    model = Client
    template_name = 'search_client.html'
    context_object_name = 'clients'

    def get_queryset(self):
        clients = super().get_queryset().order_by('name')
        search = self.request.GET.get('search')

        if search:
            clients = clients.filter(document__icontains=search)
        return clients


@method_decorator(login_required(login_url='login'), name='dispatch')
class NewClientCreateView(TenantRequiredMixin, CreateView):

    model = Client
    form_class = NewClientModelForm
    template_name = 'new_client.html'
    success_url = '/search_client/'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['tenant'] = _tenant_of(self.request.user)
        return kwargs

    def form_valid(self, form):
        tenant = _tenant_of(self.request.user)
        if tenant is None and not self.request.user.is_superuser:
            form.add_error(None, 'Usuário sem tenant ativo.')
            return self.form_invalid(form)
        if tenant is not None:
            form.instance.tenant = tenant
        return super().form_valid(form)


@method_decorator(login_required(login_url='login'), name='dispatch')
class NewScaleCreateView(TenantRequiredMixin, CreateView):

    model = Scale
    form_class = NewScaleModelForm
    template_name = 'new_scale.html'
    success_url = '/new_scale/'

    def get_initial(self):
        initial = super().get_initial()
        client_id = self.request.GET.get('client')
        if client_id:
            client_qs = Client.objects.filter(pk=client_id)
            if not self.request.user.is_superuser:
                client_qs = client_qs.filter(tenant=self.request.user.tenant)
            client = client_qs.first()
            if client:
                initial['client'] = client.pk
        return initial

    def form_valid(self, form):
        tenant = _tenant_of(self.request.user)
        if tenant is None and not self.request.user.is_superuser:
            form.add_error(None, 'Usuário sem tenant ativo.')
            return self.form_invalid(form)
        if tenant is not None:
            form.instance.tenant = tenant
            if form.cleaned_data.get('client'):
                form.instance.client = form.cleaned_data['client']
        return super().form_valid(form)


@method_decorator(login_required(login_url='login'), name='dispatch')
class ScaleListView(TenantQuerysetMixin, ListView):
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
class ScaleDetailView(TenantQuerysetMixin, DetailView):
    model = Scale
    template_name = 'scale_detail.html'
    context_object_name = 'scale'


@method_decorator(plan_limit_decorator(RESOURCE_OSES, redirect_name='billing'), name='dispatch')
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
            stamp_delivery = service_order_form.cleaned_data.get('stamp')
            tenant = getattr(client, 'tenant', None) or getattr(request.user, 'tenant', None)
            signature_text = request.POST.get('client_signature') or request.POST.get('signature')

            plan = get_plan(tenant)
            if plan is not None and plan.required_signature and not signature_text:
                service_order_form.add_error(
                    None,
                    'O plano contratado exige assinatura do cliente para emitir a O.S.',
                )
                return render(
                    request,
                    'service_order.html',
                    {
                        'form': service_order_form,
                        'parts_useds': parts_useds_form,
                        'time_service': time_service_order_form,
                        'client': client,
                        'scale': scale,
                    },
                )

            try:
                with transaction.atomic():
                    service_order = service_order_form.save(commit=False)
                    service_order.client = client
                    service_order.scale = scale
                    service_order.date = timezone.now()
                    service_order.user = request.user
                    service_order.tenant = tenant
                    if tenant is not None:
                        service_order.number = next_os_number(tenant)
                    if signature_text:
                        service_order.signature = signature_text
                    service_order.save()
                    record_audit(
                        tenant=tenant,
                        actor=request.user,
                        action=AuditLog.ACTION_CREATE,
                        object_type='ServiceOrder',
                        object_id=service_order.pk,
                        metadata={'number': service_order.display_number},
                        request=request,
                    )

                    if stamp_delivery is not None:
                        consume_stamp_for_os(
                            delivery_id=stamp_delivery.pk,
                            service_order=service_order,
                        )

                    parts_useds_form.instance = service_order
                    parts_useds_form.save()

                    time_service_order_form.instance = service_order
                    time_service_order_form.save()

                    if service_order.signature:
                        captured = service_order
                        transaction.on_commit(
                            lambda: send_os_signed_email(captured)
                        )
            except Exception as exc:
                messages.error(request, str(exc))
                return render(
                    request,
                    'service_order.html',
                    {
                        'form': service_order_form,
                        'parts_useds': parts_useds_form,
                        'time_service': time_service_order_form,
                        'client': client,
                        'scale': scale,
                    },
                )

            return redirect('client_detail', id_client)

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
        date_from = self.request.GET.get('date_from')
        date_to = self.request.GET.get('date_to')

        user = self.request.user
        if not user.is_superuser:
            tenant = getattr(user, 'tenant', None)
            if tenant is not None:
                service_order_list = service_order_list.filter(tenant=tenant)
            role = getattr(user, 'role', None)
            if role == 'TECHNICIAN' or role is None:
                service_order_list = service_order_list.filter(user=user.id)

        if date_filter:
            service_order_list = service_order_list.filter(date__date=date_filter)
        if date_from:
            service_order_list = service_order_list.filter(date__date__gte=date_from)
        if date_to:
            service_order_list = service_order_list.filter(date__date__lte=date_to)

        if search:
            if search.isdigit():
                service_order_list = (
                    service_order_list.filter(Q(id=search) | Q(number=int(search)))
                )
            else:
                service_order_list = service_order_list.filter(
                    Q(client__name__icontains=search)
                    | Q(client__city__icontains=search)
                    | Q(client__document=search)
                )
        return service_order_list


@method_decorator(login_required(login_url='login'), name='dispatch')
class ServiceOrderDetailView(TenantQuerysetMixin, DetailView):

    model = ServiceOrder
    template_name = 'service_order_detail.html'
    context_object_name = 'os'

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        role = getattr(user, 'role', None)
        if role == 'TECHNICIAN' or (role is None and not user.is_superuser):
            qs = qs.filter(user=user)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        service_order = context['os']
        context['parts_useds'] = Part.objects.filter(service_order=service_order )
        context['time_service'] = TimeService.objects.filter(service_order=service_order)
        context['tenant'] = service_order.tenant
        return context


@method_decorator(login_required(login_url='login'), name='dispatch')
class ServiceOrderPrintView(TenantQuerysetMixin, DetailView):

    model = ServiceOrder
    template_name = 'service_order_print.html'
    context_object_name = 'os'

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        role = getattr(user, 'role', None)
        if role == 'TECHNICIAN' or (role is None and not user.is_superuser):
            qs = qs.filter(user=user)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        service_order = context['os']
        context['parts_useds'] = Part.objects.filter(service_order=service_order)
        context['time_service'] = TimeService.objects.filter(service_order=service_order)
        context['tenant'] = service_order.tenant
        return context


@method_decorator(login_required(login_url='login'), name='dispatch')
class TechnicalReportListView(TenantQuerysetMixin, ListView):
    model = TechnicalReport
    template_name = 'technical_report_list.html'
    context_object_name = 'reports'

    def get_queryset(self):
        reports = super().get_queryset().select_related(
            'service_order__client', 'service_order__scale', 'tenant'
        ).order_by('-created_at', '-pk')
        user = self.request.user
        if not user.is_superuser and getattr(user, 'role', None) in ('TECHNICIAN', None):
            reports = reports.filter(service_order__user=user)
        search = self.request.GET.get('search', '').strip()
        if search:
            filters = Q(service_order__client__name__icontains=search)
            if search.isdigit():
                filters |= Q(number=int(search)) | Q(service_order__number=int(search))
            reports = reports.filter(filters)
        status = self.request.GET.get('status', '').strip()
        if status in {choice[0] for choice in TechnicalReport.STATUS_CHOICES}:
            reports = reports.filter(status=status)
        return reports


def _technical_report_formsets(report, data=None):
    configurations = [
        (FidelityTest, FidelityTestFormset, 'fidelitytest', 3),
        (EccentricityTest, EccentricityTestFormset, 'eccentricitytest', 6),
        (WeighingTest, WeighingTestFormset, 'weighingtest', 22),
    ]
    result = []
    for model, formset_class, prefix, total in configurations:
        existing = model.objects.filter(report=report).count() if report.pk else 0
        formset_class = inlineformset_factory(
            TechnicalReport,
            model,
            form=TechnicalMeasurementForm,
            fields=['sequence', 'load_kg', 'indication_kg', 'ema_kg'],
            extra=max(0, total - existing),
            can_delete=False,
        )
        initial = [{'sequence': index} for index in range(1, total + 1)] if not report.pk else None
        result.append(formset_class(data, instance=report, prefix=prefix, initial=initial))
    return result


def _technical_measurements_complete(formsets):
    required_measurements = 11
    checked_measurements = 0
    for formset in formsets:
        for form in formset.forms:
            if checked_measurements >= required_measurements:
                return True
            if not all(form.cleaned_data.get(field) is not None for field in ('load_kg', 'indication_kg', 'ema_kg')):
                return False
            checked_measurements += 1
    return checked_measurements >= required_measurements


@method_decorator(login_required(login_url='login'), name='dispatch')
class TechnicalReportView(TenantRequiredMixin, TenantQuerysetMixin, View):
    template_name = 'technical_report.html'

    def get_queryset(self):
        qs = ServiceOrder.objects.select_related('client', 'scale', 'tenant')
        user = self.request.user
        if not user.is_superuser and getattr(user, 'role', None) in ('TECHNICIAN', None):
            qs = qs.filter(user=user)
        return qs

    def get_object(self, pk):
        return get_object_or_404(self.get_queryset(), pk=pk)

    def _context(self, order, form, formsets):
        report = getattr(order, 'technical_report', None)
        return {
            'os': order,
            'report': report,
            'form': form,
            'fidelity_formset': formsets[0],
            'eccentricity_formset': formsets[1],
            'weighing_formset': formsets[2],
            'tenant': order.tenant,
        }

    def _report(self, order):
        return getattr(order, 'technical_report', None) or TechnicalReport(
            service_order=order,
            tenant=order.tenant,
        )

    def get(self, request, pk):
        order = self.get_object(pk)
        if order.scale.scale_type not in {
            Scale.TYPE_ROAD, Scale.TYPE_RAIL, Scale.TYPE_ROAD_RAIL,
        }:
            return redirect('os_detail', pk=order.pk)
        report = self._report(order)
        formsets = _technical_report_formsets(report)
        return render(request, self.template_name, self._context(order, TechnicalReportForm(instance=report), formsets))

    def post(self, request, pk):
        order = self.get_object(pk)
        if order.scale.scale_type not in {
            Scale.TYPE_ROAD, Scale.TYPE_RAIL, Scale.TYPE_ROAD_RAIL,
        }:
            return redirect('os_detail', pk=order.pk)
        report = self._report(order)
        tenant = order.tenant
        if tenant is None:
            messages.error(request, 'A O.S. precisa estar vinculada a um tenant.')
            return redirect('os_detail', pk=order.pk)
        plan = get_plan(tenant)
        form = TechnicalReportForm(
            request.POST,
            instance=report,
            require_signature=bool(plan and plan.required_signature),
        )
        formsets = _technical_report_formsets(report, request.POST)
        valid_formsets = all(formset.is_valid() for formset in formsets)
        completing = request.POST.get('action') == 'complete'
        if form.is_valid() and valid_formsets:
            is_new = report.pk is None
            with transaction.atomic():
                report = form.save(commit=False)
                report.service_order = order
                report.tenant = tenant
                if report.number is None:
                    report.number = next_technical_report_number(tenant)
                report.save()
                for formset in formsets:
                    formset.instance = report
                    for measurement in formset.save():
                        if measurement.load_kg is not None and measurement.indication_kg is not None:
                            measurement.error_kg = measurement.indication_kg - measurement.load_kg
                            measurement.save(update_fields=['error_kg'])
                ensure_technical_report_rows(report)
                if completing:
                    complete_technical_report(report)
                else:
                    snapshot_technical_report(report).save()
                record_audit(
                    tenant=tenant,
                    actor=request.user,
                    action=AuditLog.ACTION_CREATE if is_new else AuditLog.ACTION_UPDATE,
                    object_type='TechnicalReport',
                    object_id=report.pk,
                    metadata={'service_order': order.display_number, 'status': report.status},
                    request=request,
                )
            messages.success(request, 'Relatório técnico salvo com sucesso.')
            return redirect('technical_report_print' if report.status == TechnicalReport.STATUS_COMPLETED else 'technical_report', pk=order.pk)
        return render(request, self.template_name, self._context(order, form, formsets))


@method_decorator(login_required(login_url='login'), name='dispatch')
class TechnicalReportPrintView(TenantQuerysetMixin, DetailView):
    model = ServiceOrder
    template_name = 'technical_report_print.html'
    context_object_name = 'os'

    def get_queryset(self):
        qs = super().get_queryset().select_related('client', 'scale', 'tenant').filter(
            scale__scale_type__in=(Scale.TYPE_ROAD, Scale.TYPE_RAIL, Scale.TYPE_ROAD_RAIL),
            technical_report__status=TechnicalReport.STATUS_COMPLETED,
        )
        user = self.request.user
        if getattr(user, 'role', None) == 'TECHNICIAN' or (getattr(user, 'role', None) is None and not user.is_superuser):
            qs = qs.filter(user=user)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        order = context['os']
        context['report'] = order.technical_report
        context['tenant'] = order.tenant
        logo = order.tenant.logo if order.tenant else None
        context['tenant_logo_url'] = (
            logo.url if logo and logo.storage.exists(logo.name)
            else static('img/logo_euller.png')
        )
        record_audit(
            tenant=order.tenant,
            actor=self.request.user,
            action=AuditLog.ACTION_EXPORT,
            object_type='TechnicalReport',
            object_id=order.technical_report.pk,
            metadata={'service_order': order.display_number, 'format': 'print'},
            request=self.request,
        )
        return context


@method_decorator(login_required(login_url='login'), name='dispatch')
class TechnicalReportDeleteView(TenantRequiredMixin, View):
    def post(self, request, pk):
        tenant = getattr(request.user, 'tenant', None)
        report = get_object_or_404(
            TechnicalReport.objects.select_related('service_order'),
            pk=pk,
            tenant=tenant,
        )
        if getattr(request.user, 'role', None) == 'TECHNICIAN' and report.service_order.user_id != request.user.pk:
            raise PermissionDenied('Técnico só pode excluir seus próprios relatórios.')
        report_number = report.display_number
        report.delete()
        messages.success(request, f'Relatório técnico #{report_number} excluído.')
        return redirect('technical_report_list')


@method_decorator(login_required(login_url='login'), name='dispatch')
class TechnicalReportCancelView(StaffRequiredMixin, TenantRequiredMixin, View):
    def post(self, request, pk):
        order = get_object_or_404(
            ServiceOrder.objects.filter(tenant=getattr(request.user, 'tenant', None)),
            pk=pk,
        )
        report = get_object_or_404(TechnicalReport, service_order=order)
        cancel_technical_report(report, request.POST.get('reason', ''))
        record_audit(
            tenant=order.tenant,
            actor=request.user,
            action=AuditLog.ACTION_UPDATE,
            object_type='TechnicalReport',
            object_id=report.pk,
            metadata={'service_order': order.display_number, 'status': report.status},
            request=request,
        )
        messages.success(request, 'Relatório técnico cancelado.')
        return redirect('technical_report', pk=order.pk)


@method_decorator(login_required(login_url='login'), name='dispatch')
class TechnicalReportReopenView(AdminRequiredMixin, TenantRequiredMixin, View):
    def post(self, request, pk):
        order = get_object_or_404(
            ServiceOrder.objects.filter(tenant=getattr(request.user, 'tenant', None)),
            pk=pk,
        )
        report = get_object_or_404(
            TechnicalReport,
            service_order=order,
            status=TechnicalReport.STATUS_CANCELED,
        )
        report.status = TechnicalReport.STATUS_DRAFT
        report.canceled_at = None
        report.canceled_reason = ''
        report.save(update_fields=['status', 'canceled_at', 'canceled_reason', 'updated_at'])
        record_audit(
            tenant=order.tenant,
            actor=request.user,
            action=AuditLog.ACTION_UPDATE,
            object_type='TechnicalReport',
            object_id=report.pk,
            metadata={'service_order': order.display_number, 'status': report.status},
            request=request,
        )
        messages.success(request, 'Relatório técnico reaberto como rascunho.')
        return redirect('technical_report', pk=order.pk)


@method_decorator(login_required(login_url='login'), name='dispatch')
class ClientDetailView(TenantQuerysetMixin, DetailView):
    model = Client
    template_name = 'client_detail.html'
    context_object_name = 'client'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        client = context['client']
        context['scales'] = Scale.objects.filter(client=client)

        return context

@method_decorator(login_required(login_url='login'), name='dispatch')
class ClientUpdateView(TenantRequiredMixin, TenantQuerysetMixin, UpdateView):
    model = Client
    form_class = NewClientModelForm
    template_name = 'client_update.html'
    success_url = '/search_client/'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['tenant'] = getattr(self.object, 'tenant', None)
        return kwargs


@method_decorator(login_required(login_url='login'), name='dispatch')
class ScaleUpdateView(TenantRequiredMixin, TenantQuerysetMixin, UpdateView):
    model = Scale
    form_class = NewScaleModelForm
    template_name = 'scale_update.html'
    success_url = '/search_scale/'


@method_decorator(login_required(login_url='login'), name='dispatch')
class ServiceOrderUpdateView(TenantRequiredMixin, TenantQuerysetMixin, UpdateView):
    model = ServiceOrder
    form_class = ServiceOrderForm
    template_name = 'os_update.html'
    context_object_name = 'os'
    success_url = '/list_os/'

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if getattr(user, 'role', None) == 'TECHNICIAN':
            qs = qs.filter(user=user)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tenant'] = self.object.tenant
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

        if parts_useds.is_valid() and time_service.is_valid():
            self.object = form.save()

            parts_useds.instance = self.object
            parts_useds.save()

            time_service.instance = self.object
            time_service.save()

            return HttpResponseRedirect(self.get_success_url())
        else:
            return self.render_to_response(self.get_context_data(form=form))


@method_decorator(login_required(login_url='login'), name='dispatch')
class ScaleDeleteView(TenantRequiredMixin, TenantQuerysetMixin, DeleteView):
    model = Scale
    template_name = 'scale_delete.html'
    success_url = '/search_scale/'
    context_object_name = 'scale'

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        record_audit(
            tenant=self.object.tenant,
            actor=request.user,
            action=AuditLog.ACTION_DELETE,
            object_type='Scale',
            object_id=self.object.pk,
            request=request,
        )
        return super().delete(request, *args, **kwargs)


@method_decorator(login_required(login_url='login'), name='dispatch')
class ClientDeleteView(TenantRequiredMixin, TenantQuerysetMixin, DeleteView):
    model = Client
    template_name = 'client_delete.html'
    success_url = '/search_client/'
    context_object_name = 'client'

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        record_audit(
            tenant=self.object.tenant,
            actor=request.user,
            action=AuditLog.ACTION_DELETE,
            object_type='Client',
            object_id=self.object.pk,
            request=request,
        )
        return super().delete(request, *args, **kwargs)


@method_decorator(login_required(login_url='login'), name='dispatch')
class ServiceOrderDeleteView(AdminRequiredMixin, TenantRequiredMixin, TenantQuerysetMixin, View):
    def post(self, request, pk, *args, **kwargs):
        qs = self.get_queryset()
        if getattr(request.user, 'role', None) == 'TECHNICIAN':
            qs = qs.filter(user=request.user)
        service_order = get_object_or_404(qs, pk=pk)
        delete_service_order(service_order=service_order, tenant=service_order.tenant)
        record_audit(
            tenant=service_order.tenant,
            actor=request.user,
            action=AuditLog.ACTION_DELETE,
            object_type='ServiceOrder',
            object_id=pk,
            request=request,
        )
        messages.success(request, 'Ordem de Serviço excluída.')
        return redirect('list_os')

    def get_queryset(self):
        return ServiceOrder.objects.filter(tenant=getattr(self.request.user, 'tenant', None))


@method_decorator(login_required(login_url='login'), name='dispatch')
class StampListView(AdminRequiredMixin, TenantQuerysetMixin, ListView):
    model = Stamp
    template_name = 'stamp_list.html'
    context_object_name = 'stamps'

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .select_related('tenant')
            .prefetch_related('stam_util')
            .order_by('number')
        )


@method_decorator(login_required(login_url='login'), name='dispatch')
class StampCreateView(AdminRequiredMixin, TenantRequiredMixin, CreateView):
    model = Stamp
    form_class = StampCreateForm
    template_name = 'stamp_create.html'
    success_url = '/selos/'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.pop('instance', None)
        kwargs['tenant'] = getattr(self.request.user, 'tenant', None)
        return kwargs

    def form_valid(self, form):
        tenant = getattr(self.request.user, 'tenant', None)
        if tenant is None:
            form.add_error(None, 'Usuário sem tenant ativo.')
            return self.form_invalid(form)
        with transaction.atomic():
            stamps = [Stamp.objects.create(tenant=tenant, number=number) for number in form.cleaned_data['numbers_list']]
            for stamp in stamps:
                record_audit(
                    tenant=tenant,
                    actor=self.request.user,
                    action=AuditLog.ACTION_CREATE,
                    object_type='Stamp',
                    object_id=stamp.pk,
                    metadata={'number': stamp.number},
                    request=self.request,
                )
        messages.success(self.request, f'{len(stamps)} selo(s) cadastrado(s) com sucesso.')
        return redirect(self.success_url)


@method_decorator(login_required(login_url='login'), name='dispatch')
class StampDeliveryCreateView(AdminRequiredMixin, CreateView):
    model = StampDelivery
    form_class = StampDeliveryForm
    template_name = 'stamp_distribute.html'
    success_url = '/selos/'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['tenant'] = _tenant_of(self.request.user)
        return kwargs

    def form_valid(self, form):
        tenant = _tenant_of(self.request.user)
        if tenant is None and not self.request.user.is_superuser:
            form.add_error(None, 'Usuário sem tenant ativo.')
            return self.form_invalid(form)
        stamp = form.cleaned_data['number']
        user = form.cleaned_data['user']
        try:
            distribute_stamp(stamp=stamp, user=user, tenant=tenant or stamp.tenant)
        except Exception as exc:
            form.add_error(None, str(exc))
            return self.form_invalid(form)
        messages.success(self.request, f'Selo {stamp.number} distribuído.')
        record_audit(
            tenant=tenant or stamp.tenant,
            actor=self.request.user,
            action=AuditLog.ACTION_STAMP_DISTRIBUTE,
            object_type='Stamp',
            object_id=stamp.pk,
            metadata={'number': str(stamp.number)},
            request=self.request,
        )
        return HttpResponseRedirect('/selos/')


@method_decorator(login_required(login_url='login'), name='dispatch')
class StampBulkDeliveryView(AdminRequiredMixin, TenantRequiredMixin, View):
    template_name = 'stamp_bulk_distribute.html'

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, {
            'form': StampBulkDeliveryForm(tenant=_tenant_of(request.user)),
        })

    def post(self, request, *args, **kwargs):
        tenant = _tenant_of(request.user)
        form = StampBulkDeliveryForm(request.POST, tenant=tenant)
        if not form.is_valid():
            return render(request, self.template_name, {'form': form})

        stamps = list(form.cleaned_data['stamps'])
        technician = form.cleaned_data['user']
        try:
            with transaction.atomic():
                for stamp in stamps:
                    distribute_stamp(stamp=stamp, user=technician, tenant=tenant)
                    record_audit(
                        tenant=tenant,
                        actor=request.user,
                        action=AuditLog.ACTION_STAMP_DISTRIBUTE,
                        object_type='Stamp',
                        object_id=stamp.pk,
                        metadata={'number': stamp.number, 'bulk': True},
                        request=request,
                    )
        except Exception as exc:
            form.add_error(None, str(exc))
            return render(request, self.template_name, {'form': form})

        messages.success(
            request,
            f'{len(stamps)} selo(s) distribuído(s) para {technician.email}.',
        )
        return redirect('stamp_list')


@method_decorator(login_required(login_url='login'), name='dispatch')
class StampDamageView(AdminRequiredMixin, View):
    def post(self, request, pk):
        delivery = get_object_or_404(StampDelivery, pk=pk)
        tenant = _tenant_of(request.user)
        try:
            damage_delivery(delivery_id=delivery.pk, tenant=tenant or delivery.tenant)
            messages.success(request, 'Selo marcado como danificado.')
            record_audit(
                tenant=tenant or delivery.tenant,
                actor=request.user,
                action=AuditLog.ACTION_STAMP_DAMAGE,
                object_type='StampDelivery',
                object_id=delivery.pk,
                metadata={'number': delivery.number.number},
                request=request,
            )
        except Exception as exc:
            messages.error(request, str(exc))
        return HttpResponseRedirect('/selos/')


@method_decorator(login_required(login_url='login'), name='dispatch')
class HomeView(View):
    def get(self, request):
        return render(request, 'home.html')


SERVICE_STATUS_LABELS = dict(ServiceOrder.STATUS_CHOICES)
SERVICE_LABELS = [
    (f'service{i}', getattr(ServiceOrder._meta.get_field(f'service{i}'), 'verbose_name', ''))
    for i in range(1, 9)
]


def _scoped_service_orders(request):
    qs = ServiceOrder.objects.all()
    user = request.user
    if user.is_superuser:
        return qs
    tenant = getattr(user, 'tenant', None)
    if tenant is None:
        return ServiceOrder.objects.none()
    qs = qs.filter(tenant=tenant)
    if getattr(user, 'role', None) == 'TECHNICIAN':
        qs = qs.filter(user=user)
    return qs


def avg_total_hours(os_ids) -> float | None:
    total_minutes = 0
    count = 0
    for value in TimeService.objects.filter(service_order_id__in=os_ids).values_list(
        'total_hours', flat=True
    ):
        if value is not None:
            total_minutes += value.hour * 60 + value.minute
            count += 1
    if count == 0:
        return None
    return total_minutes / (count * 60)


@method_decorator(login_required(login_url='login'), name='dispatch')
class DashboardView(StaffRequiredMixin, TemplateView):
    """Indicadores operacionais do ciclo: O.S., status, técnico e tempo médio."""

    template_name = 'dashboard.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        tenant = getattr(self.request, 'tenant', None) or getattr(
            self.request.user, 'tenant', None
        )
        start, end = period_bounds(tenant)
        qs = ServiceOrder.objects.filter(tenant=tenant, date__gte=start, date__lte=end) if tenant else ServiceOrder.objects.none()

        by_use = list(
            qs.values('user__first_name', 'user__last_name', 'user__email', 'user_id')
            .annotate(count=Count('id'))
            .order_by('-count')
        )
        technicians = []
        for row in by_use:
            name = (
                f"{row['user__first_name'] or ''} {row['user__last_name'] or ''}".strip()
                or row['user__email']
            )
            technicians.append({'name': name, 'count': row['count']})

        os_by_status = [
            {'code': code, 'label': label, 'count': qs.filter(status=code).count()}
            for code, label in ServiceOrder.STATUS_CHOICES
        ]

        avg_hours = avg_total_hours(list(qs.values_list('id', flat=True)))

        ctx.update({
            'tenant': tenant,
            'period_start': start,
            'period_end': end,
            'os_total': qs.count(),
            'os_by_status': os_by_status,
            'technicians': technicians,
            'tempo_medio_horas': avg_hours,
            'tempo_medio_display': (
                f'{avg_hours:.1f}'.replace('.', ',') + 'h' if avg_hours is not None else '—'
            ),
        })
        return ctx


@method_decorator(login_required(login_url='login'), name='dispatch')
class ServiceOrderExportView(View):
    """Export CSV com escopo de tenant: ?tipo=os|pecas|tempos (Sprint 3.2)."""

    def get(self, request, *args, **kwargs):
        tipo = request.GET.get('tipo', 'os')
        if tipo not in ('os', 'pecas', 'tempos'):
            return HttpResponse('Tipo de exportação inválido.', status=400)

        qs = _scoped_service_orders(request).select_related(
            'client', 'scale', 'user', 'stamp'
        ).order_by('-date')

        buffer = io.StringIO()
        writer = csv.writer(buffer, delimiter=';')

        if tipo == 'os':
            writer.writerow([
                'ID', 'Número', 'Status', 'Cliente', 'Documento', 'Cidade',
                'Balança', 'Série', 'Técnico', 'Data', 'Serviços', 'Observações',
                'Selo aplicado', 'Selo retirado', 'Assinada',
                'INMETRO este ano', 'Instalação nova', 'Hospedagem', 'Alimentação',
            ])
            for os_obj in qs:
                checked = ' | '.join(
                    label for field, label in SERVICE_LABELS if getattr(os_obj, field)
                )
                writer.writerow([
                    os_obj.id,
                    os_obj.display_number,
                    SERVICE_STATUS_LABELS.get(os_obj.status, os_obj.status),
                    os_obj.client.name,
                    os_obj.client.document,
                    os_obj.client.city or '',
                    f'{os_obj.scale.brand} / {os_obj.scale.model}',
                    os_obj.scale.serie,
                    os_obj.user.email if os_obj.user else '',
                    os_obj.date.strftime('%d/%m/%Y %H:%M'),
                    checked,
                    os_obj.observation or '',
                    os_obj.stamp.number.number if os_obj.stamp else '',
                    os_obj.stamp_retired or '',
                    'Sim' if os_obj.signature else 'Não',
                    'Sim' if os_obj.verified else 'Não',
                    'Sim' if os_obj.new_instalation else 'Não',
                    'Sim' if os_obj.host else 'Não',
                    'Sim' if os_obj.food else 'Não',
                ])
        elif tipo == 'pecas':
            writer.writerow([
                'ID', 'ID da O.S.', 'Número', 'Cliente', 'Código', 'Quantidade',
                'Descrição', 'Série', 'Base de troca',
            ])
            for part in Part.objects.filter(service_order__in=qs).select_related(
                'service_order__client'
            ).order_by('service_order_id', 'id'):
                writer.writerow([
                    part.id,
                    part.service_order_id,
                    part.service_order.display_number,
                    part.service_order.client.name,
                    part.code if part.code is not None else '',
                    part.amount if part.amount is not None else '',
                    part.description or '',
                    part.serie or '',
                    'Sim' if part.base else 'Não',
                ])
        else:
            writer.writerow([
                'ID', 'ID da O.S.', 'Número', 'Cliente', 'Dia', 'Início',
                'Parada', 'Total de horas', 'Carro', 'Caminhão',
            ])
            for time_row in TimeService.objects.filter(service_order__in=qs).select_related(
                'service_order', 'service_order__client'
            ).order_by('service_order_id', 'id'):
                writer.writerow([
                    time_row.id,
                    time_row.service_order_id,
                    time_row.service_order.display_number,
                    time_row.service_order.client.name,
                    time_row.day.strftime('%d/%m/%Y') if time_row.day else '',
                    time_row.start.strftime('%H:%M') if time_row.start else '',
                    time_row.stop.strftime('%H:%M') if time_row.stop else '',
                    time_row.total_hours.strftime('%H:%M') if time_row.total_hours else '',
                    time_row.car or '',
                    time_row.truck or '',
                ])

        filename = {
            'os': 'ordens-de-servico.csv',
            'pecas': 'pecas.csv',
            'tempos': 'tempos.csv',
        }[tipo]
        response = HttpResponse(
            '﻿' + buffer.getvalue(), content_type='text/csv; charset=utf-8'
        )
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        tenant = getattr(request, 'tenant', None) or getattr(request.user, 'tenant', None)
        record_audit(
            tenant=tenant,
            actor=request.user,
            action=AuditLog.ACTION_EXPORT,
            object_type='ServiceOrder',
            metadata={'format': 'csv', 'type': tipo},
            request=request,
        )
        return response
