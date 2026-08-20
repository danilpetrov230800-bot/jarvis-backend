const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('nova', {
  getBackendUrl: () => ipcRenderer.invoke('get-backend-url'),
  openExternal: (url) => ipcRenderer.invoke('open-external', url),
});
