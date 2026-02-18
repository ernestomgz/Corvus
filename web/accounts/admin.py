from django.contrib import admin
from .models import User

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('id', 'email', 'created_at', 'is_active', 'is_staff')
    search_fields = ('email',)
    ordering = ('-created_at',)
