// Offline Electron client with a minimum width just larger than its assigned
// half-screen slot. No Discord profile, login, or remote content is involved.
const {app, BrowserWindow, screen} = require('electron');
const path = require('node:path');

app.setPath('userData', path.join(process.env.XDG_CACHE_HOME, 'scrollwork-electron'));
app.commandLine.appendSwitch('disable-background-networking');
app.disableHardwareAcceleration();
let window;
app.whenReady().then(() => {
    const minWidth = Number(process.env.SCROLLWORK_ELECTRON_MIN_WIDTH ??
        (Math.floor((screen.getPrimaryDisplay().workArea.width - 24) / 2) + 16));
    window = new BrowserWindow({
        title: 'SW-electron', width: 800, height: 400,
        minWidth, minHeight: 200,
        backgroundColor: '#f00000',
        webPreferences: {sandbox: true, nodeIntegration: false},
    });
    window.loadURL('data:text/html,<title>SW-electron</title><body style="margin:0;background:%23f00000"><h1>Offline minimum-width regression</h1></body>');
});
app.on('window-all-closed', () => app.quit());
