# docker-compose.yml — описание

Файл поднимает 3 сервиса в одной сети `appnet`. Все переменные (образы, имена контейнеров, креды, порты) берутся из `.env`.
Сеть задана явно через `networks: appnet` (bridge) с именем `${NETWORK_NAME}`.

## services

### database
PostgreSQL.
- образ: `${POSTGRES_IMAGE}`
- имя контейнера: `${DB_CONTAINER_NAME}`
- env из `.env` (`env_file`)
- volume: `./db_data:/var/lib/postgresql/data` (данные БД на хосте)
- healthcheck: `pg_isready ...` (готовность Postgres)
- restart: `unless-stopped`

### init-database
Одноразовая инициализация схемы БД.
- образ: `${INIT_IMAGE}` (например Ubuntu + psql)
- имя контейнера: `${INIT_CONTAINER_NAME}`
- зависит от `database` (ждёт `service_healthy`)
- volume: `./init-db.sh:/init-db.sh:ro` (скрипт, только чтение)
- command: запускает `/init-db.sh`
- restart: `no` (должен завершиться после выполнения)

### app
Приложение.
- build из `./app/Dockerfile`
- имя образа: `${APP_IMAGE_NAME}`
- имя контейнера: `${APP_CONTAINER_NAME}`
- env из `.env` (`env_file`)
- depends_on:
  - `database` (healthy)
  - `init-database` (успешно завершился)
- ports: `"${APP_PORT}:5000"`
- restart: `unless-stopped`

## networks
`appnet` — общая сеть для всех сервисов (явно задана).

---

# Ответы на вопросы

## Можно ли ограничивать ресурсы (память/CPU) в docker-compose.yml?

Да, но зависит от режима:

- Для обычного `docker compose up` обычно используют `cpus` и `mem_limit`.
- `deploy.resources` работает только в Swarm и в обычном `docker compose up` игнорируется.

Пример (обычный compose):
```yaml
services:
  app:
    cpus: "1.0"
    mem_limit: "512m"
```

Пример (Swarm):
```yaml
services:
  app:
    deploy:
      resources:
        limits:
          cpus: "1.0"
          memory: 512M
```

## Как запустить только один сервис, не запуская остальные?

Запуск конкретного сервиса:
```bash
docker compose up -d app
```

Без автозапуска зависимостей:
```bash
docker compose up -d --no-deps app
```

Одноразово запустить init:
```bash
docker compose run --rm init-database
```