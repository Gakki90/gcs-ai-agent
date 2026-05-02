$ErrorActionPreference = "Stop"

Set-Location (Split-Path -Parent $PSScriptRoot)

if (!(Test-Path ".venv")) {
  py -3.10 -m venv .venv
}

.\.venv\Scripts\python.exe -m pip install -U pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pip install pyinstaller

if (Test-Path "..\Open-AutoGLM") {
  Push-Location ..\Open-AutoGLM
  ..\gcs-agent-py-1.0\.venv\Scripts\python.exe -m pip install -r requirements.txt
  ..\gcs-agent-py-1.0\.venv\Scripts\python.exe -m pip install -e .
  Pop-Location
} else {
  Write-Host "未找到 ..\Open-AutoGLM。请先 clone 官方项目并在当前虚拟环境中安装 phone_agent。" -ForegroundColor Yellow
}

Push-Location frontend
npm install
npm run build
Pop-Location

if (!(Test-Path "vendor\platform-tools\adb.exe")) {
  Write-Host "请把 Windows platform-tools 放到 vendor\platform-tools，至少包含 adb.exe、AdbWinApi.dll、AdbWinUsbApi.dll。" -ForegroundColor Yellow
}

.\.venv\Scripts\pyinstaller.exe --clean --noconfirm --name autoglm-backend --onefile --collect-all autoglm_phone_controller --collect-all phone_agent --add-data "apk/ADBKeyboard.apk;apk" backend_entry.py

npm install
npm run electron:pack
