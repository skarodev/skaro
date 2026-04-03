<script>
	import { t } from '$lib/i18n/index.js';
	import { page } from '$app/stores';
	import { status } from '$lib/stores/statusStore.js';
	import { chatPanelOpen, toggleChatPanel } from '$lib/stores/chatPanelStore.js';
	import { MessageSquare, PanelRightClose, PanelRightOpen } from 'lucide-svelte';

	/** Map of route segment → i18n key. Covers every sidebar entry. */
	const NAV_KEYS = {
		dashboard: 'nav.dashboard',
		constitution: 'nav.constitution',
		architecture: 'nav.architecture',
		adr: 'nav.adr',
		devplan: 'nav.devplan',
		features: 'nav.features',
		tasks: 'nav.tasks',
		review: 'nav.review',
		git: 'nav.git',
		settings: 'nav.settings',
		about: 'nav.about',
	};

	/** Pages that have a chat context available. */
	const NO_CHAT_PAGES = new Set(['dashboard', 'git', 'settings', 'about']);

	/** Check if current page supports chat panel. */
	let hasChatContext = $derived.by(() => {
		const parts = $page.url.pathname.split('/').filter(Boolean);
		const section = parts[0] || 'dashboard';
		return !NO_CHAT_PAGES.has(section);
	});

	let projectName = $derived($status?.project_name || '');

	let currentTab = $derived.by(() => {
		const parts = $page.url.pathname.split('/').filter(Boolean);
		return parts[0] || 'dashboard';
	});

	/**
	 * Build breadcrumb segments from the current URL.
	 * Each segment: { label, href?, isLast }
	 */
	let crumbs = $derived.by(() => {
		const parts = $page.url.pathname.split('/').filter(Boolean);
		const section = parts[0] || 'dashboard';
		const navKey = NAV_KEYS[section];
		const sectionLabel = navKey ? $t(navKey) : section;

		// Sub-page slug (e.g. tasks/[name] or features/[slug])
		const subPage = parts[1] ? decodeURIComponent(parts[1]) : null;

		const result = [];

		if (subPage) {
			// Section is a link when there's a deeper page
			result.push({ label: sectionLabel, href: `/${section}` });
			result.push({ label: subPage, href: null, isLast: true });
		} else {
			result.push({ label: sectionLabel, href: null, isLast: true });
		}

		return result;
	});
</script>

<div class="toolbar-strip">
	{#if currentTab === 'dashboard'}
	<div class="project-title">
		{projectName || 'Skaro'}
	</div>
	{:else}
	<nav class="breadcrumb" aria-label="Breadcrumb">
		<a class="crumb" href="/dashboard">{projectName || 'Skaro'}</a>
		{#each crumbs as crumb}
			<span class="sep">›</span>
			{#if crumb.href}
				<a class="crumb" href={crumb.href}>{crumb.label}</a>
			{:else}
				<span class="crumb last">{crumb.label}</span>
			{/if}
		{/each}
	</nav>
	{/if}
	{#if hasChatContext}
		<div class="chat-area">
			<span class="chat-label">{$t('chat_panel.label')}</span>
			<button
				class="chat-toggle"
				class:active={$chatPanelOpen}
				onclick={toggleChatPanel}
				title={$t('chat_panel.toggle')}
			>
				{#if $chatPanelOpen}
					<PanelRightClose size={16} strokeWidth={1.5} />
				{:else}
					<PanelRightOpen size={16} strokeWidth={1.5} />
				{/if}
			</button>
		</div>
	{/if}
</div>

<style>
	.toolbar-strip {
		height: 2.875rem;
		display: flex;
		align-items: center;
		padding: 0 1rem;
		font-size: 0.9375rem;
		color: var(--tx-dim);
		gap: 0.25rem;
		flex-shrink: 0;
	}

	.breadcrumb {
		display: flex;
		align-items: center;
		gap: 0.375rem;
	}

	.project-title {
		font-weight: 600;
		color: var(--tx-bright);
		font-size: 1rem;
	}

	.sep {
		color: var(--tx-dim);
	}

	a.crumb {
		color: var(--tx-dim);
		text-decoration: none;
		transition: color 0.12s;
	}

	a.crumb:hover {
		color: var(--tx-bright);
	}

	.last {
		color: var(--tx);
	}

	.chat-area {
		margin-left: auto;
		display: flex;
		align-items: center;
		gap: 0.25rem;
		flex-shrink: 0;
	}

	.chat-label {
		font-size: 0.8125rem;
		color: var(--tx-dim);
		font-family: var(--font-ui);
		white-space: nowrap;
	}

	.chat-toggle {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 2rem;
		height: 2rem;
		border: none;
		background: none;
		color: var(--tx-dim);
		cursor: pointer;
		border-radius: var(--r2);
		flex-shrink: 0;
		transition: color .12s, background .12s;
	}

	.chat-toggle:hover {
		color: var(--tx-bright);
		background: var(--sf);
	}

	.chat-toggle.active {
		color: var(--ac);
	}
</style>
