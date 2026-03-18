<script>
	import '../app.css';
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import { t } from '$lib/i18n/index.js';
	import { api, connectWs, onWsEvent, onWsStatus } from '$lib/api/client.js';
	import { status, wsConnected, taskDetail, updateInfo } from '$lib/stores/statusStore.js';
	import { addLog, startLlm, addLlmChunk, endLlm } from '$lib/stores/logStore.js';
	import { cachedFetch, invalidate } from '$lib/api/cache.js';
	import { setProviderLabels } from '$lib/ui/icons/providers.js';
	import Sidebar from '$lib/layout/Sidebar.svelte';
	import Toolbar from '$lib/layout/Toolbar.svelte';
	import BottomPanel from '$lib/layout/BottomPanel.svelte';
	import StatusBar from '$lib/layout/StatusBar.svelte';

	let error = $state('');
	let { children } = $props();
	let statusValue = $state(null);

	// Derive selected task from URL for WS-triggered reloads
	let selectedTask = $derived.by(() => {
		const parts = $page.url.pathname.split('/').filter(Boolean);
		return parts[0] === 'tasks' && parts[1] ? decodeURIComponent(parts[1]) : null;
	});

	// ── Dynamic browser title ──
	const TAB_NAV_KEYS = {
		dashboard: 'nav.dashboard',
		analytics: 'nav.analytics',
		constitution: 'nav.constitution',
		architecture: 'nav.architecture',
		adr: 'nav.adr',
		devplan: 'nav.devplan',
		tasks: 'nav.tasks',
		review: 'nav.review',
		cicd: 'nav.cicd',
		git: 'nav.git',
		settings: 'nav.settings',
	};

	let appName = $derived($status?.project_name || 'Skaro');

	let pageTitle = $derived.by(() => {
		const parts = $page.url.pathname.split('/').filter(Boolean);
		const section = parts[0] || 'dashboard';
		const navKey = TAB_NAV_KEYS[section];
		const label = navKey ? $t(navKey) : section;
		if (section === 'tasks' && parts[1]) {
			return `${appName} / ${label} / ${decodeURIComponent(parts[1])}`;
		}
		return `${appName} / ${label}`;
	});

	$effect(() => {
		document.title = pageTitle;
	});

	// Keep a local reference to status for the template
	status.subscribe((v) => { statusValue = v; });

	onMount(() => {
		loadStatus();
		loadUpdateCheck();
		connectWs();
		onWsStatus((c) => wsConnected.set(c));
		onWsEvent((data) => {
			// LLM activity events
			if (data.event === 'llm:start') {
				startLlm(data.phase || '');
				return;
			}
			if (data.event === 'llm:chunk') {
				addLlmChunk(data.text || '');
				return;
			}
			if (data.event === 'llm:complete') {
				endLlm();
				return;
			}

			// Regular events
			if (data.event) {
				addLog(`${data.event}${data.task ? ': ' + data.task : ''}${data.phase ? ' → ' + data.phase : ''}`);
				invalidate('status');
				loadStatus();
				if (selectedTask) {
					api.getTask(selectedTask).then((d) => taskDetail.set(d)).catch(() => {});
				}
			}
		});
	});

	async function loadStatus() {
		try {
			const data = await cachedFetch('status', () => api.getStatus(), 5000);
			status.set(data);
			if (data?._provider_labels) setProviderLabels(data._provider_labels);
			error = '';
		} catch (e) {
			error = e.message;
		}
	}

	async function loadUpdateCheck() {
		try {
			const data = await api.getUpdateCheck(false);
			updateInfo.set(data);
		} catch {
			// Non-critical — silently ignore
		}
	}
</script>

<div class="app">
	<Sidebar />
	<div class="main-wrapper">
		<Toolbar />
		<main class="main">
			{#if error}
				<div class="alert alert-warn">{error}</div>
			{:else if !statusValue}
				<div class="center-msg">{$t('app.loading')}</div>
			{:else if !statusValue.initialized}
				<div class="center-msg">
					<p>{$t('app.not_initialized')}</p>
					<p><code>{$t('app.not_initialized_cmd')}</code></p>
				</div>
			{:else}
				{@render children()}
			{/if}
		</main>
		<BottomPanel />
		<StatusBar />
	</div>
</div>

<style>
	.app {
		display: flex;
		height: 100vh;
		position: relative;
	}

	.main-wrapper {
		flex: 1;
		display: flex;
		flex-direction: column;
		min-width: 0;
		overflow: hidden;
	}

	.main {
		flex: 1;
		overflow-y: auto;
		padding: 0 1.5rem;
		background: var(--bg);
		min-height: 0;
	}

	.main > :global(*) {
		max-width: 100%;
		padding: 0 5%;
		margin-left: auto;
		margin-right: auto;
	}

	.main > :global(.page-with-tabs) {
		max-width: 100%;
		padding: 0 5%;
	}

	.main > :global(.page-wide) {
		max-width: 100%;
		padding: 0 5%;
	}

	.center-msg {
		text-align: center;
		padding: 3.75rem 1.25rem;
		color: var(--dm);
	}
</style>
