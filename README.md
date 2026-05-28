# Smart Academic Timetable Scheduler Backend

Django + PostgreSQL backend for generating conflict-free academic timetables. The project models departments, sections, faculty, subjects, rooms, constraints, teaching assignments, synchronized lab groups, and generated timetable entries.

The current scheduler is a V1 heuristic engine: deterministic, constraint-driven, occupancy-map based, and designed for semester-wise weekly timetable generation.

## Features

- Department, faculty, student, subject, room, day, and timeslot data models
- Faculty availability/preference constraints
- Teaching assignments expanded into weekly schedulable sessions
- Parallel lab/common group synchronization
- Room allocation with capacity and room-type validation
- Hard conflict checks for faculty, room, section, break slots, and unavailable slots
- Soft scoring for preferred rooms, preferred slots, balanced day load, and avoid slots
- Bounded backtracking instead of exhaustive brute force
- JWT-based authentication endpoints for register, login, refresh, and current user lookup
- Terminal commands for seeding, generating, and inspecting timetables

## Tech Stack

- Python 3.11+
- Django 5.2
- PostgreSQL
- `psycopg`
- `python-dotenv`

## Project Structure

```text
backend_django/
|-- accounts/          # App users, students, faculty
|-- academics/         # Departments, terms, sections, subjects
|-- constraints/       # Constraint types and faculty constraints
|-- infrastructure/    # Buildings, rooms, days, timeslots
|-- timetables/        # Assignments, groups, timetables, entries, commands
|-- scheduler/         # Pure scheduler engine package
|-- config/            # Django project settings
|-- sql/               # Database setup SQL
|-- manage.py
|-- requirements.txt
|-- docker-compose.yml
|-- .env.example
`-- README.md
```

## Scheduler Architecture

```text
TeachingAssignment
    -> expanded into SchedulableSession objects
    -> grouped into synchronized SchedulingUnit objects when needed
    -> prioritized hardest-first
    -> candidate day/slot/room allocations generated
    -> hard constraints validated
    -> soft score calculated
    -> best candidate committed into occupancy maps
    -> Timetable and TimetableEntry rows persisted
```

Important scheduler files:

```text
scheduler/engine.py        Orchestrates generation and persistence
scheduler/generator.py     Loads ORM data and expands assignments
scheduler/prioritizer.py   Sorts hardest sessions first
scheduler/allocator.py     Candidate search and bounded backtracking
scheduler/validator.py     Hard constraint validation
scheduler/scorer.py        Soft preference scoring
scheduler/occupancy.py     Faculty/room/section busy maps
scheduler/constraints.py   Faculty constraint indexing
scheduler/models.py        Internal scheduler dataclasses
```

## Setup

Create and activate a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Create your local environment file:

```powershell
Copy-Item .env.example .env
```

## PostgreSQL Setup

If PostgreSQL is installed locally, create the database and application user:

```powershell
psql -U postgres -h localhost -p 5432 -f sql/create_database.sql
```

Default local credentials:

```text
database: smart_sched
user: smart_sched_user
password: smart_sched_password
host: localhost
port: 5432
```

Alternatively, if Docker is installed:

```powershell
docker compose up -d postgres
```

Apply migrations:

```powershell
python manage.py migrate
```

Optional admin user:

```powershell
python manage.py createsuperuser
```

Run the development server:

```powershell
python manage.py runserver
```

## Authentication Service

The backend now uses `accounts.AppUser` as the Django auth model and exposes JWT auth endpoints under `/api/auth/`.

Available endpoints:

- `POST /api/auth/register/`
- `POST /api/auth/login/`
- `POST /api/auth/refresh/`
- `GET /api/auth/me/`

Example register payload:

```json
{
  "email": "admin@example.com",
  "password": "StrongPass123",
  "role": "ADMIN"
}
```

Example login payload:

```json
{
  "email": "admin@example.com",
  "password": "StrongPass123"
}
```

`/api/auth/login/` returns `access`, `refresh`, and the authenticated `user`.

## Seed Data

Seed a realistic ECE department dataset:

```powershell
python manage.py seed_ece_data
```

This creates:

- ECE department
- 4 sections
- faculty and HOD users
- classrooms, seminar hall, hardware labs, and computer labs
- subjects and weekly session requirements
- teaching assignments
- synchronized parallel lab groups
- faculty hard/soft constraints

There is also an older CSE demo seed:

```powershell
python manage.py seed_demo_data
```

## Generate Timetables

Dry run without saving:

```powershell
python manage.py generate_timetable --term-id 2 --section-id 5 --section-id 6 --section-id 7 --section-id 8 --dry-run
```

Generate and persist:

```powershell
python manage.py generate_timetable --term-id 2 --section-id 5 --section-id 6 --section-id 7 --section-id 8
```

Generate while treating an existing timetable as locked occupancy:

```powershell
python manage.py generate_timetable --term-id 2 --lock-timetable-id 4
```

Print the latest timetable for a section:

```powershell
python manage.py show_timetable --term-id 2 --section-id 5
```

## Current Validation Baseline

The ECE dataset has been generated and checked successfully:

```text
Sections generated: 4
Timetable entries: 80
Expanded-duration conflicts: 0
Average generation time: ~0.26s
```

Checked conflict types:

- Section overlaps
- Faculty overlaps
- Room overlaps
- Multi-slot lab duration overlaps
- Break-slot allocation
- Room type mismatch
- Faculty unavailable slots
- Synchronized parallel lab timing

## Development Notes

- CRUD APIs are intentionally not implemented yet.
- Django admin and management commands are enough for current scheduler validation.
- The scheduler is independent from views and serializers, so API integration can be added later without rewriting generation logic.
- `__pycache__`, `.pyc`, `.env`, virtual environments, and local database files are ignored by `.gitignore`.

## Recommended Next Steps

- Add Django REST Framework CRUD APIs
- Add frontend screens for master data management
- Add timetable review and export UI
- Add unit tests for allocator, validator, grouping, and occupancy
- Improve failure diagnostics for impossible schedules
- Refine soft scoring after testing with real institutional data
