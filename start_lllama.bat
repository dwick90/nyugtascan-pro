@echo off
chcp 65001 > nul
title Llama Server - Helyi AI Backend

:: ======================================================
:: BEÁLLÍTÁSOK (Ezeket módosítsa a felhasználó)
:: ======================================================
set MODEL_NAME=gemma-4-12b-it-Q4_K_M.gguf
set HOST=0.0.0.0
set PORT=8080
set CTX_SIZE=34400
set GPU_LAYERS=99

:: ======================================================
:: ÚTVONALAK
:: ======================================================
set EXE_PATH=%~dp0bin\llama-server.exe
set MODEL_PATH=%~dp0models\%MODEL_NAME%

:: ======================================================
:: ELLENŐRZÉSEK
:: ======================================================
if not exist "%EXE_PATH%" (
    echo.
    echo [HIBA] A llama-server.exe nem található a 'bin' mappában!
    echo Mappaszerkezet ellenőrzése: bin\llama-server.exe
    echo.
    pause
    exit /b
)

if not exist "%MODEL_PATH%" (
    echo.
    echo [HIBA] A megadott modell nem található: models\%MODEL_NAME%
    echo.
    echo Kérlek, másold be a GGUF fájlodat a 'models' mappába,
    echo majd nyisd meg a start_llama.bat fájlt és írd át a MODEL_NAME változót!
    echo.
    pause
    exit /b
)

echo ======================================================
echo           Llama Server Indítása
echo ======================================================
echo Modell:      models\%MODEL_NAME%
echo Cím:         http://%HOST%:%PORT%
echo Kontextus:   %CTX_SIZE% token
echo GPU Rétegek: %GPU_LAYERS%
echo ======================================================
echo.

"%EXE_PATH%" ^
  -m "%MODEL_PATH%" ^
  --host %HOST% ^
  --port %PORT% ^
  -ngl %GPU_LAYERS% ^
  -c %CTX_SIZE% ^
  --parallel 1 ^
  -b 2048 ^
  -ub 2048 ^
  --kv-unified ^
  --cache-idle-slots ^
  -ctk q8_0 ^
  -ctv q8_0 ^
  -fa 1 ^
  -t 6 ^
  --cache-ram 4096 ^
  --temp 1.0 ^
  --top-p 0.95 ^
  --top-k 64 ^
  --min-p 0.05 ^
  --presence-penalty 0.15 ^
  --repeat-penalty 1.0 ^
  --reasoning off ^
  --reasoning-format none ^
  --jinja

pause