CREATE DATABASE smart_sched;

CREATE USER smart_sched_user WITH PASSWORD 'smart_sched_password';

ALTER ROLE smart_sched_user SET client_encoding TO 'utf8';
ALTER ROLE smart_sched_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE smart_sched_user SET timezone TO 'Asia/Kolkata';

GRANT ALL PRIVILEGES ON DATABASE smart_sched TO smart_sched_user;

\connect smart_sched

GRANT ALL ON SCHEMA public TO smart_sched_user;
ALTER SCHEMA public OWNER TO smart_sched_user;
