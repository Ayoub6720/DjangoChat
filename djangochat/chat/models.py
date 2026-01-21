from django.conf import settings
from django.db import models

User = settings.AUTH_USER_MODEL


class Room(models.Model):
    name = models.CharField(max_length=80, unique=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="rooms_created")
    created_at = models.DateTimeField(auto_now_add=True)
    password = models.CharField(max_length=128, blank=True, default="")

    def __str__(self) -> str:
        return self.name


class Membership(models.Model):
    OWNER = "OWNER"
    MOD = "MOD"
    MEMBER = "MEMBER"
    BANNED = "BANNED"

    ROLE_CHOICES = [
        (OWNER, "Owner"),
        (MOD, "Moderator"),
        (MEMBER, "Member"),
        (BANNED, "Banned"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="memberships")
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default=MEMBER)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "room")

    def __str__(self) -> str:
        return f"{self.user} in {self.room} ({self.role})"


class Message(models.Model):
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name="messages")
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name="messages")
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    edited_at = models.DateTimeField(null=True, blank=True)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        ordering = ["id"]

    def __str__(self) -> str:
        return f"#{self.id} {self.author}: {self.content[:30]}"

