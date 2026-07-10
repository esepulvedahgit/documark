from django.urls import path

from apps.converter import views

app_name = "converter"

urlpatterns = [
    path("", views.index, name="index"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("convert/", views.convert_view, name="convert"),
    path("convert/status/<str:conversion_id>/", views.convert_status_view, name="convert_status"),
    path("preview/<str:conversion_id>/", views.preview_view, name="preview"),
    path("download/<str:conversion_id>/", views.download_view, name="download"),
    path("history/", views.history_view, name="history"),
    path("admin/history/", views.admin_history_view, name="admin_history"),
]
