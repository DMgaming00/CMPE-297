#!/bin/sh
# Creates the separate bug-tracker database inside the local Postgres container.
set -e
psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "CREATE DATABASE bugs"
psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d bugs -f /seed/bug_tracker_schema.sql
psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d bugs -f /seed/bug_tracker_seed.sql
