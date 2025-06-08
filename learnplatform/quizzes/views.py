from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.forms import modelformset_factory, inlineformset_factory
from django.contrib import messages

from courses.models import Lesson

from .forms import QuizForm, QuestionForm, AnswerForm
from .models import Quiz, Question, Answer, QuizAttempt
from .models import RetakeRequest
from django.views.decorators.http import require_POST
from quizzes.models import RetakeRequest


@login_required
@require_POST
def approve_retake_view(request, request_id):
    retake = get_object_or_404(RetakeRequest, id=request_id)

    if request.user != retake.quiz.lesson.course.teacher:
        messages.warning(request, "Ви не маєте прав для схвалення.")
        return redirect('users:cabinet')

    retake.approved = True
    retake.save()

    messages.success(request, f"Схвалено повторну спробу для {retake.student.username}.")
    return redirect('courses:detail', course_id=retake.quiz.lesson.course.id)


@login_required
@require_POST
def request_retake_view(request, lesson_id):
    quiz = get_object_or_404(Quiz, lesson_id=lesson_id)
    if not request.user.is_student():
        return redirect('users:cabinet')

    retake, created = RetakeRequest.objects.get_or_create(
        student=request.user,
        quiz=quiz,
        defaults={'approved': False}
    )

    if created:
        messages.success(request, 'Запит на повторну спробу надіслано викладачу.')
    else:
        messages.info(request, 'Ви вже подали запит на повторну спробу.')

    return redirect('courses:lesson_detail', course_id=quiz.lesson.course.id, lesson_id=lesson_id)


@login_required
def take_quiz_view(request, lesson_id):
    quiz = get_object_or_404(Quiz, lesson_id=lesson_id)
    course = quiz.lesson.course

    if request.user.is_teacher() or request.user not in course.students.all():
        messages.warning(request, "У вас немає доступу до цього тесту.")
        return redirect('users:cabinet')

    lesson = quiz.lesson
    existing_attempt = QuizAttempt.objects.filter(student=request.user, quiz=quiz).order_by('-completed_at').first()

    # Перевірка запитів на повторну спробу
    approved_retake = RetakeRequest.objects.filter(student=request.user, quiz=quiz, approved=True).first()
    request_already_sent = RetakeRequest.objects.filter(student=request.user, quiz=quiz, approved=False).exists()

    # Якщо користувач уже проходив тест і не має підтвердженого запиту на повтор,
    # не дозволяємо нову спробу
    if existing_attempt and not approved_retake:
        return render(request, 'quizzes/already_done.html', {
            'quiz': quiz,
            'score': existing_attempt.score,
            'lesson': lesson,
            'request_already_sent': request_already_sent,
        })

    questions = quiz.questions.prefetch_related('answers')

    if request.method == 'POST':
        total = questions.count()
        correct = 0
        incorrect_questions = []

        for question in questions:
            selected = request.POST.get(f'question_{question.id}')
            correct_answer = question.answers.filter(is_correct=True).first()

            if selected and str(correct_answer.id) == selected:
                correct += 1
            else:
                incorrect_questions.append(question)

        score = round((correct / total) * 100, 2) if total > 0 else 0

        # Якщо є підтверджений запит на повтор, видаляємо попередню спробу
        if approved_retake and existing_attempt:
            existing_attempt.delete()

        attempt = QuizAttempt.objects.create(
            student=request.user,
            quiz=quiz,
            score=score
        )
        attempt.incorrect_questions.set(incorrect_questions)

        # Після повторного проходження видаляємо запит на повтор
        if approved_retake:
            approved_retake.delete()

        messages.success(request, f'Тест завершено! Ваш результат: {score}%.')
        return render(request, 'quizzes/quiz_result.html', {
            'quiz': quiz,
            'score': score
        })

    return render(request, 'quizzes/take_quiz.html', {
        'quiz': quiz,
        'questions': questions
    })


@login_required
def edit_answers_view(request, question_id):
    question = get_object_or_404(Question, id=question_id)
    quiz = question.quiz

    if request.user != quiz.lesson.course.teacher:
        messages.warning(request, "Редагування відповідей доступне лише викладачу.")
        return redirect('users:cabinet')

    AnswerFormSet = inlineformset_factory(
        Question, Answer, form=AnswerForm,
        extra=2, can_delete=True
    )

    if request.method == 'POST':
        formset = AnswerFormSet(request.POST, instance=question)
        if formset.is_valid():
            formset.save()
            messages.success(request, "Варіанти відповідей успішно збережені.")
            return redirect('quizzes:edit', lesson_id=quiz.lesson.id)
    else:
        formset = AnswerFormSet(instance=question)

    return render(request, 'quizzes/edit_answers.html', {
        'question': question,
        'formset': formset
    })


@login_required
def edit_quiz_view(request, lesson_id):
    quiz = get_object_or_404(Quiz, lesson_id=lesson_id)

    QuestionFormSet = modelformset_factory(Question, form=QuestionForm, extra=1, can_delete=True)

    if request.method == 'POST':
        formset = QuestionFormSet(request.POST, queryset=quiz.questions.all())
        if formset.is_valid():
            instances = formset.save(commit=False)
            for instance in instances:
                instance.quiz = quiz
                instance.save()
            for obj in formset.deleted_objects:
                obj.delete()
            messages.success(request, "Запитання збережено.")
            return redirect('quizzes:edit', lesson_id=lesson_id)
    else:
        formset = QuestionFormSet(queryset=quiz.questions.all())

    return render(request, 'quizzes/edit_quiz.html', {
        'quiz': quiz,
        'formset': formset
    })


@login_required
def create_quiz_view(request, lesson_id):
    lesson = get_object_or_404(Lesson, id=lesson_id)

    if not request.user.is_teacher() or lesson.course.teacher != request.user:
        messages.warning(request, "Лише викладач курсу може створювати тести.")
        return redirect('users:cabinet')

    if hasattr(lesson, 'quiz'):
        messages.info(request, "До цього уроку вже прив'язано тест.")
        return redirect('quizzes:edit', lesson_id=lesson_id)

    if request.method == 'POST':
        quiz_form = QuizForm(request.POST)
        if quiz_form.is_valid():
            quiz = quiz_form.save(commit=False)
            quiz.lesson = lesson
            quiz.save()
            messages.success(request, f'Тест "{quiz.title}" створено.')
            return redirect('quizzes:edit', lesson_id=lesson_id)
    else:
        quiz_form = QuizForm()

    return render(request, 'quizzes/create_quiz.html', {'form': quiz_form, 'lesson': lesson})
