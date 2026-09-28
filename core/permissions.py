from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied
from functools import wraps

ROLE_TECHNICIAN = 'TECHNICIAN'
ROLE_STAFF = 'STAFF'
ROLE_ADMIN = 'ADMIN'
ALL_ROLES = (ROLE_TECHNICIAN, ROLE_STAFF, ROLE_ADMIN)
STAFF_ROLES = (ROLE_STAFF, ROLE_ADMIN)
ADMIN_ROLES = (ROLE_ADMIN,)


class TenantRequiredMixin(LoginRequiredMixin):
    """Exige usuário autenticado com tenant ativo (ou superuser interno)."""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not request.user.is_superuser and getattr(request.user, 'tenant_id', None) is None:
            raise PermissionDenied('Usuário sem tenant ativo.')
        return super().dispatch(request, *args, **kwargs)


class RoleRequiredMixin(UserPassesTestMixin):
    """RBAC: user.role deve estar em `roles` (superuser sempre passa)."""

    roles: tuple = ALL_ROLES

    def test_func(self):
        user = self.request.user
        if not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        return getattr(user, 'role', None) in self.roles


class StaffRequiredMixin(RoleRequiredMixin):
    roles = STAFF_ROLES


class AdminRequiredMixin(RoleRequiredMixin):
    roles = ADMIN_ROLES


def admin_required(view_func):
    """Versão função de AdminRequiredMixin: exige role ADMIN (superuser passa)."""

    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        user = request.user
        if not user.is_authenticated:
            raise PermissionDenied('Autenticação necessária.')
        if user.is_superuser or getattr(user, 'role', None) == ADMIN_ROLES[0]:
            return view_func(request, *args, **kwargs)
        raise PermissionDenied('Acesso restrito ao administrador do tenant.')

    from django.contrib.auth.decorators import login_required

    return login_required(login_url='login')(_wrapped)
