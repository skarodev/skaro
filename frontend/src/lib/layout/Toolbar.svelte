<script>
	import { t } from '$lib/i18n/index.js';
	import { page } from '$app/stores';
	import { status } from '$lib/stores/statusStore.js';
	import { chatPanelOpen, toggleChatPanel } from '$lib/stores/chatPanelStore.js';
	import { MessageSquare, PanelRightClose, PanelRightOpen } from 'lucide-svelte';
	import Tooltip from '$lib/ui/Tooltip.svelte';

	/** Map of route segment → i18n key. Covers every sidebar entry. */
	const NAV_KEYS = {
		start: 'nav.start',
		constitution: 'nav.constitution',
		architecture: 'nav.architecture',
		adr: 'nav.adr',
		devplan: 'nav.devplan',
		features: 'nav.features',
		tasks: 'nav.tasks',
		review: 'nav.review',
		git: 'nav.git',
		stats: 'nav.stats',
		settings: 'nav.settings',
		about: 'nav.about',
	};

	/** Pages that have a chat context available. */
	const NO_CHAT_PAGES = new Set(['start', 'git', 'stats', 'settings', 'about']);

	/** Check if current page supports chat panel. */
	let hasChatContext = $derived.by(() => {
		const parts = $page.url.pathname.split('/').filter(Boolean);
		const section = parts[0] || 'start';
		return !NO_CHAT_PAGES.has(section);
	});

	let projectName = $derived($status?.project_name || '');

	let currentTab = $derived.by(() => {
		const parts = $page.url.pathname.split('/').filter(Boolean);
		return parts[0] || 'start';
	});

	/**
	 * Build breadcrumb segments from the current URL.
	 * Each segment: { label, href?, isLast }
	 */
	let crumbs = $derived.by(() => {
		const parts = $page.url.pathname.split('/').filter(Boolean);
		const section = parts[0] || 'start';
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
	{#if currentTab === 'start'}
	<div class="project-title">
		{projectName || 'Skaro'}
	</div>
	{:else}
	<nav class="breadcrumb" aria-label="Breadcrumb">
		<a class="crumb" href="/start">{projectName || 'Skaro'}</a>
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
		<span class="chat-toggle-wrap">
		<Tooltip text={$t('chat_panel.toggle')} placement="bottom">
			<button
				class="chat-toggle"
				class:active={$chatPanelOpen}
				onclick={toggleChatPanel}
			>
			<span class="chat-label">{$t('chat_panel.label')}</span>
			{#if $chatPanelOpen}
				<PanelRightClose size={16} strokeWidth={1.5} />
			{:else}
				<PanelRightOpen size={16} strokeWidth={1.5} />
			{/if}
		</button>
		</Tooltip>
		</span>
	{/if}
</div>

<style>
	.toolbar-strip {
		height: 2.875rem;
		display: flex;
		align-items: center;
		padding: 0 1.5rem;
		font-size: 0.9rem;
		color: var(--tx-dim);
		gap: 0.25rem;
		flex-shrink: 0;
        border-bottom: solid 1px var(--bd);
        background: var(--bg-soft);
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

	.chat-toggle-wrap {
		margin-left: auto;
		display: inline-flex;
	}

	.chat-toggle {
		display: flex;
		align-items: center;
		gap: 0.375rem;
		height: 2rem;
		padding: 0 0.5rem;
		border: none;
		background: none;
		color: var(--tx-dim);
		cursor: pointer;
		border-radius: var(--r2);
		flex-shrink: 0;
		transition: color .12s, background .12s;
	}

	.chat-label {
		font-size: 0.8125rem;
		white-space: nowrap;
	}

	.chat-toggle:hover {
		color: var(--tx-bright);
		background: var(--bg-deep);
	}

	.chat-toggle.active {
		color: var(--ac);
	}
</style>
