from django.db import models
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login
from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import HttpResponse

from .forms import CustomUserCreationForm
from courses.models import Course
from quizzes.models import QuizAttempt, Quiz
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import ttfonts
from collections import Counter


@login_required
def export_student_report_pdf(request):
    if not request.user.is_student():
        messages.warning(request, "Функція доступна лише студентам.")
        return redirect('users:cabinet')

    # Дані для звіту
    attempts = QuizAttempt.objects.filter(student=request.user).select_related(
        'quiz', 'quiz__lesson', 'quiz__lesson__course'
    ).order_by('quiz__lesson__course__title', 'completed_at')

    # Один раз перед створенням PDF
    pdfmetrics.registerFont(TTFont('DejaVu', 'static/fonts/DejaVuSans.ttf'))

    # PDF відповідь
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="звіт_{request.user.username}.pdf"'

    p = canvas.Canvas(response, pagesize=A4)
    width, height = A4

    y = height - 50
    p.setFont("DejaVu", 16)
    p.drawString(50, y, f"Звіт про проходження тестів – {request.user.username}")
    y -= 30

    p.setFont("DejaVu", 10)
    headers = ["Курс", "Урок", "Тест", "Результат", "Дата"]
    col_widths = [140, 100, 100, 60, 80]
    x_start = 50

    # Заголовки таблиці
    for i, header in enumerate(headers):
        p.drawString(x_start + sum(col_widths[:i]), y, header)
    y -= 20

    # Дані таблиці
    for attempt in attempts:
        data = [
            attempt.quiz.lesson.course.title[:30],
            attempt.quiz.lesson.title[:25],
            attempt.quiz.title[:25],
            f"{attempt.score}%",
            attempt.completed_at.strftime("%Y-%m-%d")
        ]
        for i, cell in enumerate(data):
            p.drawString(x_start + sum(col_widths[:i]), y, str(cell))
        y -= 18
        if y < 60:
            p.showPage()
            y = height - 50

    p.showPage()
    p.save()
    return response


@login_required
def cabinet_view(request):
    user = request.user

    if user.is_teacher():
        courses = Course.objects.filter(teacher=user)
        quiz_attempts = None
        stats = None
        recommendations = None
        detailed_recommendations = None
    else:
        courses = user.enrolled_courses.all()
        quiz_attempts = QuizAttempt.objects.filter(student=user).select_related(
            'quiz', 'quiz__lesson', 'quiz__lesson__course'
        ).prefetch_related('incorrect_questions')

        total_quizzes = Quiz.objects.filter(lesson__course__in=courses).count()
        completed_quizzes = quiz_attempts.count()
        average_score = round(quiz_attempts.aggregate(avg=models.Avg('score'))['avg'] or 0, 2)

        # Статистика по помилках
        topic_counter = Counter()
        detailed_recommendations = {}

        for attempt in quiz_attempts:
            for question in attempt.incorrect_questions.all():
                lesson = question.quiz.lesson
                key = (lesson.id, lesson.title, lesson.course.id, lesson.course.title)

                topic_counter[lesson] += 1

                if key not in detailed_recommendations:
                    detailed_recommendations[key] = []
                detailed_recommendations[key].append(question.text)

        recommendations = sorted(topic_counter.items(), key=lambda x: x[1], reverse=True)[:5]

        stats = {
            'completed': completed_quizzes,
            'total': total_quizzes,
            'success': average_score
        }

    return render(request, 'users/cabinet.html', {
        'courses': courses,
        'quiz_attempts': quiz_attempts,
        'stats': stats,
        'recommendations': recommendations,
        'detailed_recommendations': detailed_recommendations,
    })


def home_view(request):
    return render(request, 'users/home.html')


def register_view(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f'Ласкаво просимо, {user.username}! Ви успішно зареєструвались.')
            return redirect('users:cabinet')
        else:
            messages.error(request, 'Форма заповнена некоректно. Будь ласка, перевірте введені дані.')
    else:
        form = CustomUserCreationForm()
    return render(request, 'users/register.html', {'form': form})
