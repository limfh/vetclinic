from django.contrib import admin
from .models import Owner, Species, Pet, Doctor, Appointment, Diagnosis, Treatment, Vaccine, VaccinationScheme, Vaccination
for model in (Owner, Species, Pet, Doctor, Appointment, Diagnosis, Treatment, Vaccine, VaccinationScheme, Vaccination):
    admin.site.register(model)
