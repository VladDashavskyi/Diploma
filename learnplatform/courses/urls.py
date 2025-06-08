from django.urls import path
from .views import create_course_view, create_lesson_view, course_detail_view, lesson_detail_view, enroll_view, \
    available_courses_view, export_grades_excel

app_name = 'courses'

urlpatterns = [
    path('create/', create_course_view, name='create'),
    path('create/', create_course_view, name='create'),
    path('<int:course_id>/add-lesson/', create_lesson_view, name='add_lesson'),
    path('<int:course_id>/', course_detail_view, name='detail'),
    path('<int:course_id>/lesson/<int:lesson_id>/', lesson_detail_view, name='lesson_detail'),
    path('<int:course_id>/enroll/', enroll_view, name='enroll'),
    path('available/', available_courses_view, name='available'),
    path('<int:course_id>/export/', export_grades_excel, name='export_excel'),

]
