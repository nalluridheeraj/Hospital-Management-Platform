from datetime import timedelta
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from appointments.models import Doctor, DoctorSlot, Patient, AuditLog


class Command(BaseCommand):
    help = "Seeds the database with synthetic doctors, slots, patients, and test users."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="Force re-seeding even if data exists")

    def handle(self, *args, **options):
        force = options.get("force", False)

        if User.objects.filter(username="admin").exists() and not force:
            self.stdout.write(self.style.WARNING("Database already seeded. Skipping."))
            return

        self.stdout.write(self.style.NOTICE("Initializing synthetic seed data..."))

        # 1. Seed Users
        users_data = [
            {"username": "admin", "password": "Admin@Password2026!", "email": "admin@hospital.example.com", "is_staff": True, "is_superuser": True},
            {"username": "dr.smith", "password": "Doctor@Password2026!", "email": "alice.smith@hospital.example.com", "is_staff": True, "is_superuser": False},
            {"username": "dr.jones", "password": "Doctor@Password2026!", "email": "bob.jones@hospital.example.com", "is_staff": True, "is_superuser": False},
            {"username": "patient.john", "password": "Patient@Password2026!", "email": "john.doe.synthetic@hospital.example.com", "is_staff": False, "is_superuser": False},
            {"username": "patient.jane", "password": "Patient@Password2026!", "email": "jane.roe.synthetic@hospital.example.com", "is_staff": False, "is_superuser": False},
        ]

        for u in users_data:
            user, created = User.objects.get_or_create(
                username=u["username"],
                defaults={
                    "email": u["email"],
                    "is_staff": u["is_staff"],
                    "is_superuser": u["is_superuser"],
                },
            )
            user.set_password(u["password"])
            user.save()

        # 2. Seed Doctors
        doctors_data = [
            {"doctor_code": "DOC-001", "name": "Dr. Alice Smith", "specialization": "Cardiology", "department": "Cardiovascular Sciences", "email": "alice.smith@hospital.example.com"},
            {"doctor_code": "DOC-002", "name": "Dr. Bob Jones", "specialization": "Neurology", "department": "Neurosciences", "email": "bob.jones@hospital.example.com"},
            {"doctor_code": "DOC-003", "name": "Dr. Clara Oswald", "specialization": "Pediatrics", "department": "Pediatric Medicine", "email": "clara.oswald@hospital.example.com"},
            {"doctor_code": "DOC-004", "name": "Dr. David Chen", "specialization": "Orthopedics", "department": "Surgical Specialties", "email": "david.chen@hospital.example.com"},
        ]

        doctors = []
        for d in doctors_data:
            doc, _ = Doctor.objects.get_or_create(
                doctor_code=d["doctor_code"],
                defaults={
                    "name": d["name"],
                    "specialization": d["specialization"],
                    "department": d["department"],
                    "email": d["email"],
                },
            )
            doctors.append(doc)

        # 3. Seed Synthetic Patients
        patients_data = [
            {"patient_code": "PAT-001", "full_name": "John Doe", "date_of_birth": "1985-04-12", "phone": "+1-555-0101", "email": "john.doe.synthetic@hospital.example.com"},
            {"patient_code": "PAT-002", "full_name": "Jane Roe", "date_of_birth": "1990-08-23", "phone": "+1-555-0102", "email": "jane.roe.synthetic@hospital.example.com"},
            {"patient_code": "PAT-003", "full_name": "Alex Casey", "date_of_birth": "1978-11-30", "phone": "+1-555-0103", "email": "alex.casey.synthetic@hospital.example.com"},
            {"patient_code": "PAT-004", "full_name": "Sam Rivera", "date_of_birth": "1995-02-17", "phone": "+1-555-0104", "email": "sam.rivera.synthetic@hospital.example.com"},
        ]

        for p in patients_data:
            Patient.objects.get_or_create(
                patient_code=p["patient_code"],
                defaults={
                    "full_name": p["full_name"],
                    "date_of_birth": p["date_of_birth"],
                    "phone": p["phone"],
                    "email": p["email"],
                },
            )

        # 4. Seed Standardized Future Slots
        base_date = timezone.now().date() + timedelta(days=1)
        slot_hours = [9, 10, 11, 14, 15]

        for doc in doctors:
            for day_offset in range(3):
                target_date = base_date + timedelta(days=day_offset)
                for hour in slot_hours:
                    start_dt = timezone.make_aware(
                        timezone.datetime(target_date.year, target_date.month, target_date.day, hour, 0, 0)
                    )
                    end_dt = start_dt + timedelta(minutes=45)

                    DoctorSlot.objects.get_or_create(
                        doctor=doc,
                        start_time=start_dt,
                        defaults={
                            "end_time": end_dt,
                            "is_available": True,
                        },
                    )

        # 5. Audit Log Entry
        AuditLog.objects.create(
            actor_id="system-seed",
            actor_role="system",
            action="SEED_DATABASE",
            resource_type="all",
            details="Synthetic doctors, slots, patients, and test users seeded successfully.",
            status="SUCCESS",
        )

        self.stdout.write(self.style.SUCCESS("Synthetic seed data seeded successfully!"))
