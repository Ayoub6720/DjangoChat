from django.contrib import admin
from .models import Room, Membership, Message


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "created_by", "created_at")
    search_fields = ("name",)


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("id", "room", "user", "role", "joined_at")
    list_filter = ("role", "room")


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("id", "room", "author", "created_at", "is_deleted")
    list_filter = ("room", "is_deleted")
    search_fields = ("content",)
