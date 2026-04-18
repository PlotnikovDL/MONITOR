# Performance Monitor Lite

Portable-сборка [Erik Darling Performance Monitor](https://github.com/erikdarlingdata/PerformanceMonitor) Lite edition — мониторинг SQL Server для базы 1С без установки на сервер. Встроенный MCP-сервер позволяет Claude Code анализировать метрики напрямую.

Версия: **2.7.0**

## Что делает

- Читает DMV целевого MSSQL (локально или удалённо), складывает в локальный DuckDB + Parquet
- Wait stats, blocking, deadlocks, top queries, CPU/memory, TempDB, file I/O, execution plans
- Алерты (tray, email, webhooks) на блокировки, дедлоки, poison waits, long queries, high CPU
- MCP-сервер (opt-in) для AI-анализа собранных данных

## Первый запуск

### 1. Права на MSSQL

Нужен логин с минимальными правами на целевом сервере:

```sql
GRANT VIEW SERVER STATE TO [<логин>];
GRANT VIEW ANY DEFINITION TO [<логин>];
GRANT VIEW DATABASE STATE TO [<логин>]; -- для Query Store
```

### 2. Запуск приложения

Запустить `PerformanceMonitorLite.exe` из этой папки. Ничего не ставится в систему (portable).

### 3. Добавить сервер (Add SQL Server)

- **Server Name**: `имя_хоста` или `имя_хоста\ИНСТАНС` если named instance
- **Authentication**: SQL Auth или Windows Auth
- **Encryption**: `Mandatory` + отметить ✓ **Trust server certificate** (если сертификат самоподписанный)
- **Database**: оставить пустым (мониторим весь инстанс)
- Test Connection → Save

### 4. Включить MCP-сервер

Settings → секция **MCP Server (LLM Tool Access)**:

- ✓ Enable MCP server
- Port: `5151` (Auto)
- Save → **перезапустить приложение** (MCP требует рестарт)

После рестарта Status должен стать `Running`.

## Интеграция с Claude Code

В корне репо уже есть запись в [../../.mcp.json](../../.mcp.json):

```json
"sql-monitor": {
  "type": "http",
  "url": "http://localhost:5151/"
}
```

При открытии проекта Claude Code предложит одобрить MCP — нажать **Allow**. Проверить: `/mcp` → в списке `sql-monitor` со статусом `connected`.

Условие работы: `PerformanceMonitorLite.exe` должен быть запущен на той же машине с включённым MCP.

## Типичные запросы к Claude через MCP

> Покажи топ-5 wait stats за последние 15 минут

> Есть ли блокировки или дедлоки за последний час?

> Топ-10 запросов по CPU за сегодня, с планами

> Проанализируй memory grants и poison waits

Всего доступен **51 tool** в Lite edition (discovery, health, alerts, waits, queries, memory, blocking, configuration, system events).

## Важно

- Приложение **читает** только локальный DuckDB/Parquet через MCP — **не ходит в прод-БД** при запросах от Claude
- Нагрузка на целевой MSSQL минимальная: READ UNCOMMITTED, max 7 connections, 30s timeout
- Данные хранятся в `%LOCALAPPDATA%\PerformanceMonitorLite\` (не в этой папке)
- Ретеншн: rolling 3 месяца, ~50–200 МБ на сервер в неделю после сжатия

## Обновление

Новые релизы — [github.com/erikdarlingdata/PerformanceMonitor/releases](https://github.com/erikdarlingdata/PerformanceMonitor/releases). Скачать `PerformanceMonitorLite-lite-Portable.zip`, распаковать с заменой поверх этой папки, закоммитить обновление.
