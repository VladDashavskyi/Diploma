from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.db.models import Q
from django.http import HttpResponse

from .forms import CourseForm, LessonForm
from .models import Course, Lesson
from quizzes.models import QuizAttempt, RetakeRequest
import openpyxl


@login_required
def export_grades_excel(request, course_id):
    course = get_object_or_404(Course, id=course_id)

    if not request.user.is_teacher() or course.teacher != request.user:
        messages.warning(request, "Доступ заборонено.")
        return redirect('users:cabinet')

    lessons = course.lessons.order_by('order')
    quizzes = {lesson.id: lesson.quiz for lesson in lessons if hasattr(lesson, 'quiz')}
    students = course.students.all()

    # Створення Excel-файлу
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f"{course.title[:25]}"

    # Заголовки
    headers = ['Студент']
    headers += [lesson.title for lesson in lessons if lesson.quiz]
    ws.append(headers)

    # Дані по студентах
    for student in students:
        row = [student.username]
        for lesson_id in quizzes:
            quiz = quizzes[lesson_id]
            attempt = QuizAttempt.objects.filter(student=student, quiz=quiz).first()
            score = f"{attempt.score}%" if attempt else "—"
            row.append(score)
        ws.append(row)

    # Відправка як файл
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{course.title}_успішність.xlsx"'
    wb.save(response)
    return response


@login_required
def available_courses_view(request):
    if not request.user.is_student():
        messages.warning(request, "Доступ заборонено.")
        return redirect('users:cabinet')

    courses = Course.objects.exclude(students=request.user)

    return render(request, 'courses/available_courses.html', {
        'courses': courses
    })


@login_required
@require_POST
def enroll_view(request, course_id):
    course = get_object_or_404(Course, id=course_id)

    if request.user.is_student():
        course.students.add(request.user)
        messages.success(request, f'Ви успішно записалися на курс "{course.title}".')
    else:
        messages.error(request, "Лише студенти можуть записуватися на курси.")

    return redirect('courses:detail', course_id=course.id)


@login_required
def lesson_detail_view(request, course_id, lesson_id):
    course = get_object_or_404(Course, id=course_id)
    lesson = get_object_or_404(course.lessons, id=lesson_id)

    if request.user.is_teacher():
        if course.teacher != request.user:
            messages.warning(request, "У вас немає доступу до цього уроку.")
            return redirect('users:cabinet')
    else:
        if request.user not in course.students.all():
            messages.warning(request, "Ви не записані на цей курс.")
            return redirect('users:cabinet')

    retake = None
    if request.user.is_student():
        try:
            retake = RetakeRequest.objects.get(student=request.user, quiz=lesson.quiz)
        except RetakeRequest.DoesNotExist:
            pass

    return render(request, 'courses/lesson_detail.html', {
        'course': course,
        'lesson': lesson,
        'request_already_sent': retake and not retake.approved,
    })


@login_required
def course_detail_view(request, course_id):
    course = get_object_or_404(Course, id=course_id)

    # 🔐 Перевірка доступу
    if request.user.is_teacher():
        if course.teacher != request.user:
            messages.warning(request, "У вас немає доступу до цього курсу.")
            return redirect('users:cabinet')
    else:
        if request.user not in course.students.all():
            messages.warning(request, "Ви не записані на цей курс.")
            return redirect('users:cabinet')

    lessons = course.lessons.order_by('order')

    # За замовчуванням для всіх користувачів
    gradebook = []
    quiz_lessons = [lesson for lesson in lessons if getattr(lesson, 'quiz', None)]

    # Формування даних для викладача
    if request.user.is_teacher():
        # Запити на повторну спробу (непідтверджені)
        retake_requests = RetakeRequest.objects.filter(
            quiz__lesson__in=lessons,
            approved=False
        ).select_related('quiz', 'student')
        retake_map = {
            f"{req.student.id}_{req.quiz.id}": req.id
            for req in retake_requests
        }

        # Отримуємо всіх студентів курсу
        students = course.students.all()

        # Попереднє завантаження спроб проходження тесту для всіх студентів та тестів
        quizzes = [lesson.quiz for lesson in quiz_lessons]
        attempts = QuizAttempt.objects.filter(
            student__in=students,
            quiz__in=quizzes
        ).select_related('student', 'quiz')
        attempt_map = {
            (attempt.student.id, attempt.quiz.id): attempt
            for attempt in attempts
        }

        # Формування журналу оцінок
        for student in students:
            lesson_scores = []
            for lesson in quiz_lessons:
                quiz = lesson.quiz
                attempt = attempt_map.get((student.id, quiz.id))
                score = attempt.score if attempt else None
                # Формування ключа для перевірки повторної спроби
                retake_key = f"{student.id}_{quiz.id}"
                lesson_scores.append({
                    "lesson": lesson,
                    "score": score,
                    "retake_request_id": retake_map.get(retake_key)
                })
            gradebook.append({
                "student": student,
                "lesson_scores": lesson_scores,
            })
    else:
        # Для студентів можна передати інший набір даних або залишити gradebook порожнім
        retake_map = {}

    return render(request, 'courses/course_detail.html', {
        'course': course,
        'lessons': lessons,
        'quiz_lessons': quiz_lessons,
        'gradebook': gradebook,
    })


@login_required
def create_lesson_view(request, course_id):
    course = get_object_or_404(Course, id=course_id)

    if not request.user.is_teacher() or course.teacher != request.user:
        messages.warning(request, "Лише викладачі можуть додавати уроки.")
        return redirect('users:cabinet')

    if request.method == 'POST':
        form = LessonForm(request.POST)
        if form.is_valid():
            lesson = form.save(commit=False)
            lesson.course = course
            lesson.save()
            messages.success(request, f'Урок "{lesson.title}" успішно створено.')
            return redirect('users:cabinet')
    else:
        form = LessonForm()

    return render(request, 'courses/create_lesson.html', {
        'form': form,
        'course': course
    })


@login_required
def create_course_view(request):
    if not request.user.is_teacher():
        messages.warning(request, "Лише викладачі можуть створювати курси.")
        return redirect('users:cabinet')

    if request.method == 'POST':
        form = CourseForm(request.POST)
        if form.is_valid():
            course = form.save(commit=False)
            course.teacher = request.user
            course.save()
            messages.success(request, f'Курс "{course.title}" успішно створено.')
            return redirect('users:cabinet')
    else:
        form = CourseForm()

    return render(request, 'courses/create_course.html', {'form': form})
