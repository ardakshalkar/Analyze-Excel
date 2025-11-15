@echo off
echo Starting Vue.js frontend...
cd /d %~dp0\frontend
call npm install
call npm run dev
pause

