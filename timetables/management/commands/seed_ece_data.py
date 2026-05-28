from datetime import date, time

from django.core.management.base import BaseCommand

from academics.models import AcademicTerm, Department, Section, Subject
from accounts.models import AppUser, Faculty
from constraints.models import ConstraintType, FacultyConstraint
from infrastructure.models import Building, Day, Room, Timeslot
from timetables.models import SessionGroup, SessionGroupMember, TeachingAssignment, Timetable


class Command(BaseCommand):
    help = "Seed a realistic tier-1-style ECE department dataset for scheduler validation."

    def handle(self, *args, **options):
        term, _ = AcademicTerm.objects.update_or_create(
            academic_year="2026-2027",
            term_type=AcademicTerm.TermType.ODD,
            defaults={
                "start_date": date(2026, 7, 1),
                "end_date": date(2026, 12, 15),
                "is_active": True,
            },
        )

        ece, _ = Department.objects.update_or_create(
            department_code="ECE",
            defaults={"department_name": "Electronics and Communication Engineering"},
        )

        faculty_specs = [
            ("hod.ece@example.edu", AppUser.Role.HOD, "Prof. Ananya Krishnan"),
            ("signals.ece@example.edu", AppUser.Role.FACULTY, "Prof. S. Ramanathan"),
            ("analog.ece@example.edu", AppUser.Role.FACULTY, "Prof. Nandita Menon"),
            ("digital.ece@example.edu", AppUser.Role.FACULTY, "Dr. Ishaan Kapoor"),
            ("network.ece@example.edu", AppUser.Role.FACULTY, "Dr. Priya Varma"),
            ("math.ece@example.edu", AppUser.Role.FACULTY, "Prof. Devika Rao"),
            ("emft.ece@example.edu", AppUser.Role.FACULTY, "Dr. Farhan Ali"),
            ("comm.ece@example.edu", AppUser.Role.FACULTY, "Prof. Kavita Suresh"),
            ("edc.lab.a@example.edu", AppUser.Role.FACULTY, "Dr. Leela Thomas"),
            ("edc.lab.b@example.edu", AppUser.Role.FACULTY, "Dr. Raghav Bhat"),
            ("edc.lab.c@example.edu", AppUser.Role.FACULTY, "Prof. Sana Qureshi"),
            ("edc.lab.d@example.edu", AppUser.Role.FACULTY, "Dr. Neil D'Souza"),
            ("digital.lab.a@example.edu", AppUser.Role.FACULTY, "Prof. Mehul Shah"),
            ("digital.lab.b@example.edu", AppUser.Role.FACULTY, "Dr. Aparna Nair"),
            ("digital.lab.c@example.edu", AppUser.Role.FACULTY, "Dr. Gaurav Mishra"),
            ("digital.lab.d@example.edu", AppUser.Role.FACULTY, "Prof. Reema Joseph"),
        ]
        faculty_by_email = {}
        for email, role, name in faculty_specs:
            user, _ = AppUser.objects.update_or_create(email=email, defaults={"role": role})
            faculty, _ = Faculty.objects.update_or_create(
                user=user,
                defaults={"faculty_name": name, "department": ece},
            )
            faculty_by_email[email] = faculty

        ece.hod = faculty_by_email["hod.ece@example.edu"]
        ece.save(update_fields=["hod"])

        sections = []
        for section_name, strength in [("A", 64), ("B", 63), ("C", 62), ("D", 60)]:
            section, _ = Section.objects.update_or_create(
                department=ece,
                academic_term=term,
                year_number=2,
                section_name=section_name,
                defaults={"student_strength": strength},
            )
            sections.append(section)

        academic_block, _ = Building.objects.update_or_create(building_name="ECE Academic Tower")
        lab_complex, _ = Building.objects.update_or_create(building_name="Advanced Electronics Lab Complex")

        room_specs = [
            ("ECE-LH-201", Room.RoomType.CLASSROOM, 78, academic_block),
            ("ECE-LH-202", Room.RoomType.CLASSROOM, 78, academic_block),
            ("ECE-LH-203", Room.RoomType.CLASSROOM, 78, academic_block),
            ("ECE-LH-204", Room.RoomType.CLASSROOM, 78, academic_block),
            ("ECE-LH-301", Room.RoomType.CLASSROOM, 90, academic_block),
            ("ECE-SEMINAR-1", Room.RoomType.SEMINAR_HALL, 140, academic_block),
            ("ECE-EDC-LAB-1", Room.RoomType.HARDWARE_LAB, 72, lab_complex),
            ("ECE-EDC-LAB-2", Room.RoomType.HARDWARE_LAB, 72, lab_complex),
            ("ECE-DIGITAL-LAB-1", Room.RoomType.HARDWARE_LAB, 72, lab_complex),
            ("ECE-DIGITAL-LAB-2", Room.RoomType.HARDWARE_LAB, 72, lab_complex),
            ("ECE-VLSI-CAD-LAB", Room.RoomType.COMPUTER_LAB, 72, lab_complex),
            ("ECE-DSP-COMPUTING-LAB", Room.RoomType.COMPUTER_LAB, 72, lab_complex),
        ]
        for room_name, room_type, capacity, building in room_specs:
            Room.objects.update_or_create(
                building=building,
                room_name=room_name,
                defaults={
                    "room_type": room_type,
                    "capacity": capacity,
                    "department": ece,
                },
            )

        for day_name in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]:
            Day.objects.update_or_create(day_name=day_name)

        slot_specs = [
            (1, time(8, 30), time(9, 30), False),
            (2, time(9, 30), time(10, 30), False),
            (3, time(10, 45), time(11, 45), False),
            (4, time(11, 45), time(12, 45), False),
            (5, time(12, 45), time(13, 45), True),
            (6, time(13, 45), time(14, 45), False),
            (7, time(14, 45), time(15, 45), False),
            (8, time(16, 0), time(17, 0), False),
        ]
        for slot_number, start_time, end_time, is_break in slot_specs:
            Timeslot.objects.update_or_create(
                slot_number=slot_number,
                defaults={
                    "start_time": start_time,
                    "end_time": end_time,
                    "is_break": is_break,
                },
            )

        subject_specs = [
            ("EC201", "Signals and Systems", 4, Subject.SubjectType.THEORY, 3, 1, Subject.RequiredRoomType.CLASSROOM),
            ("EC202", "Analog Electronic Circuits", 4, Subject.SubjectType.THEORY, 3, 1, Subject.RequiredRoomType.CLASSROOM),
            ("EC203", "Digital Logic Design", 4, Subject.SubjectType.THEORY, 3, 1, Subject.RequiredRoomType.CLASSROOM),
            ("EC204", "Network Theory", 3, Subject.SubjectType.THEORY, 3, 1, Subject.RequiredRoomType.CLASSROOM),
            ("MA203", "Probability and Random Processes", 3, Subject.SubjectType.THEORY, 3, 1, Subject.RequiredRoomType.CLASSROOM),
            ("EC205", "Electromagnetic Field Theory", 3, Subject.SubjectType.THEORY, 2, 1, Subject.RequiredRoomType.CLASSROOM),
            ("EC251", "Electronic Devices and Circuits Lab", 2, Subject.SubjectType.LAB, 1, 3, Subject.RequiredRoomType.HARDWARE_LAB),
            ("EC252", "Digital Logic Design Lab", 2, Subject.SubjectType.LAB, 1, 3, Subject.RequiredRoomType.HARDWARE_LAB),
            ("EC281", "Engineering Design Seminar", 1, Subject.SubjectType.SEMINAR, 1, 1, Subject.RequiredRoomType.SEMINAR_HALL),
        ]
        subject_by_code = {}
        for code, title, credits, subject_type, sessions_per_week, session_duration, required_room_type in subject_specs:
            subject, _ = Subject.objects.update_or_create(
                subject_code=code,
                defaults={
                    "subject_title": title,
                    "credits": credits,
                    "department": ece,
                    "subject_type": subject_type,
                    "sessions_per_week": sessions_per_week,
                    "session_duration": session_duration,
                    "required_room_type": required_room_type,
                },
            )
            subject_by_code[code] = subject

        Timetable.objects.filter(section__in=sections, term=term).delete()
        SessionGroupMember.objects.filter(assignment__section__in=sections).delete()
        TeachingAssignment.objects.filter(section__in=sections).delete()

        theory_faculty = {
            "EC201": faculty_by_email["signals.ece@example.edu"],
            "EC202": faculty_by_email["analog.ece@example.edu"],
            "EC203": faculty_by_email["digital.ece@example.edu"],
            "EC204": faculty_by_email["network.ece@example.edu"],
            "MA203": faculty_by_email["math.ece@example.edu"],
            "EC205": faculty_by_email["emft.ece@example.edu"],
            "EC281": faculty_by_email["comm.ece@example.edu"],
        }
        edc_lab_faculty = {
            "A": faculty_by_email["edc.lab.a@example.edu"],
            "B": faculty_by_email["edc.lab.b@example.edu"],
            "C": faculty_by_email["edc.lab.c@example.edu"],
            "D": faculty_by_email["edc.lab.d@example.edu"],
        }
        digital_lab_faculty = {
            "A": faculty_by_email["digital.lab.a@example.edu"],
            "B": faculty_by_email["digital.lab.b@example.edu"],
            "C": faculty_by_email["digital.lab.c@example.edu"],
            "D": faculty_by_email["digital.lab.d@example.edu"],
        }

        assignments = []
        for section in sections:
            for subject in subject_by_code.values():
                if subject.subject_code == "EC251":
                    faculty = edc_lab_faculty[section.section_name]
                    priority = 1
                elif subject.subject_code == "EC252":
                    faculty = digital_lab_faculty[section.section_name]
                    priority = 1
                else:
                    faculty = theory_faculty[subject.subject_code]
                    priority = 2 if subject.subject_code in {"EC201", "EC202", "EC203"} else 3

                assignment, _ = TeachingAssignment.objects.update_or_create(
                    section=section,
                    subject=subject,
                    faculty=faculty,
                    defaults={
                        "required_room_type": subject.required_room_type,
                        "priority_level": priority,
                    },
                )
                assignments.append(assignment)

        groups = [
            ("ECE 2 Parallel EDC Labs", "EC251"),
            ("ECE 2 Parallel Digital Logic Labs", "EC252"),
        ]
        for group_name, subject_code in groups:
            group, _ = SessionGroup.objects.update_or_create(
                group_name=group_name,
                defaults={
                    "group_category": SessionGroup.GroupCategory.PARALLEL_LAB,
                    "same_time_required": True,
                    "same_building_required": True,
                    "preferred_building": lab_complex,
                    "priority_level": 1,
                },
            )
            for assignment in [item for item in assignments if item.subject_id == subject_code]:
                SessionGroupMember.objects.update_or_create(group=group, assignment=assignment)

        unavailable, _ = ConstraintType.objects.update_or_create(
            constraint_name="UNAVAILABLE",
            defaults={
                "constraint_category": "FACULTY",
                "priority_level": 1,
                "is_hard_constraint": True,
                "description": "Faculty cannot teach in this slot.",
            },
        )
        preferred, _ = ConstraintType.objects.update_or_create(
            constraint_name="PREFERRED",
            defaults={
                "constraint_category": "FACULTY",
                "priority_level": 3,
                "is_hard_constraint": False,
                "description": "Faculty prefers this slot.",
            },
        )
        avoid, _ = ConstraintType.objects.update_or_create(
            constraint_name="AVOID",
            defaults={
                "constraint_category": "FACULTY",
                "priority_level": 4,
                "is_hard_constraint": False,
                "description": "Faculty prefers to avoid this slot.",
            },
        )

        monday = Day.objects.get(day_name="Monday")
        friday = Day.objects.get(day_name="Friday")
        saturday = Day.objects.get(day_name="Saturday")
        slot_1 = Timeslot.objects.get(slot_number=1)
        slot_6 = Timeslot.objects.get(slot_number=6)
        slot_8 = Timeslot.objects.get(slot_number=8)

        constraints_to_seed = [
            (faculty_by_email["signals.ece@example.edu"], monday, slot_1, preferred, "Prefers early analytical lectures."),
            (faculty_by_email["analog.ece@example.edu"], friday, slot_8, avoid, "Avoid late Friday teaching load."),
            (faculty_by_email["emft.ece@example.edu"], saturday, slot_8, unavailable, "Research colloquium commitment."),
            (faculty_by_email["hod.ece@example.edu"], monday, slot_6, unavailable, "Department review meeting."),
        ]
        for faculty, day, slot, constraint_type, remarks in constraints_to_seed:
            FacultyConstraint.objects.update_or_create(
                faculty=faculty,
                day=day,
                slot=slot,
                constraint_type=constraint_type,
                defaults={"remarks": remarks},
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded ECE data for term_id={term.term_id} with {len(sections)} sections, "
                f"{len(subject_by_code)} subjects, and {len(assignments)} teaching assignments."
            )
        )
