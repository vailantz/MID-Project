@echo off
chcp 65001 >nul
set PGCLIENTENCODING=UTF8
set PAGER=
set PG_BIN=C:\Program Files\PostgreSQL\16\bin
set PORT=55441

if "%~1"=="" goto :help
if /I "%~1"=="help" goto :help
if /I "%~1"=="all" goto :all
if /I "%~1"=="profile" goto :profile
if /I "%~1"=="pg" goto :pg
if /I "%~1"=="sql" goto :sql
if /I "%~1"=="psql" goto :psql
if /I "%~1"=="xml" goto :xml
if /I "%~1"=="xquery" goto :xquery
if /I "%~1"=="clean" goto :clean

echo Comando desconhecido: %~1
goto :help

:help
echo ============================================================================
echo   MID Project P1 - Comandos Rapidos (Subtopico B: PostgreSQL B1 + BaseX B2)
echo ============================================================================
echo.
echo   run all       - Corre TUDO automaticamente (CSV + 38 testes PG + 36 testes XML)
echo   run profile   - Mostra o perfil de qualidade do CSV de Lisboa (5.261 registos)
echo   run pg        - Valida e abre a base PostgreSQL B1 (fica aberta para mostrar)
echo   run sql       - Mostra o resultado formatado das 3 consultas SQL da P1 (Fonte B1)
echo   run psql      - Abre a consola interativa do PostgreSQL (tiago_p1=#) em UTF-8
echo   run xml       - Valida o XSD e corre os 36 testes do BaseX XML (Fonte B2)
echo   run xquery    - Mostra o resultado formatado das 6 consultas XQuery (Fonte B2)
echo   run clean     - Limpa os ficheiros temporarios (.runtime e __pycache__)
echo.
echo ============================================================================
exit /b 0

:all
echo [1/3] A perfilar fonte original CSV (B1)...
python -X utf8 "%~dp0scripts\profile_source.py"
if errorlevel 1 exit /b 1
echo.
echo [2/3] A testar PostgreSQL B1 (Catalogo + Atividade Sintetica - 38 verificacoes)...
python -X utf8 "%~dp0scripts\check_full_catalogue.py" --with-activity
if errorlevel 1 exit /b 1
echo.
echo [3/3] A testar BaseX XML B2 (XSD + XQuery - 36 verificacoes)...
python -X utf8 "%~dp0scripts\check_basex_p1.py"
exit /b %ERRORLEVEL%

:profile
python -X utf8 "%~dp0scripts\profile_source.py"
exit /b %ERRORLEVEL%

:pg
python -X utf8 "%~dp0scripts\check_full_catalogue.py" --with-activity --keep-open
exit /b %ERRORLEVEL%

:sql
python -X utf8 "%~dp0scripts\show_queries.py" sql
exit /b %ERRORLEVEL%

:psql
"%PG_BIN%\psql.exe" -h 127.0.0.1 -p %PORT% -U dmi_p1 -d tiago_p1 -P pager=off
exit /b %ERRORLEVEL%

:xml
python -X utf8 "%~dp0scripts\check_basex_p1.py"
exit /b %ERRORLEVEL%

:xquery
python -X utf8 "%~dp0scripts\show_queries.py" xquery %~2
exit /b %ERRORLEVEL%

:clean
if exist "%~dp0.runtime" rmdir /s /q "%~dp0.runtime"
if exist "%~dp0scripts\__pycache__" rmdir /s /q "%~dp0scripts\__pycache__"
echo Limpeza concluida (.runtime e __pycache__ removidos).
exit /b 0
