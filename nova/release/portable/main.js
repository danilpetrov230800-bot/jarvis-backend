const { app, BrowserWindow, ipcMain, shell } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const http = require('http');

const BACKEND_PORT = 47821;
const BACKEND_HOST = '127.0.0.1';
let mainWindow = null;
let backendProcess = null;

const isDev = !app.isPackaged;

function getBackendPath() {
  if (isDev) {
    return {
      cwd: path.join(__dirname, '../../backend'),
      cmd: process.platform === 'win32' ? 'python' : 'python3',
      args: ['-m', 'nova.main'],
    };
  }
  const resources = process.resourcesPath;
  const bundledExe = path.join(resources, 'nova-backend.exe');
  const fs = require('fs');
  if (process.platform === 'win32' && fs.existsSync(bundledExe)) {
    return { cwd: resources, cmd: bundledExe, args: [] };
  }
  return {
    cwd: path.join(resources, 'backend'),
    cmd: process.platform === 'win32' ? 'python' : 'python3',
    args: ['-m', 'nova.main'],
  };
}

function waitForBackend(maxAttempts = 30) {
  return new Promise((resolve, reject) => {
    let attempts = 0;
    const check = () => {
      attempts++;
      const req = http.get(`http://${BACKEND_HOST}:${BACKEND_PORT}/`, (res) => {
        if (res.statusCode === 200) resolve();
        else if (attempts < maxAttempts) setTimeout(check, 500);
        else reject(new Error('Backend timeout'));
      });
      req.on('error', () => {
        if (attempts < maxAttempts) setTimeout(check, 500);
        else reject(new Error('Backend timeout'));
      });
    };
    check();
  });
}

function startBackend() {
  const { cwd, cmd, args } = getBackendPath();
  const env = {
    ...process.env,
    NOVA_HOST: BACKEND_HOST,
    NOVA_PORT: String(BACKEND_PORT),
    PYTHONPATH: cwd,
  };

  backendProcess = spawn(cmd, args, {
    cwd,
    env,
    stdio: ['ignore', 'pipe', 'pipe'],
    windowsHide: true,
  });

  backendProcess.stdout?.on('data', (d) => console.log('[NOVA Backend]', d.toString()));
  backendProcess.stderr?.on('data', (d) => console.error('[NOVA Backend]', d.toString()));
  backendProcess.on('exit', (code) => {
    console.log('[NOVA Backend] exited with code', code);
    backendProcess = null;
  });
}

function stopBackend() {
  if (backendProcess) {
    backendProcess.kill();
    backendProcess = null;
  }
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 900,
    minHeight: 600,
    title: 'NOVA',
    backgroundColor: '#0a0a0f',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
    show: false,
  });

  mainWindow.once('ready-to-show', () => mainWindow.show());

  if (isDev) {
    mainWindow.loadURL('http://localhost:5173');
  } else {
    mainWindow.loadFile(path.join(__dirname, '../dist/index.html'));
  }

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

app.whenReady().then(async () => {
  if (!isDev) {
    startBackend();
    try {
      await waitForBackend();
    } catch (e) {
      console.error('Failed to start backend:', e);
    }
  }
  createWindow();
});

app.on('window-all-closed', () => {
  stopBackend();
  if (process.platform !== 'darwin') app.quit();
});

app.on('before-quit', () => stopBackend());

ipcMain.handle('get-backend-url', () => `http://${BACKEND_HOST}:${BACKEND_PORT}`);
ipcMain.handle('open-external', (_, url) => shell.openExternal(url));
