from django.contrib.auth.models import User
from rest_framework import permissions


class IsOwnerOrAdmin(permissions.BasePermission):
    """
    Custom permission to only allow owners of an object to edit it.
    """

    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed to any request,
        # so we'll always allow GET, HEAD or OPTIONS requests.
        try:
            if request.method in permissions.SAFE_METHODS: # if object belongs to user or admin
                return obj.user_id == request.user.username or User.objects.get(username=request.user).is_staff
        except User.DoesNotExist:
            return False

        # Write permissions are only allowed to the owner of the snippet.
        return False
    
class IsAdminOrUser(permissions.BasePermission):
    """
    Custom permission to distinguish admin and user
    """
    def has_permission(self, request, view):
        # Read permissions are allowed to any request,
        # so we'll always allow GET, HEAD or OPTIONS requests.
        try:
            if request.method in permissions.SAFE_METHODS:
                return User.objects.get(username=request.user)
        except User.DoesNotExist:
            return False

        # Write permissions are only allowed to admin 
        return User.objects.get(username=request.user).is_staff