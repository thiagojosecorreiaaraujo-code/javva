@echo off
rem Javva - liga a SUA conta do Claude ao container (rode uma vez, no servidor).
cd /d "%~dp0"
echo.
echo  == JAVVA: ligar a sua conta do Claude ==
echo.
echo  1) Vai abrir o navegador para VOCE autorizar a sua conta.
echo     No fim aparece um token que comeca com sk-ant-oat. Copie-o.
echo.
pause
call claude setup-token
echo.
echo  2) Agora cole o token abaixo (ele nao aparece na tela).
python gerar_env.py --pedir-token
if errorlevel 1 goto erro
echo.
echo  3) Subindo o Javva...
docker compose up -d --build
if errorlevel 1 goto erro
timeout /t 8 /nobreak >nul
curl -s http://127.0.0.1:8787/saude
echo.
echo.
echo  Pronto. Nos PCs da rede: baixe http://192.168.68.106:8787/javva.bat
echo  e de dois cliques.
pause
exit /b 0
:erro
echo.
echo  Algo falhou - leia a mensagem acima.
pause
exit /b 1
