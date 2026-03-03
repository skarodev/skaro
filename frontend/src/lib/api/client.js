/**
 * Skaro API client and WebSocket manager.
 */

const BASE = '';

/** Max consecutive WebSocket reconnect attempts before giving up. */
const WS_MAX_RECONNECTS = 10;

/** Delay between reconnect attempts (ms). */
const WS_RECONNECT_DELAY = 3000;

// ── HTTP helpers ──────────────────────────────

/**
 * @param {string} path
 * @param {AbortSignal} [signal]
 */
async function get(path, signal) {
	const res = await fetch(`${BASE}${path}`, { signal });
	if (!res.ok) throw new Error(`GET ${path}: ${res.status}`);
	return res.json();
}

/**
 * @param {string} path
 * @param {any} body
 * @param {AbortSignal} [signal]
 */
async function post(path, body = {}, signal) {
	const res = await fetch(`${BASE}${path}`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(body),
		signal,
	});
	if (!res.ok) throw new Error(`POST ${path}: ${res.status}`);
	return res.json();
}

/**
 * @param {string} path
 * @param {any} body
 * @param {AbortSignal} [signal]
 */
async function put(path, body = {}, signal) {
	const res = await fetch(`${BASE}${path}`, {
		method: 'PUT',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(body),
		signal,
	});
	if (!res.ok) throw new Error(`PUT ${path}: ${res.status}`);
	return res.json();
}

/**
 * @param {string} path
 * @param {AbortSignal} [signal]
 */
async function del(path, signal) {
	const res = await fetch(`${BASE}${path}`, { method: 'DELETE', signal });
	if (!res.ok) throw new Error(`DELETE ${path}: ${res.status}`);
	return res.json();
}

/**
 * @param {string} path
 * @param {any} body
 * @param {AbortSignal} [signal]
 */
async function patch(path, body = {}, signal) {
	const res = await fetch(`${BASE}${path}`, {
		method: 'PATCH',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(body),
		signal,
	});
	if (!res.ok) throw new Error(`PATCH ${path}: ${res.status}`);
	return res.json();
}

// ── Public API ────────────────────────────────

export const api = {
	// Status
	getStatus: (/** @type {AbortSignal} [signal] */ signal) => get('/api/status', signal),

	// Constitution
	getConstitution: (signal) => get('/api/constitution', signal),
	validateConstitution: (signal) => post('/api/constitution/validate', {}, signal),
	getConstitutionPresets: (signal) => get('/api/constitution/presets', signal),
	getConstitutionPreset: (/** @type {string} */ presetId, signal) => get(`/api/constitution/presets/${presetId}`, signal),

	// Architecture
	getArchitecture: (signal) => get('/api/architecture', signal),
	runArchReview: (/** @type {string} */ draft, /** @type {string} */ domain, signal) =>
		post('/api/architecture/review', { architecture_draft: draft, domain_description: domain }, signal),
	acceptArchitecture: (/** @type {string} */ proposed_architecture, signal) =>
		post('/api/architecture/accept', { proposed_architecture }, signal),
	approveArchitecture: (signal) => post('/api/architecture/approve', {}, signal),
	getInvariants: (signal) => get('/api/architecture/invariants', signal),
	updateInvariants: (/** @type {string} */ content, signal) =>
		put('/api/architecture/invariants', { content }, signal),
	getAdrs: (signal) => get('/api/architecture/adrs', signal),
	createAdr: (/** @type {string} */ title, signal) => post('/api/architecture/adrs', { title }, signal),
	updateAdrStatus: (/** @type {number} */ number, /** @type {string} */ status, signal) =>
		patch(`/api/architecture/adrs/${number}/status`, { status }, signal),
	generateAdrs: (signal) => post('/api/architecture/adrs/generate', {}, signal),
	saveAdrContent: (/** @type {number} */ number, /** @type {string} */ content, signal) =>
		put(`/api/architecture/adrs/${number}`, { content }, signal),
	saveConstitution: (/** @type {string} */ content, signal) =>
		put('/api/constitution', { content }, signal),
	saveArchitecture: (/** @type {string} */ content, signal) =>
		put('/api/architecture', { content }, signal),
	applyArchReview: (signal) => post('/api/architecture/apply-review', {}, signal),

	// Dev Plan
	getDevPlan: (signal) => get('/api/devplan', signal),
	generateDevPlan: (signal) => post('/api/devplan/generate', {}, signal),
	getDevPlanMilestones: (signal) => get('/api/devplan/milestones', signal),
	confirmDevPlan: (/** @type {any} */ payload, signal) => post('/api/devplan/confirm', payload, signal),
	updateDevPlan: (/** @type {string} */ guidance, signal) => post('/api/devplan/update', { guidance }, signal),
	confirmDevPlanUpdate: (/** @type {any} */ payload, signal) => post('/api/devplan/confirm-update', payload, signal),
	saveDevPlan: (/** @type {string} */ content, signal) => put('/api/devplan', { content }, signal),

	// Tasks
	getTasks: (signal) => get('/api/tasks', signal),
	getTask: (/** @type {string} */ name, signal) => get(`/api/tasks/${name}`, signal),

	// Phases
	runClarify: (/** @type {string} */ name, signal) => post(`/api/tasks/${name}/clarify`, {}, signal),
	answerClarify: (/** @type {string} */ name, /** @type {any} */ payload, signal) =>
		post(`/api/tasks/${name}/clarify/answer`, payload, signal),
	saveClarifyDraft: (/** @type {string} */ name, /** @type {any[]} */ questions, signal) =>
		put(`/api/tasks/${name}/clarify/draft`, { questions }, signal),
	runPlan: (/** @type {string} */ name, signal) => post(`/api/tasks/${name}/plan`, {}, signal),
	runImplement: (/** @type {string} */ name, /** @type {any} */ payload, signal) =>
		post(`/api/tasks/${name}/implement`, payload, signal),
	applyImplementFile: (/** @type {string} */ name, /** @type {string} */ filepath, /** @type {string} */ content, signal) =>
		post(`/api/tasks/${name}/apply-file`, { filepath, content }, signal),
	completeStage: (/** @type {string} */ name, /** @type {number} */ stage, signal) =>
		post(`/api/tasks/${name}/stage/${stage}/complete`, {}, signal),

	// Tests (structural checks + verify commands)
	runTests: (/** @type {string} */ name, signal) =>
		post(`/api/tasks/${name}/tests`, {}, signal),
	confirmTests: (/** @type {string} */ name, signal) =>
		post(`/api/tasks/${name}/tests/confirm`, {}, signal),
	getVerifyCommands: (/** @type {string} */ name, signal) =>
		get(`/api/tasks/${name}/tests/commands`, signal),
	saveVerifyCommands: (/** @type {string} */ name, /** @type {any[]} */ commands, signal) =>
		put(`/api/tasks/${name}/tests/commands`, { commands }, signal),

	// Fix (conversational bug fixing)
	sendFix: (/** @type {string} */ name, /** @type {string} */ message, /** @type {any[]} */ conversation, signal) =>
		post(`/api/tasks/${name}/fix`, { message, conversation }, signal),
	applyFixFile: (/** @type {string} */ name, /** @type {string} */ filepath, /** @type {string} */ content, signal) =>
		post(`/api/tasks/${name}/fix/apply`, { filepath, content }, signal),
	getFixLog: (/** @type {string} */ name, signal) => get(`/api/tasks/${name}/fix/log`, signal),
	loadFixConversation: (/** @type {string} */ name, signal) => get(`/api/tasks/${name}/fix/conversation`, signal),
	clearFixConversation: (/** @type {string} */ name, signal) => del(`/api/tasks/${name}/fix/conversation`, signal),

	// Config
	getConfig: (signal) => get('/api/config', signal),
	saveConfig: (/** @type {any} */ payload, signal) => put('/api/config', payload, signal),

	// Tokens & Stats
	getTokens: (signal) => get('/api/tokens', signal),
	getStats: (signal) => get('/api/stats', signal),
	getDashboard: (signal) => get('/api/dashboard', signal),
};

// ── WebSocket ─────────────────────────────────

/** @type {WebSocket | null} */
let ws = null;
/** @type {((data: any) => void)[]} */
let listeners = [];
/** @type {number} */
let reconnectAttempts = 0;
/** @type {ReturnType<typeof setTimeout> | null} */
let reconnectTimer = null;

/** @param {(data: any) => void} fn */
export function onWsEvent(fn) {
	listeners.push(fn);
	return () => {
		listeners = listeners.filter((l) => l !== fn);
	};
}

/** @type {(connected: boolean) => void} */
let statusCb = () => {};

/** @param {(connected: boolean) => void} fn */
export function onWsStatus(fn) {
	statusCb = fn;
}

export function connectWs() {
	if (reconnectTimer) {
		clearTimeout(reconnectTimer);
		reconnectTimer = null;
	}

	const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
	ws = new WebSocket(`${proto}//${location.host}/ws`);

	ws.onopen = () => {
		reconnectAttempts = 0;
		statusCb(true);
	};

	ws.onerror = (event) => {
		console.error('[WS] Connection error:', event);
	};

	ws.onclose = () => {
		statusCb(false);

		if (reconnectAttempts < WS_MAX_RECONNECTS) {
			reconnectAttempts++;
			reconnectTimer = setTimeout(connectWs, WS_RECONNECT_DELAY);
		} else {
			console.warn(`[WS] Gave up reconnecting after ${WS_MAX_RECONNECTS} attempts.`);
		}
	};

	ws.onmessage = (e) => {
		try {
			const data = JSON.parse(e.data);
			listeners.forEach((fn) => fn(data));
		} catch (err) {
			console.warn('[WS] Failed to parse message:', err);
		}
	};
}

/** Reset reconnect counter and reconnect (e.g. after user action). */
export function reconnectWs() {
	reconnectAttempts = 0;
	connectWs();
}
