#!/bin/bash
# Creates the Postiz role + database on FIRST init of the postgres volume.
# (docker-entrypoint-initdb.d scripts run once, before the app ever boots.)
# Only needed when the optional postiz profile is enabled.
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
    DO \$\$
    BEGIN
        IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'postiz') THEN
            CREATE ROLE postiz WITH LOGIN PASSWORD '${POSTIZ_POSTGRES_PASSWORD:-postiz_change_me}';
        END IF;
    END
    \$\$;
    SELECT 'CREATE DATABASE postiz OWNER postiz'
    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'postiz')\gexec
EOSQL
