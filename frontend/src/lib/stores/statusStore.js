/**
 * Status & data stores for the Skaro Dashboard.
 *
 * Each field is a separate writable so that updates to one (e.g. WS status)
 * don't cause re-renders in subscribers of another (e.g. task detail).
 */
import { writable } from 'svelte/store';

/** Server-side project status (tasks list, config, flags). */
export const status = writable(null);

/** WebSocket connection state. */
export const wsConnected = writable(false);

/** Update check result from /api/update-check. */
export const updateInfo = writable(null);

/** Currently loaded task detail object. */
export const taskDetail = writable(null);

/** Proposed dev-plan milestones (temporary, during generation flow). */
export const devplanMilestones = writable(null);

/** Last implementation result, stage number, and task name (for review UI). */
export const lastImplementResult = writable(null);
export const lastImplementStage = writable(null);
export const lastImplementTask = writable(null);

/** Clear all task-related transient state (e.g. on navigation away). */
export function resetTaskState() {
	taskDetail.set(null);
	lastImplementResult.set(null);
	lastImplementStage.set(null);
	lastImplementTask.set(null);
}
