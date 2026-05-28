from datetime import date, time

from django.core.management.base import BaseCommand

from academics.models import AcademicTerm, Department, Section, Subject
from accounts.models import AppUser, Faculty
from constraints.models import ConstraintType, FacultyConstraint
from infrastructure.models import Building, Day, Room, Timeslot
from timetables.models import SessionGroup, SessionGroupMember, TeachingAssignment, Timetable


class Command(BaseCommand):
    help = "Seed realistic demo data for scheduler engine validation."

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

        cse, _ = Department.objects.update_or_create(
            department_code="CSE",
            defaults={"department_name": "Computer Science and Engineering"},
        )

        faculty_specs = [
            ("hod.cse@example.com", AppUser.Role.HOD, "Dr. Meera Rao"),
            ("dbms.faculty@example.com", AppUser.Role.FACULTY, "Prof. Arjun Iyer"),
            ("dbms.lab1@example.com", AppUser.Role.FACULTY, "Prof. Sahana Pillai"),
            ("dbms.lab2@example.com", AppUser.Role.FACULTY, "Prof. Vikram Das"),
            ("dbms.lab3@example.com", AppUser.Role.FACULTY, "Prof. Farah Khan"),
            ("os.faculty@example.com", AppUser.Role.FACULTY, "Prof. Kavya Nair"),
            ("math.faculty@example.com", AppUser.Role.FACULTY, "Dr. Rohan Sen"),
            ("cn.faculty@example.com", AppUser.Role.FACULTY, "Prof. Neha Shah"),
        ]
        faculty_by_email = {}
        for email, role, name in faculty_specs:
            user, _ = AppUser.objects.update_or_create(email=email, defaults={"role": role})
            faculty, _ = Faculty.objects.update_or_create(
                user=user,
                defaults={"faculty_name": name, "department": cse},
            )
            faculty_by_email[email] = faculty

        cse.hod = faculty_by_email["hod.cse@example.com"]
        cse.save(update_fields=["hod"])

        sections = []
        for section_name in ["A", "B", "C"]:
            section, _ = Section.objects.update_or_create(
                department=cse,
                academic_term=term,
                year_number=2,
                section_name=section_name,
                defaults={"student_strength": 60},
            )
            sections.append(section)

        building, _ = Building.objects.update_or_create(building_name="Main Academic Block")
        lab_building, _ = Building.objects.update_or_create(building_name="Computing Block")

        for room_name, room_type, capacity, room_building in [
            ("MAB-201", Room.RoomType.CLASSROOM, 75, building),
            ("MAB-202", Room.RoomType.CLASSROOM, 75, building),
            ("MAB-203", Room.RoomType.CLASSROOM, 75, building),
            ("CB-LAB-1", Room.RoomType.COMPUTER_LAB, 70, lab_building),
            ("CB-LAB-2", Room.RoomType.COMPUTER_LAB, 70, lab_building),
            ("CB-LAB-3", Room.RoomType.COMPUTER_LAB, 70, lab_building),
            ("MAB-SEMINAR", Room.RoomType.SEMINAR_HALL, 120, building),
        ]:
            Room.objects.update_or_create(
                building=room_building,
                room_name=room_name,
                defaults={
                    "room_type": room_type,
                    "capacity": capacity,
                    "department": cse,
                },
            )

        for day_name in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]:
            Day.objects.update_or_create(day_name=day_name)

        slot_specs = [
            (1, time(9, 0), time(10, 0), False),
            (2, time(10, 0), time(11, 0), False),
            (3, time(11, 0), time(12, 0), False),
            (4, time(12, 0), time(13, 0), True),
            (5, time(13, 0), time(14, 0), False),
            (6, time(14, 0), time(15, 0), False),
            (7, time(15, 0), time(16, 0), False),
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

        subjects = [
            ("CS201", "Database Management Systems", 4, Subject.SubjectType.THEORY, 3, 1, Subject.RequiredRoomType.CLASSROOM),
            ("CS251", "Database Management Systems Lab", 2, Subject.SubjectType.LAB, 1, 3, Subject.RequiredRoomType.COMPUTER_LAB),
            ("CS202", "Operating Systems", 4, Subject.SubjectType.THEORY, 3, 1, Subject.RequiredRoomType.CLASSROOM),
            ("MA201", "Discrete Mathematics", 3, Subject.SubjectType.THEORY, 3, 1, Subject.RequiredRoomType.CLASSROOM),
            ("CS203", "Computer Networks", 3, Subject.SubjectType.THEORY, 2, 1, Subject.RequiredRoomType.CLASSROOM),
        ]
        subject_by_code = {}
        for code, title, credits, subject_type, sessions_per_week, session_duration, required_room_type in subjects:
            subject, _ = Subject.objects.update_or_create(
                subject_code=code,
                defaults={
                    "subject_title": title,
                    "credits": credits,
                    "department": cse,
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

        faculty_for_subject = {
            "CS201": faculty_by_email["dbms.faculty@example.com"],
            "CS202": faculty_by_email["os.faculty@example.com"],
            "MA201": faculty_by_email["math.faculty@example.com"],
            "CS203": faculty_by_email["cn.faculty@example.com"],
        }
        lab_faculty_by_section = {
            "A": faculty_by_email["dbms.lab1@example.com"],
            "B": faculty_by_email["dbms.lab2@example.com"],
            "C": faculty_by_email["dbms.lab3@example.com"],
        }
        assignments = []
        for section in sections:
            for subject in subject_by_code.values():
                faculty = (
                    lab_faculty_by_section[section.section_name]
                    if subject.subject_code == "CS251"
                    else faculty_for_subject[subject.subject_code]
                )
                assignment, _ = TeachingAssignment.objects.update_or_create(
                    section=section,
                    subject=subject,
                    faculty=faculty,
                    defaults={
                        "required_room_type": subject.required_room_type,
                        "priority_level": 1 if subject.subject_type == Subject.SubjectType.LAB else 3,
                    },
                )
                assignments.append(assignment)

        group, _ = SessionGroup.objects.update_or_create(
            group_name="CSE 2 Parallel DBMS Labs",
            defaults={
                "group_category": SessionGroup.GroupCategory.PARALLEL_LAB,
                "same_time_required": True,
                "same_building_required": True,
                "preferred_building": lab_building,
                "priority_level": 1,
            },
        )
        dbms_lab_assignments = [
            assignment
            for assignment in assignments
            if assignment.subject_id == "CS251"
        ]
        for assignment in dbms_lab_assignments:
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

        monday = Day.objects.get(day_name="Monday")
        saturday = Day.objects.get(day_name="Saturday")
        first_slot = Timeslot.objects.get(slot_number=1)
        last_slot = Timeslot.objects.get(slot_number=7)
        FacultyConstraint.objects.update_or_create(
            faculty=faculty_by_email["dbms.faculty@example.com"],
            day=saturday,
            slot=last_slot,
            constraint_type=unavailable,
            defaults={"remarks": "Avoid late Saturday lab scheduling."},
        )
        FacultyConstraint.objects.update_or_create(
            faculty=faculty_by_email["math.faculty@example.com"],
            day=monday,
            slot=first_slot,
            constraint_type=preferred,
            defaults={"remarks": "Prefers first slot."},
        )

        self.stdout.write(self.style.SUCCESS(f"Seeded demo data for term_id={term.term_id}."))
