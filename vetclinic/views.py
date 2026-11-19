import json
from datetime import date, datetime, timedelta

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import HttpResponse
from django.shortcuts import redirect, render

from .models import *


# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ

# Определяем, кто сейчас на сайте: гость, админ, врач или владелец
def user_role(user):
    if not user.is_authenticated:
        return 'guest'
    if user.is_superuser:
        return 'admin'
    for doctor in Doctor.objects.all():
        if doctor.user == user:
            return 'doctor'
    return 'owner'


# Базовые данные, которые нужны почти на каждой странице
def base_context(request, active=''):
    return {
        'role': user_role(request.user),
        'today': date.today(),
        'active': active,
    }


# Получаем профиль владельца для текущего пользователя
def owner_for(request):
    for owner in Owner.objects.all():
        if owner.user == request.user:
            return owner
    return None


# Какие питомцы доступны текущему пользователю
def visible_pets(request):
    role = user_role(request.user)
    if role == 'admin' or role == 'doctor':
        return list(Pet.objects.all())

    owner = owner_for(request)
    result = []
    for pet in Pet.objects.all():
        if pet.owner == owner:
            result.append(pet)
    return result


# ОБЫЧНЫЕ СТРАНИЦЫ (видны всем)

def home(request):
    return render(request, 'home.html', base_context(request, 'home'))


def services(request):
    return render(request, 'services.html', base_context(request, 'services'))


def contacts(request):
    return render(request, 'contacts.html', base_context(request, 'contacts'))


def doctors(request):
    context = base_context(request, 'doctors')
    context['doctors'] = Doctor.objects.all()
    return render(request, 'doctors.html', context)


# ВХОД, ВЫХОД И РЕГИСТРАЦИЯ

def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        # Проверяем логин и пароль в базе
        user = authenticate(request, username=username, password=password)

        if user is None:
            messages.error(request, 'Неверный логин или пароль.')
        else:
            login(request, user)
            role = user_role(user)
            if role == 'admin':
                return redirect('clinic')
            if role == 'doctor':
                return redirect('doctor')
            return redirect('pets')

    return render(request, 'login.html', base_context(request))


def register(request):
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        phone = request.POST.get('phone', '').strip()
        password = request.POST.get('password', '')
        password_repeat = request.POST.get('password_repeat', '')

        # Проверяем только пароль
        if password != password_repeat:
            messages.error(request, 'Пароли не совпадают.')
        elif len(password) < 6:
            messages.error(request, 'Пароль должен быть не короче 6 символов.')
        else:
            user = User.objects.create_user(
                username=username,
                password=password,
                first_name=first_name,
                last_name=last_name
            )
            Owner.objects.create(user=user, phone=phone)

            login(request, user)
            messages.success(request, 'Регистрация завершена. Добавьте вашего питомца.')
            return redirect('pets')

    return render(request, 'register.html', base_context(request))


def logout_view(request):
    logout(request)
    return redirect('home')


# ПИТОМЦЫ И ПРИВИВКИ

@login_required
def pets(request):
    owner = owner_for(request)

    if owner is None:
        if user_role(request.user) == 'doctor':
            return redirect('doctor')
        return redirect('clinic')

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        birth_date_str = request.POST.get('birth_date', '')
        species_id = request.POST.get('species')
        breed = request.POST.get('breed', '')
        sex = request.POST.get('sex', '')

        try:
            birth_date = date.fromisoformat(birth_date_str)
            species = Species.objects.get(id=species_id)

            if not name or birth_date > date.today():
                messages.error(request, 'Проверьте имя и дату рождения питомца.')
            else:
                pet = Pet.objects.create(
                    owner=owner,
                    species=species,
                    name=name,
                    birth_date=birth_date,
                    breed=breed,
                    sex=sex
                )
                make_schedule(pet)
                messages.success(request, 'Питомец добавлен. График прививок сформирован.')
                return redirect('pet_detail', pk=pet.id)
        except Exception:
            messages.error(request, 'Проверьте имя, вид и дату рождения питомца.')

    context = base_context(request)
    context.update({
        'pets': visible_pets(request),
        'species': Species.objects.all(),
        'owner': owner,
    })
    return render(request, 'pets.html', context)


@login_required
def delete_pet(request, pk):
    if request.method != 'POST':
        return redirect('pets')

    owner = owner_for(request)
    if owner is None:
        messages.error(request, 'Удалять питомцев может только их владелец.')
        return redirect('home')

    try:
        pet = Pet.objects.get(pk=pk, owner=owner)
    except Exception:
        return redirect('pets')

    pet_name = pet.name
    pet.delete()

    messages.success(request, f'Питомец {pet_name} и связанные данные удалены.')
    return redirect('pets')


@login_required
def pet_detail(request, pk):
    my_pets = visible_pets(request)

    # Ищем нужного питомца среди доступных
    pet = None
    for p in my_pets:
        if p.id == pk:
            pet = p
            break

    if pet is None:
        return redirect('pets')

    # Прививки этого питомца
    shots = []
    for shot in Vaccination.objects.all():
        if shot.pet == pet:
            shots.append(shot)

    # Записи на прием этого питомца
    appointments = []
    for appt in Appointment.objects.all():
        if appt.pet == pet:
            appointments.append(appt)

    context = base_context(request)
    context.update({
        'pet': pet,
        'pets': my_pets,
        'shots': shots,
        'appointments': appointments[-1:],  # Берем последнюю запись
    })
    return render(request, 'pet_detail.html', context)


@login_required
def vaccinations(request):
    my_pets = visible_pets(request)
    pet_id = request.GET.get('pet', '')

    # Выбираем питомца из адресной строки (?pet=5) или берем первого
    pet = None
    if pet_id:
        for p in my_pets:
            if str(p.id) == pet_id:
                pet = p
                break
    elif len(my_pets) > 0:
        pet = my_pets[0]

    if request.method == 'POST' and pet is not None:
        make_schedule(pet)
        messages.success(request, 'График обновлён.')
        return redirect(f'/vaccinations/?pet={pet.id}')

    shots = []
    if pet is not None:
        for shot in Vaccination.objects.all():
            if shot.pet == pet:
                shots.append(shot)

    context = base_context(request)
    context.update({
        'pet': pet,
        'pets': my_pets,
        'shots': shots,
    })
    return render(request, 'vaccinations.html', context)


# НАПОМИНАНИЯ И ИСТОРИЯ ЛЕЧЕНИЯ

@login_required
def reminders(request):
    owner = owner_for(request)
    if owner is None:
        return HttpResponse('Только для владельца')

    if request.method == 'POST':
        days = request.POST.get('days')
        if days in ['7', '14', '30']:
            owner.reminder_days = int(days)
            owner.save()
        return redirect('reminders')

    today = date.today()
    limit_date = today + timedelta(days=owner.reminder_days)
    my_pets = visible_pets(request)

    shots = []
    overdue = []
    upcoming = []

    for shot in Vaccination.objects.all():
        if shot.pet in my_pets and shot.done_date is None and shot.due_date <= limit_date:
            shots.append(shot)
            if shot.due_date < today:
                overdue.append(shot)
            else:
                upcoming.append(shot)

    appointments = []
    for appt in Appointment.objects.all():
        if appt.pet in my_pets and appt.date >= today and appt.status not in ['Отменён', 'Завершён']:
            appointments.append(appt)

    context = base_context(request)
    context.update({
        'shots': shots,
        'overdue': overdue,
        'upcoming_shots': upcoming,
        'appointments': appointments,
        'owner': owner,
        'selected': request.GET.get('filter', 'all'),
    })
    return render(request, 'reminders.html', context)


@login_required
def history(request):
    my_pets = visible_pets(request)
    pet_id = request.GET.get('pet', '')
    year = request.GET.get('year', '')

    # Отбираем завершенные приемы по фильтрам
    visits = []
    for appt in Appointment.objects.all():
        if appt.pet in my_pets and appt.status == 'Завершён':
            if pet_id and str(appt.pet.id) != pet_id:
                continue
            if year and str(appt.date.year) != year:
                continue
            visits.append(appt)

    # Какой прием показать подробно
    appt_id = request.GET.get('appointment', '')
    selected = None
    if appt_id:
        for v in visits:
            if str(v.id) == appt_id:
                selected = v
                break
    elif len(visits) > 0:
        selected = visits[0]

    # Список уникальных годов для фильтра
    years_list = []
    for visit in visits:
        if visit.date.year not in years_list:
            years_list.append(visit.date.year)

    # Все уже сделанные прививки
    completed_shots = []
    for shot in Vaccination.objects.all():
        if shot.pet in my_pets and shot.done_date is not None:
            completed_shots.append(shot)

    context = base_context(request)
    context.update({
        'visits': visits,
        'pets': my_pets,
        'selected': selected,
        'pet_id': pet_id,
        'year': year,
        'years': years_list,
        'completed_shots': completed_shots,
    })
    return render(request, 'history.html', context)


# ЗАПИСЬ НА ПРИЕМ

@login_required
def book(request):
    my_pets = visible_pets(request)
    if len(my_pets) == 0:
        messages.error(request, 'Сначала добавьте питомца.')
        return redirect('pets')

    # Запрос от JavaScript: вернуть список занятого времени у врача на выбранный день
    if request.GET.get('slots') == '1':
        doctor_id = request.GET.get('doctor')
        day = request.GET.get('date')
        busy_times = []

        if doctor_id and day:
            for appt in Appointment.objects.all():
                if str(appt.doctor.id) == doctor_id and str(appt.date) == day and appt.status != 'Отменён':
                    busy_times.append(appt.time.strftime('%H:%M'))

        text = json.dumps({'busy': busy_times})
        return HttpResponse(text, content_type='application/json')

    # Создание новой записи
    if request.method == 'POST':
        try:
            pet = Pet.objects.get(id=request.POST.get('pet'))
            doctor = Doctor.objects.get(id=request.POST.get('doctor'))
            visit_date = date.fromisoformat(request.POST.get('date', ''))
            visit_time = datetime.strptime(request.POST.get('time', ''), '%H:%M').time()
            service = request.POST.get('service', 'Осмотр')

            # Проверяем, свободно ли это время у врача
            is_busy = False
            for appt in Appointment.objects.all():
                if appt.doctor == doctor and appt.date == visit_date and appt.time == visit_time and appt.status != 'Отменён':
                    is_busy = True

            if visit_date < date.today() or is_busy:
                messages.error(request, 'Дата занята или указана неверно.')
            else:
                appointment = Appointment.objects.create(
                    pet=pet,
                    doctor=doctor,
                    date=visit_date,
                    time=visit_time,
                    service=service
                )
                return redirect('appointment_detail', pk=appointment.id)
        except Exception:
            messages.error(request, 'Дата занята или данные записи указаны неверно.')

    context = base_context(request)
    context.update({
        'pets': my_pets,
        'doctors': Doctor.objects.all(),
    })
    return render(request, 'book.html', context)


@login_required
def appointment_detail(request, pk):
    try:
        appointment = Appointment.objects.get(id=pk)
    except Exception:
        return redirect('home')

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'cancel':
            appointment.status = 'Отменён'
            appointment.save()
            messages.success(request, 'Запись отменена.')

        elif action == 'confirm':
            appointment.status = 'Подтверждён'
            appointment.save()
            messages.success(request, 'Запись подтверждена.')

        elif action == 'move':
            try:
                appointment.date = date.fromisoformat(request.POST.get('date', ''))
                appointment.time = datetime.strptime(request.POST.get('time', ''), '%H:%M').time()
                appointment.status = 'Ожидает'
                appointment.save()
                messages.success(request, 'Запись перенесена.')
            except Exception:
                messages.error(request, 'Дата указана неверно.')

        return redirect('appointment_detail', pk=pk)

    context = base_context(request)
    context['appt'] = appointment
    return render(request, 'appointment.html', context)


# КАБИНЕТ ВРАЧА

# Вспомогательная функция: сохраняет жалобы, диагноз и назначение
def save_protocol(request, appointment):
    appointment.complaint = request.POST.get('complaint', '')
    appointment.save()

    diag_text = request.POST.get('diagnosis', '')
    diag = None
    for d in Diagnosis.objects.all():
        if d.appointment == appointment:
            diag = d
            break

    if diag is not None:
        diag.text = diag_text
        diag.save()
    else:
        Diagnosis.objects.create(appointment=appointment, text=diag_text)

    treat_text = request.POST.get('treatment', '')
    treat = None
    for t in Treatment.objects.all():
        if t.appointment == appointment:
            treat = t
            break

    if treat is not None:
        treat.text = treat_text
        treat.save()
    else:
        Treatment.objects.create(appointment=appointment, text=treat_text)


@login_required
def doctor_page(request, pk=None):
    if user_role(request.user) != 'doctor':
        messages.error(request, 'Доступно только для врача.')
        return redirect('home')

    try:
        doctor = Doctor.objects.get(user=request.user)
    except Exception:
        return redirect('home')

    # Все не отмененные записи этого врача
    appointments = []
    for appt in Appointment.objects.all():
        if appt.doctor == doctor and appt.status != 'Отменён':
            appointments.append(appt)

    # Выбираем, какой прием открыть сейчас
    appointment = None
    if pk is not None:
        try:
            appointment = Appointment.objects.get(id=pk)
        except Exception:
            return redirect('doctor')
    else:
        for appt in appointments:
            if appt.status in ['Ожидает', 'Подтверждён']:
                appointment = appt
                break
        if appointment is None and len(appointments) > 0:
            appointment = appointments[0]

    # Обработка кнопок врача
    if request.method == 'POST' and appointment is not None:
        action = request.POST.get('action')

        if action == 'save':
            save_protocol(request, appointment)
            messages.success(request, 'Протокол сохранён.')

        if action in ['shot', 'complete']:
            shot_id = request.POST.get('shot')
            if shot_id:
                try:
                    shot = Vaccination.objects.get(id=shot_id)
                    shot.done_date = date.fromisoformat(request.POST.get('done_date', ''))
                    shot.batch = request.POST.get('batch', '')
                    shot.save()
                except Exception:
                    messages.error(request, 'Укажите дату и серию вакцины.')
                    return redirect('doctor_appointment', pk=appointment.id)

            if action == 'complete':
                appointment.status = 'Завершён'
                appointment.save()
                messages.success(request, 'Приём завершён.')

        return redirect('doctor_appointment', pk=appointment.id)

    # Несделанные прививки и лечение выбранного пациента
    shots = []
    treatment = None
    if appointment is not None:
        for shot in Vaccination.objects.all():
            if shot.pet == appointment.pet and shot.done_date is None:
                shots.append(shot)
        for t in Treatment.objects.all():
            if t.appointment == appointment:
                treatment = t
                break

    context = base_context(request)
    context.update({
        'appt': appointment,
        'appointments': appointments,
        'shots': shots,
        'treatment': treatment,
        'tab': request.GET.get('tab', 'visits'),
        'patients': Pet.objects.all(),
    })
    return render(request, 'doctor.html', context)


# ПАНЕЛЬ АДМИНИСТРАТОРА

# Вспомогательная функция: добавляет новые записи в справочники
def add_clinic_item(request):
    action = request.POST.get('action')
    name = request.POST.get('name', '').strip()

    if action == 'species' and name:
        Species.objects.create(name=name)
        messages.success(request, 'Вид добавлен.')

    elif action == 'vaccine' and name:
        Vaccine.objects.create(name=name, disease=request.POST.get('disease', ''))
        messages.success(request, 'Вакцина добавлена.')

    elif action == 'doctor' and name:
        Doctor.objects.create(
            name=name,
            specialty=request.POST.get('specialty', ''),
            room=request.POST.get('room', '4')
        )
        messages.success(request, 'Врач добавлен.')

    elif action == 'scheme':
        try:
            species = Species.objects.get(id=request.POST.get('species'))
            vaccine = Vaccine.objects.get(id=request.POST.get('vaccine'))
            VaccinationScheme.objects.create(
                species=species,
                vaccine=vaccine,
                age_days=int(request.POST.get('age_days', '0')),
                label=request.POST.get('label', '')
            )
            for pet in Pet.objects.all():
                if pet.species == species:
                    make_schedule(pet)
            messages.success(request, 'Схема сохранена.')
        except Exception:
            messages.error(request, 'Проверьте правило вакцинации.')
    else:
        messages.error(request, 'Заполните данные.')


@login_required
def clinic(request):
    if user_role(request.user) != 'admin':
        messages.error(request, 'Доступно только для администратора.')
        return redirect('home')

    if request.method == 'POST':
        add_clinic_item(request)
        return redirect('/clinic/?tab=reference')

    # Журнал всех записей + фильтр по врачу + счетчики
    doctor_id = request.GET.get('doctor', '')
    appointments = []
    waiting_count = 0
    confirmed_count = 0

    for appt in Appointment.objects.all():
        if appt.status == 'Ожидает':
            waiting_count += 1
        if appt.status == 'Подтверждён':
            confirmed_count += 1
        if not doctor_id or str(appt.doctor.id) == doctor_id:
            appointments.append(appt)

    overdue_count = 0
    for shot in Vaccination.objects.all():
        if shot.done_date is None and shot.due_date < date.today():
            overdue_count += 1

    context = base_context(request)
    context.update({
        'appointments': appointments,
        'doctors': Doctor.objects.all(),
        'owners': Owner.objects.all(),
        'species': Species.objects.all(),
        'vaccines': Vaccine.objects.all(),
        'schemes': VaccinationScheme.objects.all(),
        'tab': request.GET.get('tab', 'journal'),
        'doctor_id': doctor_id,
        'waiting_count': waiting_count,
        'confirmed_count': confirmed_count,
        'overdue_count': overdue_count,
    })
    return render(request, 'clinic.html', context)