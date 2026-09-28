from django.conf import settings


class ContentSecurityPolicyMiddleware:
    """CSP gradual: ativado explicitamente após validar os assets do ambiente."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if getattr(settings, 'ENABLE_CSP', False):
            response['Content-Security-Policy'] = (
                "default-src 'self'; "
                "base-uri 'self'; form-action 'self'; frame-ancestors 'self'; "
                "img-src 'self' data:; style-src 'self' 'unsafe-inline' https:; "
                "script-src 'self' 'unsafe-inline' https:; connect-src 'self' https:"
            )
        return response
