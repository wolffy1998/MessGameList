@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0.."

echo [1/3] 删除 dist 构建产物 ...
if exist dist rmdir /s /q dist

echo [2/3] 删除 build 中间目录 ...
if exist build rmdir /s /q build

echo [3/3] 删除 spec、__pycache__ 和 .pyc ...
if exist *.spec del /q *.spec
if exist __pycache__ rmdir /s /q __pycache__
if exist *.pyc del /q *.pyc
if exist src\__pycache__ rmdir /s /q src\__pycache__
if exist src\*.pyc del /q src\*.pyc

if /i "%~1"=="--all" (
    echo [附加] 删除虚拟环境 .venv ...
    if exist .venv rmdir /s /q .venv
)

echo [完成] 清理完毕。

cmd /k
