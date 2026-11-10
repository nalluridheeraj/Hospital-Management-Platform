import os
import shutil
import pytest
from django.db import connection
from appointments.models import Appointment, Doctor, DoctorSlot, Patient
from scripts.backup import backup_database
from scripts.restore import restore_database


@pytest.mark.django_db(transaction=True)
def test_backup_and_restore_cycle():
    """Validates complete database backup creation, simulated data disaster,
    and subsequent restore with data integrity verification.
    """
    test_backup_dir = "test_backups"
    os.makedirs(test_backup_dir, exist_ok=True)

    doctor = Doctor.objects.first()
    slot = DoctorSlot.objects.filter(doctor=doctor, is_available=True).first()
    patient = Patient.objects.first()

    # Step 1: Create appointment
    slot.is_available = False
    slot.save()
    test_apt = Appointment.objects.create(
        appointment_code="APT-BACKUP-TEST-001",
        doctor=doctor,
        slot=slot,
        patient=patient,
        start_time=slot.start_time,
        end_time=slot.end_time,
        status=Appointment.STATUS_CONFIRMED,
        reason="Pre-backup test consultation",
    )
    initial_count = Appointment.objects.count()
    assert initial_count >= 1

    try:
        # Step 2: Backup database
        backup_file = backup_database(output_dir=test_backup_dir, retention_count=5)
        assert os.path.exists(backup_file), f"Backup file not created: {backup_file}"
        assert os.path.exists(backup_file + ".sha256"), "Checksum file not created"

        # Step 3: Simulate Disaster
        Appointment.objects.all().delete()
        assert Appointment.objects.count() == 0, "Appointments should be wiped to simulate disaster"

        # Step 4: Execute Restore
        restore_success = restore_database(backup_file)
        assert restore_success is True, "Database restore reported failure"

        # Step 5: Verify Data Recovery
        recovered_count = Appointment.objects.count()
        assert recovered_count == initial_count, (
            f"Data mismatch post-restore. Expected {initial_count}, found {recovered_count}"
        )
        restored_apt = Appointment.objects.filter(appointment_code="APT-BACKUP-TEST-001").first()
        assert restored_apt is not None, "Test appointment missing after restoration"
        assert restored_apt.reason == "Pre-backup test consultation"

    finally:
        if os.path.exists(test_backup_dir):
            shutil.rmtree(test_backup_dir, ignore_errors=True)
