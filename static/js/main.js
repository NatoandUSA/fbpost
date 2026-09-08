import { API } from './api.js';
import { showToast } from './toast.js';
import { stopCurrentJob } from './jobs.js';
import { state } from './state.js';

window.AppModules = { API, showToast, stopCurrentJob, state };
console.log('FB Automation ES Modules loaded (v6.0.8)');
