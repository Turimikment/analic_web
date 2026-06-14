# Kafka UI для Aiven Kafka

В проект добавлена отдельная конфигурация для Kafka UI на базе `provectuslabs/kafka-ui`.

## Что важно

Основной тренажёр использует `KAFKA_REST_URL` — это Aiven Kafka REST.

Kafka UI подключается не к REST, а к Kafka broker protocol. Поэтому ему нужен отдельный адрес:

```env
KAFKA_BOOTSTRAP_SERVERS=kafka-tra9n-lalalazaic.g.aivencloud.com:27243
```

Порт broker обычно отличается от REST-порта. REST у тебя был `27241`, а broker в Aiven Overview обычно выглядит как `27243`.

## Локальный запуск

Создай `.env` рядом с `docker-compose.kafka-ui.yml`:

```env
KAFKA_BOOTSTRAP_SERVERS=host-from-aiven:port
KAFKA_USERNAME=avnadmin
KAFKA_PASSWORD=NEW_PASSWORD
```

Запусти:

```bash
docker compose -f docker-compose.kafka-ui.yml --env-file .env up -d
```

Открой:

```text
http://localhost:8080
```

## Render

Создай отдельный Web Service из этого же репозитория и укажи Dockerfile:

```text
Dockerfile.kafka-ui
```

Env-переменные:

```env
DYNAMIC_CONFIG_ENABLED=true
KAFKA_CLUSTERS_0_NAME=Aiven Kafka
KAFKA_CLUSTERS_0_BOOTSTRAPSERVERS=host-from-aiven:port
KAFKA_CLUSTERS_0_PROPERTIES_SECURITY_PROTOCOL=SASL_SSL
KAFKA_CLUSTERS_0_PROPERTIES_SASL_MECHANISM=PLAIN
KAFKA_CLUSTERS_0_PROPERTIES_SASL_JAAS_CONFIG=org.apache.kafka.common.security.plain.PlainLoginModule required username="avnadmin" password="NEW_PASSWORD";
KAFKA_CLUSTERS_0_READONLY=false
```

После деплоя Kafka UI можно будет открыть по URL Render-сервиса.

## Ссылка из тренажёра

Если хочешь, чтобы кнопка Kafka UI в тренажёре открывала внешний UI, добавь в основной Flask-сервис:

```env
KAFKA_UI_URL=https://your-kafka-ui-service.onrender.com
```
