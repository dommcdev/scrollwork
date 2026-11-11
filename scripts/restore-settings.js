// Run only when Scrollwork is disabled (for example after a shell crash).
import {SettingsLease} from '../settings.js';
const lease = new SettingsLease();
print(`Recovered ${lease.recovered} saved Scrollwork settings`);
