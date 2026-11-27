@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0.."

echo [1/4] 检查全局 Python ...
where python >nul 2>nul
if errorlevel 1 (
    echo [错误] 未找到全局 Python，请先安装 Python 并加入 PATH。
    goto :end
)

echo [2/4] 准备虚拟环境 .venv ...
if not exist ".venv\Scripts\python.exe" (
    python -m venv .venv
    if errorlevel 1 (
        echo [错误] 创建虚拟环境失败。
        goto :end
    )
)

echo [3/4] 在虚拟环境中安装依赖 ...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q -r requirements.txt
if errorlevel 1 (
    echo [错误] 依赖安装失败，请检查网络后重试。
    goto :end
)

echo [4/4] 打包为 exe ...
".venv\Scripts\python.exe" -m PyInstaller --clean --noconfirm --windowed --name "Oneline" --contents-directory "lib" --icon "%CD%\src\resources\app.ico" --add-data "%CD%\src\resources;resources" --distpath dist --workpath build --specpath build src\main.py
if errorlevel 1 (
    echo [错误] 构建失败，请查看上方 PyInstaller 输出。
    goto :end
)

echo [完成] 构建成功，产物位置：dist\Oneline\Oneline.exe。

:end
cmd /k
