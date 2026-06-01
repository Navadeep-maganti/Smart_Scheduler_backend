from datetime import date, time

from django.core.management.base import BaseCommand

from academics.models import AcademicTerm, Department, Section, Subject
from accounts.models import AppUser, Faculty
from constraints.models import ConstraintType, FacultyConstraint
from infrastructure.models import Building, Day, Room, Timeslot
from timetables.models import SessionGroup, SessionGroupMember, TeachingAssignment, Timetable


class Command(BaseCommand):
    help = "Seed a larger synthetic dataset for scheduler performance testing."

    def add_arguments(self, parser):
        parser.add_argument("--departments", type=int, default=3)
        parser.add_argument("--sections-per-department", type=int, default=4)

    def handle(self, *args, **options):
        department_count = options["departments"]
        sections_per_department = options["sections_per_department"]

        term, _ = AcademicTerm.objects.update_or_create(
            academic_year="2026-2027",
            term_type=AcademicTerm.TermType.EVEN,
            defaults={
                "start_date": date(2027, 1, 5),
                "end_date": date(2027, 5, 20),
                "is_active": False,
            },
        )
        self.stdout.write(f"Using performance term_id={term.term_id}")

        self.seed_calendar()
        self.stdout.write("Seeded calendar.")

        unavailable, preferred, avoid = self.seed_constraint_types()
        self.stdout.write("Seeded constraint types.")
        departments = self.seed_departments(department_count)
        self.stdout.write(f"Seeded {len(departments)} departments.")

        total_sections = 0
        total_subjects = 0
        total_assignments = 0

        for dept_index, department in enumerate(departments, start=1):
            self.stdout.write(f"Seeding {department.department_code}...")
            sections = self.seed_sections(term, department, sections_per_department)
            self.stdout.write(f"  sections={len(sections)}")
            faculty = self.seed_faculty(department, dept_index, sections_per_department)
            self.stdout.write(f"  faculty={len(faculty)}")
            self.seed_rooms(department, dept_index, sections_per_department)
            self.stdout.write("  rooms seeded")
            subjects = self.seed_subjects(department, dept_index)
            self.stdout.write(f"  subjects={len(subjects)}")

            Timetable.objects.filter(section__in=sections, term=term).delete()
            SessionGroupMember.objects.filter(assignment__section__in=sections).delete()
            TeachingAssignment.objects.filter(section__in=sections).delete()
            self.stdout.write("  old generated data cleared")

            assignments = self.seed_assignments(sections, subjects, faculty)
            self.stdout.write(f"  assignments={len(assignments)}")
            self.seed_parallel_lab_groups(department, dept_index, assignments)
            self.stdout.write("  lab groups seeded")
            self.seed_faculty_constraints(faculty, unavailable, preferred, avoid)
            self.stdout.write("  constraints seeded")

            total_sections += len(sections)
            total_subjects += len(subjects)
            total_assignments += len(assignments)

        self.stdout.write(
            self.style.SUCCESS(
                "Seeded performance dataset "
                f"term_id={term.term_id}, departments={len(departments)}, "
                f"sections={total_sections}, subjects={total_subjects}, "
                f"assignments={total_assignments}."
            )
        )

    def seed_calendar(self):
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

    def seed_constraint_types(self):
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
        return unavailable, preferred, avoid

    def seed_departments(self, department_count):
        department_templates = [
            ("PERF-CSE", "Performance Computer Science"),
            ("PERF-ECE", "Performance Electronics and Communication"),
            ("PERF-MECH", "Performance Mechanical Engineering"),
            ("PERF-CIVIL", "Performance Civil Engineering"),
            ("PERF-EEE", "Performance Electrical and Electronics"),
        ]
        departments = []
        for code, name in department_templates[:department_count]:
            department, _ = Department.objects.update_or_create(
                department_code=code,
                defaults={"department_name": name},
            )
            departments.append(department)
        return departments

    def seed_sections(self, term, department, sections_per_department):
        sections = []
        for index in range(sections_per_department):
            section_name = chr(ord("A") + index)
            section, _ = Section.objects.update_or_create(
                department=department,
                academic_term=term,
                year_number=2,
                section_name=section_name,
                defaults={"student_strength": 58 + (index % 4) * 3},
            )
            sections.append(section)
        return sections

    def seed_faculty(self, department, dept_index, sections_per_department):
        faculty = {}
        faculty_specs = [
            ("hod", AppUser.Role.HOD, "Head of Department"),
            ("core1", AppUser.Role.FACULTY, "Core Systems Faculty"),
            ("core2", AppUser.Role.FACULTY, "Applied Circuits Faculty"),
            ("core3", AppUser.Role.FACULTY, "Mathematics Faculty"),
            ("core4", AppUser.Role.FACULTY, "Design Faculty"),
            ("core5", AppUser.Role.FACULTY, "Signals Faculty"),
            ("seminar", AppUser.Role.FACULTY, "Seminar Coordinator"),
        ]
        for key, role, display_name in faculty_specs:
            email = f"{department.department_code.lower()}.{key}@perf.example.edu"
            user, _ = AppUser.objects.update_or_create(email=email, defaults={"role": role})
            member, _ = Faculty.objects.update_or_create(
                user=user,
                defaults={
                    "faculty_name": f"{display_name} {dept_index}",
                    "department": department,
                },
            )
            faculty[key] = member

        for lab_index in range(1, sections_per_department + 1):
            for lab_prefix in ["labA", "labB"]:
                key = f"{lab_prefix}{lab_index}"
                email = f"{department.department_code.lower()}.{key}@perf.example.edu"
                user, _ = AppUser.objects.update_or_create(email=email, defaults={"role": AppUser.Role.FACULTY})
                member, _ = Faculty.objects.update_or_create(
                    user=user,
                    defaults={
                        "faculty_name": f"{department.department_code} {lab_prefix.upper()} Faculty {lab_index}",
                        "department": department,
                    },
                )
                faculty[key] = member

        department.hod = faculty["hod"]
        department.save(update_fields=["hod"])
        return faculty

    def seed_rooms(self, department, dept_index, sections_per_department):
        academic_building, _ = Building.objects.update_or_create(
            building_name=f"{department.department_code} Academic Block"
        )
        lab_building, _ = Building.objects.update_or_create(
            building_name=f"{department.department_code} Lab Complex"
        )

        for room_index in range(1, sections_per_department + 3):
            Room.objects.update_or_create(
                building=academic_building,
                room_name=f"{department.department_code}-LH-{200 + room_index}",
                defaults={
                    "room_type": Room.RoomType.CLASSROOM,
                    "capacity": 80,
                    "department": department,
                },
            )

        Room.objects.update_or_create(
            building=academic_building,
            room_name=f"{department.department_code}-SEMINAR",
            defaults={
                "room_type": Room.RoomType.SEMINAR_HALL,
                "capacity": 140,
                "department": department,
            },
        )

        for lab_index in range(1, sections_per_department + 1):
            Room.objects.update_or_create(
                building=lab_building,
                room_name=f"{department.department_code}-HARDWARE-LAB-{lab_index}",
                defaults={
                    "room_type": Room.RoomType.HARDWARE_LAB,
                    "capacity": 75,
                    "department": department,
                },
            )
            Room.objects.update_or_create(
                building=lab_building,
                room_name=f"{department.department_code}-COMPUTE-LAB-{lab_index}",
                defaults={
                    "room_type": Room.RoomType.COMPUTER_LAB,
                    "capacity": 75,
                    "department": department,
                },
            )

    def seed_subjects(self, department, dept_index):
        specs = [
            ("T1", "Core Theory I", 4, Subject.SubjectType.THEORY, 3, 1, Subject.RequiredRoomType.CLASSROOM),
            ("T2", "Core Theory II", 4, Subject.SubjectType.THEORY, 3, 1, Subject.RequiredRoomType.CLASSROOM),
            ("T3", "Mathematical Methods", 3, Subject.SubjectType.THEORY, 3, 1, Subject.RequiredRoomType.CLASSROOM),
            ("T4", "Systems and Design", 3, Subject.SubjectType.THEORY, 3, 1, Subject.RequiredRoomType.CLASSROOM),
            ("T5", "Applied Engineering Analysis", 3, Subject.SubjectType.THEORY, 2, 1, Subject.RequiredRoomType.CLASSROOM),
            ("L1", "Integrated Hardware Lab", 2, Subject.SubjectType.LAB, 1, 3, Subject.RequiredRoomType.HARDWARE_LAB),
            ("L2", "Computational Methods Lab", 2, Subject.SubjectType.LAB, 1, 3, Subject.RequiredRoomType.COMPUTER_LAB),
            ("S1", "Research Seminar", 1, Subject.SubjectType.SEMINAR, 1, 1, Subject.RequiredRoomType.SEMINAR_HALL),
        ]
        subjects = {}
        for suffix, title, credits, subject_type, sessions_per_week, session_duration, required_room_type in specs:
            code = f"{department.department_code.replace('-', '')}{suffix}"
            subject, _ = Subject.objects.update_or_create(
                subject_code=code,
                defaults={
                    "subject_title": f"{department.department_code} {title}",
                    "credits": credits,
                    "department": department,
                    "subject_type": subject_type,
                    "sessions_per_week": sessions_per_week,
                    "session_duration": session_duration,
                    "required_room_type": required_room_type,
                },
            )
            subjects[suffix] = subject
        return subjects

    def seed_assignments(self, sections, subjects, faculty):
        theory_faculty = {
            "T1": faculty["core1"],
            "T2": faculty["core2"],
            "T3": faculty["core3"],
            "T4": faculty["core4"],
            "T5": faculty["core5"],
            "S1": faculty["seminar"],
        }
        assignments = []
        for section_index, section in enumerate(sections, start=1):
            for suffix, subject in subjects.items():
                if suffix == "L1":
                    assigned_faculty = faculty[f"labA{section_index}"]
                    priority = 1
                elif suffix == "L2":
                    assigned_faculty = faculty[f"labB{section_index}"]
                    priority = 1
                else:
                    assigned_faculty = theory_faculty[suffix]
                    priority = 2 if suffix in {"T1", "T2"} else 3

                assignment, _ = TeachingAssignment.objects.update_or_create(
                    section=section,
                    subject=subject,
                    faculty=assigned_faculty,
                    defaults={
                        "required_room_type": subject.required_room_type,
                        "priority_level": priority,
                    },
                )
                assignments.append(assignment)
        return assignments

    def seed_parallel_lab_groups(self, department, dept_index, assignments):
        lab_building = Building.objects.get(building_name=f"{department.department_code} Lab Complex")
        for subject_suffix, label in [("L1", "Hardware"), ("L2", "Computational")]:
            group, _ = SessionGroup.objects.update_or_create(
                group_name=f"{department.department_code} Performance {label} Parallel Lab",
                defaults={
                    "group_category": SessionGroup.GroupCategory.PARALLEL_LAB,
                    "same_time_required": True,
                    "same_building_required": True,
                    "preferred_building": lab_building,
                    "priority_level": 1,
                },
            )
            for assignment in assignments:
                if assignment.subject_id.endswith(subject_suffix):
                    SessionGroupMember.objects.update_or_create(group=group, assignment=assignment)

    def seed_faculty_constraints(self, faculty, unavailable, preferred, avoid):
        monday = Day.objects.get(day_name="Monday")
        friday = Day.objects.get(day_name="Friday")
        saturday = Day.objects.get(day_name="Saturday")
        slot_1 = Timeslot.objects.get(slot_number=1)
        slot_7 = Timeslot.objects.get(slot_number=7)
        slot_8 = Timeslot.objects.get(slot_number=8)

        rows = [
            (faculty["core1"], monday, slot_1, preferred, "Prefers early week teaching."),
            (faculty["core2"], friday, slot_8, avoid, "Avoids late Friday slots."),
            (faculty["core5"], saturday, slot_8, unavailable, "Department research meeting."),
            (faculty["hod"], monday, slot_7, unavailable, "Administrative review block."),
        ]
        for member, day, slot, constraint_type, remarks in rows:
            FacultyConstraint.objects.update_or_create(
                faculty=member,
                day=day,
                slot=slot,
                constraint_type=constraint_type,
                defaults={"remarks": remarks},
            )
