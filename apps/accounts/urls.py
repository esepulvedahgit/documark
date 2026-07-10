from django.urls import path

from apps.accounts import views

app_name = "accounts"

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("admin/users/", views.user_list, name="user_list"),
    path("admin/users/create/", views.user_create, name="user_create"),
    path("admin/users/<str:user_id>/edit/", views.user_edit, name="user_edit"),
]
