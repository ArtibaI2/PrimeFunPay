@echo off
chcp 65001 > nul
title FunPay Bot - Установка

echo [*] Создание виртуального окружения Python...
python -m venv .venv

echo [*] Установка необходимых библиотек...
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\pip.exe install -r requirements.txt

echo [*] Запуск тестов для проверки готовности...
.venv\Scripts\pytest.exe -v

echo.
echo =======================================================
echo [OK] Установка библиотек успешно завершена!
echo =======================================================
echo.
echo Запустить мастер настройки ключей прямо сейчас? (Y/N)
set /p run_wizard="> "
if /i "%run_wizard%"=="Y" (
    .venv\Scripts\python.exe setup_wizard.py
) else (
    echo Вы можете запустить настройку позже командой:
    echo   .venv\Scripts\python setup_wizard.py
)
echo.
pause
