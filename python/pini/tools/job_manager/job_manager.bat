:: Launcher from ShotManager commandline

@echo off

echo RUNNING ShotManager %PYTHONSTARTUP%

:: Locate python3
set python3=C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python310\python.exe
echo - python3 %python3%
if exist %python3% (
	echo - python3 found
) else (
	echo - python3 missing
	pause
	exit
)

:: Locate shot manager
set shot_manager=%~dp0/sm_standalone.py
echo - shot_manager %shot_manager%
if exist %shot_manager% (
	echo - shot_manager found
) else (
	echo - shot_manager missing
	pause
	exit
)

:: Execute shot manager
%python3% %shot_manager%

:: Maintain shell after execute
pause 