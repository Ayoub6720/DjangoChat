from django.urls import path
from . import views

urlpatterns = [
    path("", views.room_list, name="room_list"),
    path("signup/", views.signup, name="signup"),
    path("login/", views.login_view, name="login"),
    path("rooms/create/", views.room_create, name="room_create"),
    path("rooms/<int:room_id>/", views.room_detail, name="room_detail"),
    path("rooms/<int:room_id>/delete/", views.room_delete, name="room_delete"),
    path("rooms/<int:room_id>/rename/", views.room_rename, name="room_rename"),
    path("logout/", views.custom_logout, name="custom_logout"),

    # API JSON (AJAX)
    path("api/rooms/", views.api_room_list, name="api_room_list"),
    path("api/rooms/<int:room_id>/state/", views.api_room_state, name="api_room_state"),
    path("api/rooms/<int:room_id>/messages/", views.api_messages, name="api_messages"),
    path("api/rooms/<int:room_id>/send/", views.api_send_message, name="api_send_message"),
    path("api/rooms/<int:room_id>/typing/", views.api_typing, name="api_typing"),

    # modération basique (option)
    path("api/rooms/<int:room_id>/delete/<int:message_id>/", views.api_delete_message, name="api_delete_message"),
    path("api/rooms/<int:room_id>/ban/<int:user_id>/", views.ban_user, name="ban_user"),
    path("api/rooms/<int:room_id>/unban/<int:user_id>/", views.unban_user, name="unban_user"),
    path("api/rooms/<int:room_id>/mod/<int:user_id>/", views.set_moderator, name="set_moderator"),
    path("api/rooms/<int:room_id>/unmod/<int:user_id>/", views.unset_moderator, name="unset_moderator"),
]

