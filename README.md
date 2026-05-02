# AutoGLM Phone Controller

一个 Python 小项目：电脑通过 USB/ADB 连接 Android 手机，然后调用智谱 `autoglm-phone` 模型完成手机自动控制。

## 环境要求

- Python 3.10+
- Android Platform Tools，确保 `adb` 可以在终端直接运行
- Android 手机已开启「开发者选项」和「USB 调试」
- 智谱 BigModel API Key

## 安装

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
cp .env.example .env
```

再安装官方 Open-AutoGLM 的 `phone_agent` 包。它当前更适合按源码安装：

```bash
cd ..
git clone https://github.com/zai-org/Open-AutoGLM.git
cd Open-AutoGLM
python -m pip install -r requirements.txt
python -m pip install -e .
cd ../gcs-agent-py-1.0
```

编辑 `.env`：

```bash
BIGMODEL_API_KEY=你的智谱APIKey
```

## 使用

先连接手机并授权 USB 调试，然后检查设备：

```bash
autoglm-phone --list-devices
autoglm-phone --preflight
```

执行一个手机任务：

```bash
autoglm-phone "打开微信，给文件传输助手发送：测试一下 AutoGLM Phone"
```

把每一步模型返回内容保存到 txt：

```bash
autoglm-phone --max-steps 20 --trace-txt traces/run.txt "打开设置，查看当前 Wi-Fi 名称"
```

trace 文件会记录每一步的：

- `REQUEST MESSAGES`：每一步发给模型的入参，包含任务文本、屏幕信息、历史上下文和截图信息
- `MODEL THINKING`：模型推理/观察内容
- `MODEL ACTION RAW`：模型原始动作文本
- `PARSED ACTION`：Open-AutoGLM 解析后的动作
- `MODEL RAW CONTENT`：模型完整原始输出
- `MODEL TIMING`：首 token、推理结束、总耗时

默认情况下，截图会解码保存到 trace 文件旁边的图片目录中，txt 里只记录相对路径、base64 长度、前 120 字符和后 120 字符。比如：

```text
traces/run.txt
traces/run_images/step-001-image-01.png
```

如果需要在 txt 中同时写入完整截图 base64：

```bash
autoglm-phone --trace-txt traces/run-full.txt --trace-include-base64 "打开设置"
```

如果连接了多台设备：

```bash
autoglm-phone --device-id R5CT123ABC "打开设置，查看当前 Wi-Fi 名称"
```

## 手机集群任务工作台

后端启动：

```bash
cd /Users/liumeng/ai-agent/gcs-agent-py-1.0
source .venv/bin/activate
python -m pip install -e ".[dev]"
python -m uvicorn autoglm_phone_controller.web.app:app --host 127.0.0.1 --port 18081
```

前端启动：

```bash
cd /Users/liumeng/ai-agent/gcs-agent-py-1.0/frontend
npm install
npm run dev
```

打开：

```text
http://127.0.0.1:5173
```

当前工作台支持：

- 选择一台源手机，与 AutoGLM Phone 按步骤对话执行任务。
- 每一步记录模型动作、思考内容、截图 URL、点击坐标。
- 执行中可以输入人工提示，引导下一步动作。
- 只支持淘宝、京东、拼多多、得物；其他平台会直接提示暂不支持。
- 确认源手机任务无误后，系统会把主手机步骤压缩成 workflow prompt，下发给其他手机重新调用 AutoGLM Phone 执行。
- workflow prompt 会保留主手机已验证步骤、动作语义、参考截图和参考坐标，但要求目标手机根据当前截图重新判断，不照搬坐标。

旧版坐标回放规则已不作为默认执行方式：

```text
targetX = round(pointNormX / 999.0 * targetScreenWidth)
targetY = round(pointNormY / 999.0 * targetScreenHeight)
```

目标手机会使用同一套精简电商 system prompt，并以主手机 workflow prompt 作为任务输入继续看图执行。

## Windows 安装包

推荐在 Windows 11 构建机上打包：

```powershell
cd C:\path\to\gcs-agent-py-1.0
powershell -ExecutionPolicy Bypass -File .\scripts\build-windows.ps1
```

打包产物会输出到：

```text
release\AutoGLM Phone Cluster-Setup-0.1.0.exe
```

打包前请确认：

- `frontend` 可以 `npm run build`
- `apk\ADBKeyboard.apk` 存在
- `..\Open-AutoGLM` 已 clone，脚本会尝试安装它
- 如需内置 ADB，请把 Windows `platform-tools` 放到 `vendor\platform-tools`
- 当前 `.env` 会被打进安装包资源目录，MVP 阶段用于写死 API 配置

Windows `platform-tools` 至少需要：

```text
vendor\platform-tools\adb.exe
vendor\platform-tools\AdbWinApi.dll
vendor\platform-tools\AdbWinUsbApi.dll
```

也可以用 GitHub Actions 自动构建 Windows 安装包。工作流文件：

```text
.github\workflows\windows-installer.yml
```

使用方式：

1. 把 `.github/workflows/windows-installer.yml` 里的测试 key 改成你的测试 key：

```yaml
BIGMODEL_API_KEY=your_test_key_here
```

2. 推送到 GitHub。
3. 打开仓库页面：

```text
Actions → Build Windows Installer → Run workflow
```

4. 构建完成后，在 workflow run 的 Artifacts 下载：

```text
AutoGLM-Phone-Cluster-Windows-Installer
```

里面会包含：

```text
AutoGLM Phone Cluster-Setup-0.1.0.exe
```

## 工作方式

项目分三层：

- `autoglm_phone_controller.adb`：封装 ADB 设备发现、预检、唤醒、点击、滑动、截图等基础能力。
- `autoglm_phone_controller.runner`：延迟导入官方 `phone_agent`，构造 `ModelConfig` 和 `PhoneAgent`，调用 `autoglm-phone`。
- `autoglm_phone_controller.cli`：命令行入口，负责参数、环境变量和错误提示。

默认配置：

- `AUTOGLM_BASE_URL=https://open.bigmodel.cn/api/paas/v4`
- `AUTOGLM_MODEL=autoglm-phone`

## 常见问题

如果提示没有设备，先运行：

```bash
adb devices -l
```

如果状态是 `unauthorized`，看手机屏幕上是否弹出 USB 调试授权。

如果提示未安装 `phone-agent`，重新执行：

```bash
cd ../Open-AutoGLM
python -m pip install -r requirements.txt
python -m pip install -e .
cd ../gcs-agent-py-1.0
```

## 测试

```bash
pytest
```
