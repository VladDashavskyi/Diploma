from django.urls import path
from .views import cabinet_view, home_view, register_view, export_student_report_pdf

app_name = 'users'

urlpatterns = [
    path('', home_view, name='home'),
    path('cabinet/', cabinet_view, name='cabinet'),
    path('register/', register_view, name='register'),
    path('report/pdf/', export_student_report_pdf, name='student_report_pdf'),

]
