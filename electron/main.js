const { app, BrowserWindow, dialog } = require("electron");
const path = require("path");
const { spawn } = require("child_process");
const http = require("http");

const BACKEND_PORT = 18081;
let backendProcess = null;

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
  const childEnv = {
    ...process.env,
    AUTOGLM_APP_ROOT: root,
  };

  backendProcess = spawn(backendExecutable(), backendArgs(), {
    cwd: root,
    env: childEnv,
    windowsHide: true,
  });

  backendProcess.on("exit", (code) => {
    console.log(`[backend] exited with code ${code}`);
  });

  backendProcess.on("error", (error) => {
    dialog.showErrorBox("后端启动失败", String(error));
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

app.on("before-quit", () => {
  if (backendProcess && !backendProcess.killed) {
    backendProcess.kill();
  }
});

app.on("window-all-closed", () => {
  app.quit();
});
