import { writable } from 'svelte/store';

const THEME_KEY = 'skaro-theme';
const ACCENT_KEY = 'skaro-accent';
const VALID_THEMES = ['dark', 'light'];
const DEFAULT_ACCENT = '#d05e52';
const isBrowser = typeof window !== 'undefined';

/** Preset accent colors. */
export const ACCENT_PRESETS = [
	{ id: 'blue',    label: 'accent.blue',    hex: '#44a7f2' },
	{ id: 'pink',    label: 'accent.pink',    hex: '#fc4cb0' },
	{ id: 'cyan',    label: 'accent.cyan',    hex: '#00abad' },
	{ id: 'carrot',  label: 'accent.carrot',  hex: '#d05e52' },
	{ id: 'lilac',   label: 'accent.lilac',   hex: '#b65bfc' },
	{ id: 'green',   label: 'accent.green',   hex: '#6ad902' },
	{ id: 'yellow',  label: 'accent.yellow',  hex: '#d98900' },
];

function detectTheme() {
	if (!isBrowser) return 'dark';
	try {
		const saved = localStorage.getItem(THEME_KEY);
		if (saved && VALID_THEMES.includes(saved)) return saved;
	} catch { /* noop */ }
	return 'dark';
}

function detectAccent() {
	if (!isBrowser) return DEFAULT_ACCENT;
	try {
		const saved = localStorage.getItem(ACCENT_KEY);
		if (saved && /^#[0-9a-fA-F]{6}$/.test(saved)) return saved;
	} catch { /* noop */ }
	return DEFAULT_ACCENT;
}

export const theme = writable(detectTheme());
export const accentColor = writable(detectAccent());

/** @param {string} value */
export function setTheme(value) {
	if (!VALID_THEMES.includes(value)) return;
	theme.set(value);
	if (isBrowser) {
		try { localStorage.setItem(THEME_KEY, value); } catch { /* noop */ }
		applyTheme(value);
	}
}

/** @param {string} hex */
export function setAccentColor(hex) {
	if (!/^#[0-9a-fA-F]{6}$/.test(hex)) return;
	accentColor.set(hex);
	if (isBrowser) {
		try { localStorage.setItem(ACCENT_KEY, hex); } catch { /* noop */ }
		applyAccent(hex);
	}
}

/** Apply data-theme attribute to <html>. */
export function applyTheme(value) {
	if (!isBrowser) return;
	document.documentElement.setAttribute('data-theme', value);
}

/** Apply accent color as CSS custom property on :root. */
export function applyAccent(hex) {
	if (!isBrowser) return;
	const s = document.documentElement.style;
	s.setProperty('--ac', hex);
	const r = parseInt(hex.slice(1, 3), 16);
	const g = parseInt(hex.slice(3, 5), 16);
	const b = parseInt(hex.slice(5, 7), 16);
	s.setProperty('--sf-hover', `rgba(${r}, ${g}, ${b}, 0.10)`);
}

/** Initialize both theme and accent on app start. */
export function initTheme() {
	applyTheme(detectTheme());
	applyAccent(detectAccent());
}
