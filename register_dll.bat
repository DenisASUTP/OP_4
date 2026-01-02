@echo off
echo Регистрация Dll1.dll
echo.

REM Определяем разрядность системы
if exist "%SystemRoot%\SysWOW64" (
    echo 64-битная система
    echo.
    echo Регистрация 32-битной версии:
    %SystemRoot%\SysWOW64egsvr32.exe /s "%~dp0Dll1.dll"
    echo.
    echo Регистрация 64-битной версии:
    %SystemRoot%\System32egsvr32.exe /s "%~dp0Dll1.dll"
) else (
    echo 32-битная система
    echo.
    echo Регистрация:
    %SystemRoot%\System32egsvr32.exe /s "%~dp0Dll1.dll"
)

echo.
echo Готово!
pause
