/**
 * Autopilot store — manages SSE connection and autopilot state.
 *
 * Exposes reactive stores for the overlay to consume, plus
 * start/stop actions that manage the EventSource lifecycle.
 */
import { writable, derived, get } from 'svelte/store';

// ── Core state ──────────────────────────────────

/** Whether the autopilot overlay is visible. */
export const autopilotVisible = writable(false);

/** Whether autopilot is actively running. */
export const autopilotRunning = writable(false);

/** Whether a stop signal has been sent (waiting for graceful stop). */
export const autopilotStopping = writable(false);

/** Whether autopilot was stopped by user (distinct from error or complete). */
export const autopilotStopped = writable(false);

/** Current task being processed. */
export const autopilotCurrentTask = writable('');

/** Current phase of the current task. */
export const autopilotCurrentPhase = writable('');

/** Current implement stage info { stage, total_stages }. */
export const autopilotStageInfo = writable({ stage: 0, total_stages: 0 });

/** Queue of pending tasks [{ name, milestone }]. */
export const autopilotQueue = writable([]);

/** Total tasks / pending counts. */
export const autopilotCounts = writable({ total: 0, pending: 0, completed: 0 });

/** Log of events [{ time, type, task, phase, message }]. */
export const autopilotLog = writable([]);

/** Per-task status map: { taskName: 'pending' | 'running' | 'done' | 'error' | 'skipped' }. */
export const autopilotTaskStatus = writable({});

/** Error info if stopped on error: { task, phase, message } or null. */
export const autopilotError = writable(null);

/** Elapsed seconds (updated every second while running). */
export const autopilotElapsed = writable(0);

/** Final completion data or null. */
export const autopilotResult = writable(null);

// ── Derived ─────────────────────────────────────

/** Progress as 0-100 percent. */
export const autopilotProgress = derived(
	autopilotCounts,
	($c) => ($c.pending > 0 ? Math.round(($c.completed / $c.pending) * 100) : 0),
);

// ── Internal refs ───────────────────────────────

/** @type {EventSource | null} */
let eventSource = null;

/** @type {ReturnType<typeof setInterval> | null} */
let timerInterval = null;

let startTimestamp = 0;

// ── Helpers ─────────────────────────────────────

function addLog(type, task, phase, message) {
	autopilotLog.update((log) => [
		...log,
		{
			time: new Date().toLocaleTimeString(),
			timestamp: Date.now(),
			type,
			task: task || '',
			phase: phase || '',
			message: message || '',
		},
	]);
}

function setTaskStatus(taskName, status) {
	autopilotTaskStatus.update((map) => ({ ...map, [taskName]: status }));
}

// ── Actions ─────────────────────────────────────

/**
 * Start autopilot — opens SSE connection to /api/autopilot/start.
 */
export function startAutopilot() {
	if (eventSource) stopAutopilot();

	// Reset state
	autopilotRunning.set(true);
	autopilotStopping.set(false);
	autopilotStopped.set(false);
	autopilotVisible.set(true);
	autopilotCurrentTask.set('');
	autopilotCurrentPhase.set('');
	autopilotStageInfo.set({ stage: 0, total_stages: 0 });
	autopilotQueue.set([]);
	autopilotCounts.set({ total: 0, pending: 0, completed: 0 });
	autopilotLog.set([]);
	autopilotTaskStatus.set({});
	autopilotError.set(null);
	autopilotElapsed.set(0);
	autopilotResult.set(null);

	startTimestamp = Date.now();
	timerInterval = setInterval(() => {
		autopilotElapsed.set(Math.round((Date.now() - startTimestamp) / 1000));
	}, 1000);

	addLog('system', '', '', 'Autopilot starting...');

	// Use fetch + ReadableStream for POST SSE
	const controller = new AbortController();
	eventSource = /** @type {any} */ (controller); // store for cleanup

	fetch('/api/autopilot/start', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: '{}',
		signal: controller.signal,
	})
		.then((res) => {
			if (!res.ok) throw new Error(`HTTP ${res.status}`);
			const reader = res.body.getReader();
			const decoder = new TextDecoder();
			let buffer = '';

			function pump() {
				return reader.read().then(({ done, value }) => {
					if (done) {
						_handleStreamEnd();
						return;
					}
					buffer += decoder.decode(value, { stream: true });
					// Parse SSE frames
					const lines = buffer.split('\n');
					buffer = lines.pop() || ''; // keep incomplete line

					let currentEvent = '';
					let currentData = '';

					for (const line of lines) {
						if (line.startsWith('event: ')) {
							currentEvent = line.slice(7).trim();
						} else if (line.startsWith('data: ')) {
							currentData = line.slice(6);
						} else if (line === '' && currentEvent && currentData) {
							_handleSSE(currentEvent, currentData);
							currentEvent = '';
							currentData = '';
						}
					}
					return pump();
				});
			}

			return pump();
		})
		.catch((err) => {
			if (err.name === 'AbortError') return; // expected on stop
			addLog('error', '', '', `Connection error: ${err.message}`);
			autopilotError.set({ task: '', phase: '', message: err.message });
			_cleanup();
		});
}

/**
 * Signal autopilot to stop gracefully.
 */
export async function stopAutopilot() {
	autopilotStopping.set(true);
	try {
		await fetch('/api/autopilot/stop', { method: 'POST' });
	} catch {
		/* ignore */
	}
	// Also abort the fetch stream
	if (eventSource && typeof eventSource.abort === 'function') {
		try {
			eventSource.abort();
		} catch {
			/* ignore */
		}
	}
	addLog('system', '', '', 'Stop signal sent');
}

/**
 * Close overlay without stopping (if already finished/stopped).
 */
export function closeAutopilot() {
	_cleanup();
	autopilotVisible.set(false);
}

// ── SSE event handlers ──────────────────────────

function _handleSSE(event, rawData) {
	let data;
	try {
		data = JSON.parse(rawData);
	} catch {
		return;
	}

	switch (event) {
		case 'started':
			addLog('system', '', '', 'Autopilot engaged');
			break;

		case 'queue':
			autopilotQueue.set(data.tasks || []);
			autopilotCounts.set({ total: data.total, pending: data.pending, completed: 0 });
			for (const t of data.tasks || []) {
				setTaskStatus(t.name, 'pending');
			}
			addLog('system', '', '', `${data.pending} tasks in queue`);
			break;

		case 'task:start':
			autopilotCurrentTask.set(data.task);
			autopilotCurrentPhase.set('');
			autopilotStageInfo.set({ stage: 0, total_stages: 0 });
			setTaskStatus(data.task, 'running');
			addLog('task', data.task, '', `Starting task (${data.index + 1}/${data.total})`);
			break;

		case 'task:done':
			setTaskStatus(data.task, 'done');
			autopilotCounts.update((c) => ({ ...c, completed: data.completed }));
			addLog('task', data.task, '', 'Task completed');
			break;

		case 'task:skip':
			setTaskStatus(data.task, 'skipped');
			addLog('task', data.task, '', `Skipped: ${data.reason}`);
			break;

		case 'phase:start':
			autopilotCurrentPhase.set(data.phase);
			if (data.phase === 'implement') {
				autopilotStageInfo.set({
					stage: data.stage || 0,
					total_stages: data.total_stages || 0,
				});
			}
			addLog(
				'phase',
				data.task,
				data.phase,
				data.phase === 'implement'
					? `Implement stage ${data.stage}/${data.total_stages}`
					: `${_capitalize(data.phase)} started`,
			);
			break;

		case 'phase:done':
			addLog(
				'phase',
				data.task,
				data.phase,
				data.phase === 'implement'
					? `Stage ${data.stage}/${data.total_stages} done (${data.files_count} files)`
					: data.phase === 'tests'
						? `Tests: ${data.passed ? 'PASSED' : 'completed'} — ${data.summary || ''}`
						: `${_capitalize(data.phase)} done`,
			);
			break;

		case 'stopped':
			autopilotStopped.set(true);
			addLog('system', data.task || '', '', `Stopped: ${data.reason}`);
			_cleanup();
			break;

		case 'error':
			autopilotError.set({
				task: data.task || '',
				phase: data.phase || '',
				message: data.message || 'Unknown error',
			});
			setTaskStatus(data.task, 'error');
			addLog('error', data.task || '', data.phase || '', data.message);
			_cleanup();
			break;

		case 'completed':
			autopilotResult.set(data);
			autopilotCounts.update((c) => ({ ...c, completed: data.completed }));
			addLog(
				'system',
				'',
				'',
				`All done! ${data.completed}/${data.total} tasks in ${data.elapsed}s`,
			);
			_cleanup();
			break;
	}
}

function _handleStreamEnd() {
	const running = get(autopilotRunning);
	if (running) {
		// Stream ended unexpectedly
		addLog('system', '', '', 'Connection closed');
		_cleanup();
	}
}

function _cleanup() {
	autopilotRunning.set(false);
	autopilotStopping.set(false);
	if (timerInterval) {
		clearInterval(timerInterval);
		timerInterval = null;
	}
	eventSource = null;
}

function _capitalize(s) {
	return s ? s.charAt(0).toUpperCase() + s.slice(1) : '';
}
