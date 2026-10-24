@echo off
cd /d D:\OCR

echo 0. AI inditasa (gemma12.bat)...
start "AI Modell" "D:\gemma12.bat"

:: Hagyunk 10 masodpercet az AI elindulasara, mielott az OCR feldolgozas elkezdodne
timeout /t 10 /nobreak > nul

echo 1. Nyugta feldolgozasa (OCR)...
D:\OCR\glm_env\Scripts\python.exe receipt_pipeline.py

echo 2. Web szerver inditasa kulon ablakban...
start "Nyugta Szerver" D:\OCR\glm_env\Scripts\python.exe server.py

echo 3. Cloudflare Tunnel inditasa es link kuldese emailben...
D:\OCR\glm_env\Scripts\python.exe run_tunnel.py

pause