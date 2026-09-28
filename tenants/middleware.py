from core.models import reset_current_tenant, set_current_tenant


class TenantMiddleware:
    """Resolve request.tenant a partir de request.user.tenant após auth."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.tenant = None
        token = None

        user = getattr(request, 'user', None)
        if user is not None and user.is_authenticated:
            tenant = getattr(user, 'tenant', None)
            request.tenant = tenant
            token = set_current_tenant(tenant)

        try:
            return self.get_response(request)
        finally:
            if token is not None:
                reset_current_tenant(token)
