const { app, BrowserWindow, shell, Tray, Menu } = require("electron");
const path = require("path");
const { spawn } = require("child_process");

let mainWindow = null;
let pyProc = null;
const PY_PORT = 8000;

function startPythonBackend() {
  const isPackaged = app.isPackaged;
  const scriptPath = isPackaged
    ? path.join(process.resourcesPath, "server.py")
    : path.join(__dirname, "server.py");

  const pythonExecutable = isPackaged
    ? path.join(process.resourcesPath, "runtime", "python.exe")
    : (process.platform === "win32" ? "python" : "python3");

  console.log(`Starting NOVA backend: ${pythonExecutable} ${scriptPath}`);
  try {
    pyProc = spawn(pythonExecutable, [scriptPath], {
      detached: false,
      stdio: "ignore",
    });
  } catch (err) {
    console.error("Failed to spawn Python process:", err);
  }
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1240,
    height: 820,
    minWidth: 900,
    minHeight: 600,
    backgroundColor: "#0f1117",
    icon: path.join(__dirname, "static", "favicon.svg"),
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      enableRemoteModule: false,
    },
    frame: true,
    title: "NOVA — Neural Operational & Virtual Assistant",
  });

  // Load local NOVA UI
  const targetUrl = `http://127.0.0.1:${PY_PORT}`;
  
  // Retry connection until backend starts
  const checkBackend = () => {
    mainWindow.loadURL(targetUrl).catch(() => {
      setTimeout(checkBackend, 500);
    });
  };
  setTimeout(checkBackend, 800);

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
  });

  mainWindow.on("closed", () => {
    mainWindow = null;
  });
}

app.whenReady().then(() => {
  startPythonBackend();
  createWindow();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", () => {
  if (pyProc) {
    try {
      pyProc.kill();
    } catch (e) {}
  }
  if (process.platform !== "darwin") {
    app.quit();
  }
});
