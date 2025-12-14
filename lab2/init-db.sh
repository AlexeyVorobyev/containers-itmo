echo "Installing psql client..."
apt-get update
apt-get install -y --no-install-recommends postgresql-client ca-certificates
rm -rf /var/lib/apt/lists/*

echo "Waiting for Postgres..."
timeout 60 bash -c '
until pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$POSTGRES_USER" -d "$POSTGRES_DB"; do
    echo "Database not ready yet, waiting..."
    sleep 2
done
' || (echo "Timeout waiting for database" && exit 1)

echo "Database is ready"
echo "Running schema init..."

PGPASSWORD="$POSTGRES_PASSWORD" psql \
-h "$DB_HOST" -p "$DB_PORT" -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
-v ON_ERROR_STOP=1 \
-c "CREATE SCHEMA IF NOT EXISTS public;" \
-c "CREATE TABLE IF NOT EXISTS public.announcements ( \
        id BIGSERIAL PRIMARY KEY, \
        title VARCHAR(140) NOT NULL, \
        text  TEXT NOT NULL, \
        created_at TIMESTAMPTZ NOT NULL DEFAULT now() \
    );" \
-c "CREATE INDEX IF NOT EXISTS idx_announcements_created_at \
        ON public.announcements (created_at DESC);"

echo "Init completed successfully"