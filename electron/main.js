const { app, BrowserWindow, dialog } = require("electron");
const path = require("path");
const fs = require("fs");
const { spawn } = require("child_process");
const http = require("http");

const BACKEND_PORT = 18081;
let backendProcess = null;
let isQuitting = false;

function isPackaged() {
  return app.isPackaged;
}

function appRoot() {
  return isPackaged() ? process.resourcesPath : path.resolve(__dirname, "..");
}

function backendExecutable() {
  if (isPackaged()) {
    return path.join(process.resourcesPath, "backend", "autoglm-backend.exe");
  }
  const projectRoot = appRoot();
  return process.platform === "win32"
    ? path.join(projectRoot, ".venv", "Scripts", "python.exe")
    : path.join(projectRoot, ".venv", "bin", "python");
}

function backendArgs() {
  if (isPackaged()) return [];
  return ["backend_entry.py"];
}

function startBackend() {
  const root = appRoot();
  const logsDir = path.join(path.dirname(app.getPath("exe")), "logs");
  fs.mkdirSync(logsDir, { recursive: true });
  const backendLog = fs.createWriteStream(path.join(logsDir, "backend.log"), { flags: "a" });
  const backendErrorLog = fs.createWriteStream(path.join(logsDir, "backend-error.log"), { flags: "a" });

  const childEnv = {
    ...process.env,
    AUTOGLM_APP_ROOT: root,
    AUTOGLM_LOG_DIR: logsDir,
    PYTHONUTF8: "1",
    PYTHONIOENCODING: "utf-8",
  };

  backendProcess = spawn(backendExecutable(), backendArgs(), {
    cwd: root,
    env: childEnv,
    windowsHide: true,
  });

  backendProcess.stdout.pipe(backendLog);
  backendProcess.stderr.pipe(backendErrorLog);

  backendProcess.on("exit", (code) => {
    console.log(`[backend] exited with code ${code}`);
    backendProcess = null;
  });

  backendProcess.on("error", (error) => {
    dialog.showErrorBox("后端启动失败", String(error));
  });
}

function stopBackend() {
  if (!backendProcess || backendProcess.killed) {
    backendProcess = null;
    return Promise.resolve();
  }

  const pid = backendProcess.pid;
  return new Promise((resolve) => {
    const timeout = setTimeout(() => resolve(), 3000);
    backendProcess.once("exit", () => {
      clearTimeout(timeout);
      resolve();
    });

    if (process.platform === "win32" && pid) {
      spawn("taskkill", ["/pid", String(pid), "/T", "/F"], { windowsHide: true });
      return;
    }

    backendProcess.kill("SIGTERM");
    setTimeout(() => {
      if (backendProcess && !backendProcess.killed) {
        backendProcess.kill("SIGKILL");
      }
    }, 1200);
  });
}

function waitForBackend(timeoutMs = 20000) {
  const startedAt = Date.now();
  return new Promise((resolve, reject) => {
    const check = () => {
      const req = http.get(`http://127.0.0.1:${BACKEND_PORT}/api/health`, (res) => {
        res.resume();
        resolve();
      });
      req.on("error", () => {
        if (Date.now() - startedAt > timeoutMs) {
          reject(new Error("后端启动超时"));
          return;
        }
        setTimeout(check, 500);
      });
      req.setTimeout(800, () => {
        req.destroy();
      });
    };
    check();
  });
}

async function createWindow() {
  const win = new BrowserWindow({
    width: 1440,
    height: 920,
    minWidth: 1180,
    minHeight: 760,
    title: "AutoGLM Phone Cluster",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
    },
  });

  await win.loadURL(`http://127.0.0.1:${BACKEND_PORT}`);
}

app.whenReady().then(async () => {
  startBackend();
  try {
    await waitForBackend();
    await createWindow();
  } catch (error) {
    dialog.showErrorBox("启动失败", String(error));
    app.quit();
  }
});

app.on("before-quit", async (event) => {
  if (isQuitting) return;
  event.preventDefault();
  isQuitting = true;
  await stopBackend();
  app.quit();
});

app.on("window-all-closed", () => {
  app.quit();
});
