from django.contrib import admin
from django.urls import path
from . import views

urlpatterns = [
    path('django-admin/', admin.site.urls),
    path('', views.home, name='home'),
    path('services/', views.services, name='services'),
    path('doctors/', views.doctors, name='doctors'),
    path('contacts/', views.contacts, name='contacts'),
    path('login/', views.login_view, name='login'),
    path('register/', views.register, name='register'),
    path('logout/', views.logout_view, name='logout'),
    path('pets/', views.pets, name='pets'),
    path('pets/<int:pk>/', views.pet_detail, name='pet_detail'),
    path('pets/<int:pk>/delete/', views.delete_pet, name='delete_pet'),
    path('vaccinations/', views.vaccinations, name='vaccinations'),
    path('reminders/', views.reminders, name='reminders'),
    path('history/', views.history, name='history'),
    path('appointments/new/', views.book, name='book'),
    path('appointments/<int:pk>/', views.appointment_detail, name='appointment_detail'),
    path('doctor/', views.doctor_page, name='doctor'),
    path('doctor/<int:pk>/', views.doctor_page, name='doctor_appointment'),
    path('clinic/', views.clinic, name='clinic'),
]
