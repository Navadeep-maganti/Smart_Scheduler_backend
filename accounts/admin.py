from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import AppUser, Faculty, Student


@admin.register(AppUser)
class AppUserAdmin(UserAdmin):
    ordering = ("email",)
    list_display = ("email", "role", "is_active", "is_staff", "is_superuser")
    search_fields = ("email",)
    readonly_fields = ("last_login", "created_at", "updated_at")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Access", {"fields": ("role", "is_active", "is_staff", "is_superuser")}),
        ("Permissions", {"fields": ("groups", "user_permissions")}),
        ("Important dates", {"fields": ("last_login", "created_at", "updated_at")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "role", "password1", "password2", "is_active", "is_staff"),
            },
        ),
    )


admin.site.register([Faculty, Student])
