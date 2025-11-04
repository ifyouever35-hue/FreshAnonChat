param(
    [Parameter(Mandatory=$true)]
    [string]$Password
)
$container = "freshanon_pg"
docker ps --format "{{.Names}}" | findstr /I "^$container$" > $null
if ($LASTEXITCODE -ne 0) {
    Write-Error "Контейнер '$container' не запущен."
    exit 1
}
$escaped = $Password.Replace("'", "''")
docker exec -i $container psql -U postgres -d postgres -v ON_ERROR_STOP=1 -c "DO $$BEGIN
IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'neverland') THEN
  CREATE ROLE neverland LOGIN PASSWORD '$escaped';
ELSE
  ALTER ROLE neverland WITH LOGIN PASSWORD '$escaped';
END IF;
END$$;"
docker exec -i $container psql -U postgres -d postgres -v ON_ERROR_STOP=1 -c "SELECT 1 FROM pg_database WHERE datname='fresh_anon_chat';" | findstr "1" > $null
if ($LASTEXITCODE -ne 0) {
    docker exec -i $container psql -U postgres -d postgres -v ON_ERROR_STOP=1 -c "CREATE DATABASE fresh_anon_chat OWNER neverland;"
}
docker exec -i $container psql -U postgres -d postgres -v ON_ERROR_STOP=1 -c "ALTER DATABASE fresh_anon_chat OWNER TO neverland; GRANT ALL PRIVILEGES ON DATABASE fresh_anon_chat TO neverland;"
Write-Host "Готово. Обновите ваш .env: PGPASSWORD=$Password"
