@echo off
chcp 65001 > nul
title FunPay Bot

if not exist .venv (
    echo [!] Виртуальное окружение не найдено. Запуск установки...
    call setup.bat
)

if not exist .env (
    echo [!] Файл .env не найден. Запуск мастера первоначальной настройки...
    .venv\Scripts\python.exe setup_wizard.py
)

echo [*] Запуск FunPay Bot...
.venv\Scripts\python.exe main.py
pause
