from django.urls import path

from .views import SignUpView, home_page_view, AboutPageView

urlpatterns = [
    path("", home_page_view, name="home"),
    path("about/", AboutPageView.as_view(), name="about"),
    path("signup/", SignUpView.as_view(), name="signup"),
]