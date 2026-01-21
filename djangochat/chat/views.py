from django.contrib import messages as dj_messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseForbidden
from django.db.models import OuterRef, Subquery, Value, DateTimeField, Case, When, IntegerField
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from django.contrib.auth import logout
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.core.cache import cache
import time


from .forms import SignupForm, RoomCreateForm, CustomAuthenticationForm
from .models import Room, Message, Membership


def _get_role(user, room: Room) -> str:
    m = Membership.objects.filter(user=user, room=room).first()
    return m.role if m else ""


def _ensure_membership(user, room: Room) -> Membership:
    """
    - si l'utilisateur n'a pas de membership: on l'ajoute MEMBER
    - si il est BANNED: on refuse l'accès ailleurs
    """
    m, created = Membership.objects.get_or_create(user=user, room=room, defaults={"role": Membership.MEMBER})
    if created:
        Message.objects.create(
            room=room,
            author=user,
            content=f"[SYSTEM] {user.username} a rejoint le salon.",
        )
    return m


def signup(request):
    if request.user.is_authenticated:
        return redirect("room_list")

    if request.method == "POST":
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("room_list")
    else:
        form = SignupForm()

    return render(request, "registration/signup.html", {"form": form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect("room_list")

    form = CustomAuthenticationForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        login(request, form.get_user())
        return redirect("room_list")

    return render(request, "registration/login.html", {"form": form})


@login_required
def room_list(request):
    last_msg_qs = Message.objects.filter(room=OuterRef("pk")).order_by("-id")
    last_created_at = Subquery(last_msg_qs.values("created_at")[:1])
    epoch = timezone.datetime(1970, 1, 1, tzinfo=timezone.UTC)
    rooms = (
        Room.objects.all()
        .annotate(
            last_message_content=Subquery(last_msg_qs.values("content")[:1]),
            last_message_author=Subquery(last_msg_qs.values("author__username")[:1]),
            last_message_is_deleted=Subquery(last_msg_qs.values("is_deleted")[:1]),
            last_message_created_at=last_created_at,
            last_message_created_at_sort=Coalesce(
                last_created_at, Value(epoch, output_field=DateTimeField())
            ),
        )
        .order_by("-last_message_created_at_sort", "name")
    )
    return render(request, "chat/room_list.html", {"rooms": rooms})


@login_required
def room_create(request):
    if request.method == "POST":
        form = RoomCreateForm(request.POST)
        if form.is_valid():
            room = form.save(commit=False)
            room.created_by = request.user
            room.save()
            Membership.objects.create(user=request.user, room=room, role=Membership.OWNER)
            return redirect("room_detail", room_id=room.id)
    else:
        form = RoomCreateForm()

    return render(request, "chat/room_create.html", {"form": form})


@login_required
def room_detail(request, room_id: int):
    room = get_object_or_404(Room, id=room_id)
    membership = Membership.objects.filter(user=request.user, room=room).first()
    if membership and membership.role == Membership.BANNED:
        return render(request, "chat/banned.html", {"room": room}, status=403)

    if not membership:
        if room.password:
            if request.method == "POST":
                provided = (request.POST.get("room_password") or "").strip()
                if provided == room.password:
                    membership = _ensure_membership(request.user, room)
                else:
                    return render(
                        request,
                        "chat/room_password.html",
                        {"room": room, "error": True},
                        status=403,
                    )
            else:
                return render(
                    request,
                    "chat/room_password.html",
                    {"room": room, "error": False},
                    status=403,
                )
        else:
            membership = _ensure_membership(request.user, room)

    # On affiche les 50 derniers messages au chargement
    msgs = (
        Message.objects.filter(room=room)
        .select_related("author")
        .order_by("-id")[:50]
    )
    msgs = list(reversed(msgs))

    role = membership.role
    members = (
        Membership.objects.filter(room=room)
        .select_related("user")
        .annotate(
            role_order=Case(
                When(role=Membership.OWNER, then=Value(0)),
                When(role=Membership.MOD, then=Value(1)),
                When(role=Membership.MEMBER, then=Value(2)),
                When(role=Membership.BANNED, then=Value(3)),
                default=Value(9),
                output_field=IntegerField(),
            )
        )
        .order_by("role_order", "user__username")
    )
    return render(
        request,
        "chat/room_detail.html",
        {
            "room": room,
            "chat_messages": msgs,
            "role": role,
            "memberships": members,
        },
    )


@require_POST
@login_required
def room_delete(request, room_id: int):
    room = get_object_or_404(Room, id=room_id)
    membership = _ensure_membership(request.user, room)
    if membership.role != Membership.OWNER:
        return HttpResponseForbidden("Seul le owner peut supprimer ce salon.")

    room.delete()
    dj_messages.error(request, "Salon supprimé.")
    return redirect("room_list")


@require_POST
@login_required
def room_rename(request, room_id: int):
    room = get_object_or_404(Room, id=room_id)
    membership = _ensure_membership(request.user, room)
    if membership.role != Membership.OWNER:
        return HttpResponseForbidden("Seul le owner peut renommer ce salon.")

    new_name = (request.POST.get("name") or "").strip()
    if not new_name:
        dj_messages.error(request, "Le nom du salon ne peut pas être vide.")
        return redirect("room_detail", room_id=room.id)

    if len(new_name) > 80:
        dj_messages.error(request, "Le nom du salon est trop long.")
        return redirect("room_detail", room_id=room.id)

    if Room.objects.exclude(id=room.id).filter(name__iexact=new_name).exists():
        dj_messages.error(request, "Ce nom de salon existe déjà.")
        return redirect("room_detail", room_id=room.id)

    room.name = new_name
    room.save(update_fields=["name"])
    dj_messages.success(request, "Salon renommé.")
    return redirect("room_detail", room_id=room.id)


@require_GET
@login_required
def api_messages(request, room_id: int):
    room = get_object_or_404(Room, id=room_id)
    membership = _ensure_membership(request.user, room)
    if membership.role == Membership.BANNED:
        return JsonResponse({"error": "banned"}, status=403)

    after = request.GET.get("after", "")
    since = request.GET.get("since", "")
    try:
        after_id = int(after) if after else 0
    except ValueError:
        after_id = 0
    since_dt = parse_datetime(since) if since else None
    if since_dt and timezone.is_naive(since_dt):
        since_dt = timezone.make_aware(since_dt, timezone.get_current_timezone())

    qs = (
        Message.objects.filter(room=room, id__gt=after_id)
        .select_related("author")
        .order_by("id")[:200]
    )

    data = []
    for m in qs:
        data.append(
            {
                "id": m.id,
                "author": m.author.username,
                "content": "[message supprimé]" if m.is_deleted else m.content,
                "created_at": m.created_at.isoformat(),
                "is_deleted": m.is_deleted,
                "can_delete": (membership.role in (Membership.OWNER, Membership.MOD)) or (m.author_id == request.user.id),
            }
        )

    deleted_ids = []
    if since_dt:
        deleted_ids = list(
            Message.objects.filter(room=room, is_deleted=True, edited_at__gt=since_dt)
            .values_list("id", flat=True)
        )

    return JsonResponse({"messages": data, "deleted_ids": deleted_ids, "server_now": timezone.now().isoformat()})


@require_POST
@login_required
def api_send_message(request, room_id: int):
    room = get_object_or_404(Room, id=room_id)
    membership = _ensure_membership(request.user, room)
    if membership.role == Membership.BANNED:
        return JsonResponse({"error": "banned"}, status=403)

    content = (request.POST.get("content") or "").strip()
    if not content:
        return JsonResponse({"error": "empty"}, status=400)
    if len(content) > 2000:
        return JsonResponse({"error": "too_long"}, status=400)

    msg = Message.objects.create(room=room, author=request.user, content=content)
    return JsonResponse(
        {
            "ok": True,
            "message": {
                "id": msg.id,
                "author": msg.author.username,
                "content": msg.content,
                "created_at": msg.created_at.isoformat(),
                "is_deleted": msg.is_deleted,
                "can_delete": True,
            },
        }
    )


@require_POST
@login_required
def api_delete_message(request, room_id: int, message_id: int):
    room = get_object_or_404(Room, id=room_id)
    membership = _ensure_membership(request.user, room)
    if membership.role == Membership.BANNED:
        return JsonResponse({"error": "banned"}, status=403)

    msg = get_object_or_404(Message, id=message_id, room=room)

    is_mod = membership.role in (Membership.OWNER, Membership.MOD)
    is_author = msg.author_id == request.user.id
    if not (is_mod or is_author):
        return JsonResponse({"error": "forbidden"}, status=403)

    msg.is_deleted = True
    msg.edited_at = timezone.now()
    msg.save(update_fields=["is_deleted", "edited_at"])
    return JsonResponse({"ok": True})


@require_POST
@login_required
def ban_user(request, room_id: int, user_id: int):
    room = get_object_or_404(Room, id=room_id)
    actor = _ensure_membership(request.user, room)
    if actor.role not in (Membership.OWNER, Membership.MOD):
        return JsonResponse({"error": "forbidden"}, status=403)

    target = get_object_or_404(Membership, room=room, user_id=user_id)
    if target.role == Membership.OWNER:
        return JsonResponse({"error": "cannot_ban_owner"}, status=400)

    target.role = Membership.BANNED
    target.save(update_fields=["role"])
    Message.objects.create(
        room=room,
        author=actor.user,
        content=f"[SYSTEM] {target.user.username} a été banni du salon.",
    )
    return redirect("room_detail", room_id=room.id)


@require_POST
@login_required
def unban_user(request, room_id: int, user_id: int):
    room = get_object_or_404(Room, id=room_id)
    actor = _ensure_membership(request.user, room)
    if actor.role not in (Membership.OWNER, Membership.MOD):
        return JsonResponse({"error": "forbidden"}, status=403)

    target = get_object_or_404(Membership, room=room, user_id=user_id)
    if target.role != Membership.BANNED:
        return JsonResponse({"error": "not_banned"}, status=400)

    target.role = Membership.MEMBER
    target.save(update_fields=["role"])
    Message.objects.create(
        room=room,
        author=actor.user,
        content=f"[SYSTEM] {target.user.username} a été débanni du salon.",
    )
    return redirect("room_detail", room_id=room.id)


@require_POST
@login_required
def set_moderator(request, room_id: int, user_id: int):
    room = get_object_or_404(Room, id=room_id)
    actor = _ensure_membership(request.user, room)
    if actor.role != Membership.OWNER:
        return JsonResponse({"error": "forbidden"}, status=403)

    target = get_object_or_404(Membership, room=room, user_id=user_id)
    if target.role == Membership.OWNER:
        return JsonResponse({"error": "cannot_change_owner"}, status=400)

    target.role = Membership.MOD
    target.save(update_fields=["role"])
    Message.objects.create(
        room=room,
        author=actor.user,
        content=f"[SYSTEM] {target.user.username} est maintenant modérateur.",
    )
    return redirect("room_detail", room_id=room.id)


@require_POST
@login_required
def unset_moderator(request, room_id: int, user_id: int):
    room = get_object_or_404(Room, id=room_id)
    actor = _ensure_membership(request.user, room)
    if actor.role != Membership.OWNER:
        return JsonResponse({"error": "forbidden"}, status=403)

    target = get_object_or_404(Membership, room=room, user_id=user_id)
    if target.role != Membership.MOD:
        return JsonResponse({"error": "not_mod"}, status=400)

    target.role = Membership.MEMBER
    target.save(update_fields=["role"])
    Message.objects.create(
        room=room,
        author=actor.user,
        content=f"[SYSTEM] {target.user.username} n'est plus modérateur.",
    )
    return redirect("room_detail", room_id=room.id)


@require_POST
def custom_logout(request):
    logout(request)
    return redirect("login")


@require_GET
@login_required
def api_room_list(request):
    last_msg_qs = Message.objects.filter(room=OuterRef("pk")).order_by("-id")
    last_created_at = Subquery(last_msg_qs.values("created_at")[:1])
    epoch = timezone.datetime(1970, 1, 1, tzinfo=timezone.UTC)
    rooms = (
        Room.objects.all()
        .annotate(
            last_message_content=Subquery(last_msg_qs.values("content")[:1]),
            last_message_author=Subquery(last_msg_qs.values("author__username")[:1]),
            last_message_is_deleted=Subquery(last_msg_qs.values("is_deleted")[:1]),
            last_message_created_at=last_created_at,
            last_message_created_at_sort=Coalesce(
                last_created_at, Value(epoch, output_field=DateTimeField())
            ),
        )
        .order_by("-last_message_created_at_sort", "name")
    )

    data = []
    for r in rooms:
        data.append(
            {
                "id": r.id,
                "name": r.name,
                "has_password": bool(r.password),
                "created_by": r.created_by.username,
                "last_message_content": r.last_message_content,
                "last_message_author": r.last_message_author,
                "last_message_is_deleted": r.last_message_is_deleted,
                "last_message_created_at": r.last_message_created_at.isoformat()
                if r.last_message_created_at
                else None,
            }
        )

    return JsonResponse({"rooms": data})


@require_GET
@login_required
def api_room_state(request, room_id: int):
    room = get_object_or_404(Room, id=room_id)
    membership = Membership.objects.filter(user=request.user, room=room).first()
    if membership and membership.role == Membership.BANNED:
        return JsonResponse({"error": "banned"}, status=403)
    if not membership:
        return JsonResponse({"error": "forbidden"}, status=403)

    members = list(
        Membership.objects.filter(room=room)
        .select_related("user")
        .values("user_id", "user__username", "role")
    )

    data = {
        "room": {"id": room.id, "name": room.name},
        "role": membership.role,
        "members": [
            {"user_id": m["user_id"], "username": m["user__username"], "role": m["role"]}
            for m in members
        ],
    }
    return JsonResponse(data)


@require_http_methods(["GET", "POST"])
@login_required
def api_typing(request, room_id: int):
    room = get_object_or_404(Room, id=room_id)
    membership = Membership.objects.filter(user=request.user, room=room).first()
    if not membership or membership.role == Membership.BANNED:
        return JsonResponse({"error": "forbidden"}, status=403)

    user = request.user.username
    now = time.time()
    key = f"typing_{room_id}"
    room_dict = cache.get(key, {})

    if request.method == "POST":
        room_dict[user] = now
        cache.set(key, room_dict, timeout=5)
        return JsonResponse({"ok": True})

    active_users = [u for u, t in room_dict.items() if now - t <= 1.5 and u != user]
    cache.set(key, {u: t for u, t in room_dict.items() if now - t <= 1.5}, timeout=5)
    return JsonResponse({"typing": active_users})
