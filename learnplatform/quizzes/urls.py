from django.urls import path
from .views import create_quiz_view, edit_quiz_view, edit_answers_view, take_quiz_view, request_retake_view, \
    approve_retake_view

app_name = 'quizzes'

urlpatterns = [
    path('lesson/<int:lesson_id>/create/', create_quiz_view, name='create'),
    path('lesson/<int:lesson_id>/edit/', edit_quiz_view, name='edit'),
    path('question/<int:question_id>/answers/', edit_answers_view, name='edit_answers'),
    path('lesson/<int:lesson_id>/take/', take_quiz_view, name='take'),
    path('lesson/<int:lesson_id>/retake/', request_retake_view, name='request_retake'),
    path('retake/<int:request_id>/approve/', approve_retake_view, name='approve_retake'),
]
