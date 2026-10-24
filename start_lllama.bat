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
:: ELLENŐRZÉSEK & AUTO-DOWNLOAD
:: ======================================================
if not exist "%EXE_PATH%" (
    echo.
    echo [!] A llama-server.exe nem található a 'bin' mappában!
    echo [+] Letöltés indítása a hivatalos llama.cpp GitHub-ról...
    echo.
    
    if not exist "%~dp0bin" mkdir "%~dp0bin"
    
    :: Legfrissebb Windows CUDA binárisok letöltése és kicsomagolása
    powershell -Command "^
        $ProgressPreference = 'SilentlyContinue'; ^
        $url = 'https://github.com/ggerganov/llama.cpp/releases/download/b3600/llama-b3600-bin-win-cuda-cu12.2-x64.zip'; ^
        $zip = '%~dp0bin\llama.zip'; ^
        Write-Host ' Binárisok letöltése folyamatban...' -ForegroundColor Yellow; ^
        Invoke-WebRequest -Uri $url -OutFile $zip; ^
        Write-Host ' Kicsomagolás...' -ForegroundColor Yellow; ^
        Expand-Archive -Path $zip -DestinationPath '%~dp0bin' -Force; ^
        Remove-Item $zip;"

    if not exist "%EXE_PATH%" (
        echo.
        echo [HIBA] A letöltés vagy kicsomagolás meghiúsult!
        pause
        exit /b
    )
    echo [+] A llama-server sikeresen telepítve a 'bin' mappába!
    echo.
)

if not exist "%MODEL_PATH%" (
    echo.
    echo [HIBA] A megadott modell nem található: models\%MODEL_NAME%
    echo.
    echo Kérlek, másold be a GGUF fájlodat a 'models' mappába!
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