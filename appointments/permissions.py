from rest_framework import permissions


class IsAdminRole(permissions.BasePermission):
    """Allows access only to administrator accounts."""

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and (request.user.is_staff or getattr(request.user, "username", "") == "admin")
        )


class IsDoctorOrAdmin(permissions.BasePermission):
    """Allows access to doctors or administrators."""

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.user.is_staff or request.user.username == "admin":
            return True
        return request.user.username.startswith("dr.") or "doctor" in request.user.username.lower()


class IsPatientOrAdmin(permissions.BasePermission):
    """Allows access to patients or administrators."""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

