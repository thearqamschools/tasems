#!/bin/sh
# Runs once, when the database volume is first created.
# Creates the application role as an ORDINARY role (not superuser, no BYPASSRLS),
# so PostgreSQL row-level security protects branch data.
set -e
psql -v ON_ERROR_STOP=1 --username postgres <<SQL
CREATE ROLE tasems_app LOGIN PASSWORD '${TASEMS_DB_PASSWORD}' NOSUPERUSER NOBYPASSRLS NOCREATEROLE NOCREATEDB;
CREATE DATABASE tasems OWNER tasems_app;
SQL
