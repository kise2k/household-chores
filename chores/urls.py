from django.urls import path

from . import views

app_name = "chores"

urlpatterns = [
    path("", views.chore_list, name="chore_list"),
    path("chores/new/", views.chore_create, name="chore_create"),
    path(
        "chores/<int:pk>/complete/",
        views.chore_complete,
        name="chore_complete",
    ),
    path("members/", views.member_list, name="member_list"),
    path(
        "members/<int:pk>/delete/",
        views.member_delete,
        name="member_delete",
    ),
]
