<script>
	import { t } from '$lib/i18n/index.js';
	import { page } from '$app/stores';
	import { theme } from '$lib/stores/themeStore.js';
	import { Settings, PanelLeft, Info, BookOpen, ExternalLink } from 'lucide-svelte';
	import LayoutGridAnimated from '$lib/ui/icons/LayoutGridAnimated.svelte';
	import FileTextAnimated from '$lib/ui/icons/FileTextAnimated.svelte';
	import LayersAnimated from '$lib/ui/icons/LayersAnimated.svelte';
	import MapFoldFlipAnimated from '$lib/ui/icons/MapFoldFlipAnimated.svelte';
	import PackageOpenAnimated from '$lib/ui/icons/PackageOpenAnimated.svelte';
	import GitBranchAnimated from '$lib/ui/icons/GitBranchAnimated.svelte';
	import FolderOpenCrossfade from '$lib/ui/icons/FolderOpenCrossfade.svelte';
	import ShieldCheckAnimated from '$lib/ui/icons/ShieldCheckAnimated.svelte';
	import SparklesAnimated from '$lib/ui/icons/SparklesAnimated.svelte';
	import Tooltip from '$lib/ui/Tooltip.svelte';

	const STORAGE_KEY = 'skaro:sidebar-collapsed';

	const mainTabs = [
		{ id: 'dashboard', icon: LayoutGridAnimated, labelKey: 'nav.dashboard' },
		{ id: 'constitution', icon: FileTextAnimated, labelKey: 'nav.constitution' },
		{ id: 'architecture', icon: LayersAnimated, labelKey: 'nav.architecture' },
		{ id: 'adr', icon: FolderOpenCrossfade, labelKey: 'nav.adr' },
		{ id: 'devplan', icon: MapFoldFlipAnimated, labelKey: 'nav.devplan' },
		{ id: 'features', icon: SparklesAnimated, labelKey: 'nav.features', separatorBefore: true },
		{ id: 'tasks', icon: PackageOpenAnimated, labelKey: 'nav.tasks' },
		{ id: 'review', icon: ShieldCheckAnimated, labelKey: 'nav.review' },
		{ id: 'git', icon: GitBranchAnimated, labelKey: 'nav.git' },
	];

	const settingsTab = { id: 'settings', labelKey: 'nav.settings' };

	function readStored() {
		try { return localStorage.getItem(STORAGE_KEY) === '1'; }
		catch { return false; }
	}
	function writeStored(v) {
		try { localStorage.setItem(STORAGE_KEY, v ? '1' : '0'); }
		catch { /* noop */ }
	}

	let collapsed = $state(readStored());
	let currentPath = $derived($page.url.pathname);
	let hoveredTab = $state('');
	let logoSrc = $derived($theme === 'light' ? '/logo-light.svg' : '/logo-dark.svg');

	function toggle() {
		collapsed = !collapsed;
		writeStored(collapsed);
	}

	function isActive(tabId) {
		if (tabId === 'dashboard') return currentPath === '/' || currentPath === '/dashboard';
		if (tabId === 'constitution') return currentPath === '/constitution';
		return currentPath === '/' + tabId || currentPath.startsWith('/' + tabId + '/');
	}
</script>

<nav class="sidebar" class:collapsed>
	<div class="sidebar-header">
		{#if !collapsed}
			<div class="logo-area">
                <a href="/">
				    <img src={logoSrc} alt="Skaro" class="logo-img" />
                </a>
			</div>
		{/if}
		<button class="toggle-btn" onclick={toggle} title={collapsed ? 'Expand' : 'Collapse'}>
			<PanelLeft size={18} strokeWidth={1.5} />
		</button>
	</div>

	<div class="nav">
		{#each mainTabs as tab}
			{@const Icon = tab.icon}
			<Tooltip text={$t(tab.labelKey)} placement="right" disabled={!collapsed}>
				<a
					class="nav-item"
					class:active={isActive(tab.id)}
					class:nav-separator={tab.separatorBefore}
					href="/{tab.id}"
					data-sveltekit-noscroll
					onmouseenter={() => hoveredTab = tab.id}
					onmouseleave={() => hoveredTab = ''}
				>
					<span class="icon"><Icon size={18} active={hoveredTab === tab.id} /></span>
					{#if !collapsed}
						<span class="label">{$t(tab.labelKey)}</span>
					{/if}
				</a>
			</Tooltip>
		{/each}
	</div>

	<!-- About & Docs -->
	<div class="nav-aux">
		<Tooltip text={$t('nav.about')} placement="right" disabled={!collapsed}>
			<a
				class="nav-item"
				class:active={isActive('about')}
				href="/about"
				data-sveltekit-noscroll
			>
				<span class="icon"><Info size={18} strokeWidth={1.5} /></span>
				{#if !collapsed}
					<span class="label">{$t('nav.about')}</span>
				{/if}
			</a>
		</Tooltip>

		<Tooltip text={$t('nav.docs')} placement="right" disabled={!collapsed}>
			<a
				class="nav-item"
				href="https://docs.skaro.dev"
				target="_blank"
				rel="noopener noreferrer"
			>
				<span class="icon"><BookOpen size={18} strokeWidth={1.5} /></span>
				{#if !collapsed}
					<span class="label">{$t('nav.docs')}</span>
					<span class="ext-icon"><ExternalLink size={13} strokeWidth={1.75} /></span>
				{/if}
			</a>
		</Tooltip>
	</div>

	<div class="nav-bottom">
		<Tooltip text={$t(settingsTab.labelKey)} placement="right" disabled={!collapsed}>
			<a
				class="nav-item"
				class:active={isActive(settingsTab.id)}
				href="/{settingsTab.id}"
				data-sveltekit-noscroll
			>
				<span class="icon"><Settings size={18} strokeWidth={1.5} /></span>
				{#if !collapsed}
					<span class="label">{$t(settingsTab.labelKey)}</span>
				{/if}
			</a>
		</Tooltip>
	</div>
</nav>

<style>
	.sidebar {
		width: 18rem;
		background: var(--bg-soft);
		border-right: 1px solid var(--bd);
		display: flex;
		flex-direction: column;
		flex-shrink: 0;
		user-select: none;
		transition: width .2s ease;
		overflow: hidden;
	}

	.sidebar.collapsed {
		width: 3.5rem;
	}

	/* ── Header ── */
	.sidebar-header {
		padding: 0.875rem 0.625rem;
		display: flex;
		align-items: center;
		min-height: 3.25rem;
	}

	.logo-area {
		display: flex;
		align-items: center;
		flex: 1;
		min-width: 0;
		padding-left: 0.75rem;
	}

	.logo-img {
		width: auto;
		height: 18px;
		display: block;
		flex-shrink: 0;
	}

	.toggle-btn {
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
		transition: color .15s, background .15s, transform .2s ease;
		margin-left: auto;
	}

	.toggle-btn:hover {
		color: var(--tx-bright);
		background: var(--sf);
	}

	.collapsed .toggle-btn {
		transform: scaleX(-1);
		margin: 0 auto;
	}

	/* ── Nav ── */
	.nav {
		flex: 1;
		padding: 0.25rem 0.625rem;
		overflow-y: auto;
		gap: 0.0625rem;
		display: flex;
		flex-direction: column;
	}

	.collapsed .nav {
		padding: 0.25rem 0.375rem;
		align-items: center;
	}

	/* ── Settings (bottom) ── */
	.nav-bottom {
		padding: 0.5rem 0.625rem;
		border-top: 0.0625rem solid var(--bd);
		flex-shrink: 0;
	}

	.collapsed .nav-bottom {
		padding: 0.5rem 0.375rem;
		display: flex;
		justify-content: center;
	}

	.nav-item {
		display: flex;
		border-radius: var(--r);
		align-items: center;
		gap: 0.5rem;
		padding: 0.5rem;
		cursor: pointer;
		color: var(--tx-bright);
		font-size: 1rem;
		width: 100%;
		border: none;
		background: none;
		text-align: left;
		font-family: inherit;
		border-left: 0.125rem solid transparent;
		transition: background .1s;
		text-decoration: none;
		white-space: nowrap;
		overflow: hidden;
	}

	.collapsed .nav-item {
		width: 2.25rem;
		padding: 0.4375rem 0;
		justify-content: center;
		border-left: none;
		gap: 0;
	}

	.nav-item:hover {
		background: var(--bg-deep);
	}

	.nav-separator {
		margin-top: 1rem;
	}

	.nav-item.active {
		background: var(--bg-deep);
		color: var(--tx-bright);
	}

	.icon {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 1.25rem;
		flex-shrink: 0;
	}

	.label {
		overflow: hidden;
		text-overflow: ellipsis;
		flex: 1;
		min-width: 0;
	}

	/* ── Nav aux: About + Docs ── */
	.nav-aux {
		margin-top: 1rem;
		padding: 0.5rem 0.625rem;
		gap: 0.075rem;
		display: flex;
		flex-direction: column;
		border-top: 0.0625rem solid var(--bd);
		flex-shrink: 0;
	}

	.collapsed .nav-aux {
		padding: 0.25rem 0.375rem;
		align-items: center;
	}

	/* External-link arrow */
	.ext-icon {
		margin-left: auto;
		display: flex;
		align-items: center;
		color: var(--tx-dim);
		flex-shrink: 0;
		opacity: 0.7;
	}

	.nav-item:hover .ext-icon {
		opacity: 1;
	}

</style>
