@echo off
chcp 65001 >nul
echo ============================================================
echo  Разовая установка зависимостей для проектного MCP-сервера
echo  документации 1С (scripts\mcp-docs-server\).
echo.
echo  Ставится один пакет: @modelcontextprotocol/sdk (Node.js).
echo  Нужен для того, чтобы Claude Code мог искать по docs\.
echo.
echo  Запускать один раз после git clone. Повторно не нужно.
echo  После установки просто открой проект в Claude Code -
echo  MCP поднимется автоматически через .mcp.json.
echo ============================================================
echo.
cd /d "%~dp0scripts\mcp-docs-server"
call npm install
echo.
echo Готово. Открой проект в Claude Code - MCP заработает сам.
pause
