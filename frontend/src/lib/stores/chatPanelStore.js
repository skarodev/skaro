/**
 * Chat panel (right sidebar) state store.
 *
 * Persists open/closed to localStorage so the panel remembers
 * its state between page reloads.
 */
import { writable } from 'svelte/store';

const STORAGE_KEY = 'skaro:chat-panel-open';
const WIDTH_KEY = 'skaro:chat-panel-width';

const DEFAULT_WIDTH = 420;
const MIN_WIDTH = 420;
const MAX_WIDTH_VW = 0.5; // 50vw

function readBool(key, fallback) {
	try {
		const v = localStorage.getItem(key);
		return v === null ? fallback : v === '1';
	} catch {
		return fallback;
	}
}

function readNumber(key, fallback) {
	try {
		const v = localStorage.getItem(key);
		if (v === null) return fallback;
		const n = parseInt(v, 10);
		return Number.isFinite(n) ? n : fallback;
	} catch {
		return fallback;
	}
}

/** Whether the chat panel is open. */
export const chatPanelOpen = writable(readBool(STORAGE_KEY, false));

chatPanelOpen.subscribe((v) => {
	try {
		localStorage.setItem(STORAGE_KEY, v ? '1' : '0');
	} catch {
		/* noop */
	}
});

/** Panel width in pixels. */
export const chatPanelWidth = writable(readNumber(WIDTH_KEY, DEFAULT_WIDTH));

chatPanelWidth.subscribe((v) => {
	try {
		localStorage.setItem(WIDTH_KEY, String(v));
	} catch {
		/* noop */
	}
});

export function toggleChatPanel() {
	chatPanelOpen.update((v) => !v);
}

export function openChatPanel() {
	chatPanelOpen.set(true);
}

export function closeChatPanel() {
	chatPanelOpen.set(false);
}

/**
 * Extra metadata for the current chat context.
 * Pages can write here to pass additional info (e.g. selected ADR number).
 * @type {import('svelte/store').Writable<Record<string, any>>}
 */
export const chatContextMeta = writable({});

/** Update context metadata (merges with existing). */
export function setChatContextMeta(meta) {
	chatContextMeta.update((prev) => ({ ...prev, ...meta }));
}

/** Clear context metadata. */
export function clearChatContextMeta() {
	chatContextMeta.set({});
}

export { MIN_WIDTH, MAX_WIDTH_VW, DEFAULT_WIDTH };
