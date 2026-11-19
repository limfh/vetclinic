from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta


# Модель владельца питомца
class Owner(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    phone = models.CharField(max_length=30, blank=True)
    reminder_days = models.IntegerField(default=14)

    def __str__(self):
        full_name = self.user.get_full_name()
        if full_name != '':
            return full_name
        else:
            return self.user.username


# Вид животного (Кошка, Собака и т.д.)
class Species(models.Model):
    name = models.CharField(max_length=50)

    def __str__(self):
        return self.name


# Карточка питомца
class Pet(models.Model):
    owner = models.ForeignKey(Owner, on_delete=models.CASCADE)
    species = models.ForeignKey(Species, on_delete=models.PROTECT)
    name = models.CharField(max_length=80)
    birth_date = models.DateField()
    breed = models.CharField(max_length=100, blank=True)
    sex = models.CharField(max_length=30, blank=True)
    chip = models.CharField(max_length=50, blank=True)
    passport = models.CharField(max_length=50, blank=True)

    # Считаем возраст питомца в годах и месяцах
    @property
    def age(self):
        today = timezone.localdate()
        months = (today.year - self.birth_date.year) * 12 + (today.month - self.birth_date.month)
        
        if today.day < self.birth_date.day:
            months = months - 1
            
        if months < 0:
            months = 0

        if months >= 12:
            years = months // 12
            rem_months = months % 12
            return str(years) + ' лет ' + str(rem_months) + ' мес.'
        else:
            return str(months) + ' мес.'

    # Получаем список просроченных прививок
    @property
    def overdue(self):
        today = timezone.localdate()
        return self.vaccination_set.filter(done_date__isnull=True, due_date__lt=today)

    def __str__(self):
        return self.name


# Врач клиники
class Doctor(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)
    name = models.CharField(max_length=100)
    specialty = models.CharField(max_length=100)
    room = models.CharField(max_length=20, default='4')

    def __str__(self):
        return self.name


# Запись на приём
class Appointment(models.Model):
    pet = models.ForeignKey(Pet, on_delete=models.CASCADE)
    doctor = models.ForeignKey(Doctor, on_delete=models.PROTECT)
    date = models.DateField()
    time = models.TimeField()
    service = models.CharField(max_length=150)
    status = models.CharField(max_length=30, default='Ожидает')
    complaint = models.TextField(blank=True)

    def __str__(self):
        return str(self.pet.name) + ' - ' + str(self.date)


# Диагноз по приёму
class Diagnosis(models.Model):
    appointment = models.OneToOneField(Appointment, on_delete=models.CASCADE, related_name='diagnosis')
    text = models.TextField()


# Назначения и лечение
class Treatment(models.Model):
    appointment = models.ForeignKey(Appointment, on_delete=models.CASCADE, related_name='treatments')
    text = models.TextField()


# Справочник вакцин
class Vaccine(models.Model):
    name = models.CharField(max_length=100)
    disease = models.CharField(max_length=100)

    def __str__(self):
        return self.name


# Схема вакцинации (правило по виду и возрасту)
class VaccinationScheme(models.Model):
    species = models.ForeignKey(Species, on_delete=models.CASCADE)
    vaccine = models.ForeignKey(Vaccine, on_delete=models.CASCADE)
    age_days = models.IntegerField()
    label = models.CharField(max_length=100)

    def __str__(self):
        return self.label


# Конкретная прививка питомца в графике
class Vaccination(models.Model):
    pet = models.ForeignKey(Pet, on_delete=models.CASCADE)
    scheme = models.ForeignKey(VaccinationScheme, on_delete=models.PROTECT)
    due_date = models.DateField()
    done_date = models.DateField(null=True, blank=True)
    batch = models.CharField(max_length=100, blank=True)

    # Считаем количество дней просрочки
    @property
    def overdue_days(self):
        if self.done_date != None:
            return 0
            
        today = timezone.localdate()
        diff = (today - self.due_date).days
        
        if diff > 0:
            return diff
        else:
            return 0


# Функция для автоматического создания графика прививок
def make_schedule(pet):
    schemes = VaccinationScheme.objects.filter(species=pet.species)
    
    for scheme in schemes:
        exists = Vaccination.objects.filter(pet=pet, scheme=scheme).exists()
        if not exists:
            planned_date = pet.birth_date + timedelta(days=scheme.age_days)
            Vaccination.objects.create(
                pet=pet,
                scheme=scheme,
                due_date=planned_date
            )