<script>
	import { t } from '$lib/i18n/index.js';
	import { page } from '$app/stores';
	import { status, wsConnected, updateInfo } from '$lib/stores/statusStore.js';
	import { Cpu, ArrowUpCircle } from 'lucide-svelte';

	const TAB_ROLES = {
		constitution: null,
		architecture: 'architect',
		adr: 'architect',
		devplan: 'architect',
		tasks: 'coder',
		settings: null,
	};

	let currentTab = $derived.by(() => {
		const parts = $page.url.pathname.split('/').filter(Boolean);
		return parts[0] || 'dashboard';
	});

	function getRoleInfo(s, tab) {
		if (!s?.config) return '—';
		const roleName = TAB_ROLES[tab];
		const cfg = s.config;
		if (roleName && cfg.roles?.[roleName]) {
			const r = cfg.roles[roleName];
			const label = $t('settings.role_' + roleName);
			return `${label}: ${r.provider} / ${r.model}`;
		}
		const label = $t('status.role_default');
		return `${label}: ${cfg.llm_provider} / ${cfg.llm_model}`;
	}

	let hasUpdate = $derived($updateInfo?.has_update === true);
	let latestVersion = $derived($updateInfo?.latest_version ?? '');
	let docsUrl = $derived($updateInfo?.docs_url ?? 'https://docs.skaro.dev/cli/update');
</script>

<div class="status-bar">
	<div class="status-item model-info">
		<Cpu size={11} />
		<span>{getRoleInfo($status, currentTab)}</span>
	</div>
	<div class="status-right">
		{#if hasUpdate}
			<a
				class="status-item update-badge"
				href={docsUrl}
				target="_blank"
				rel="noopener noreferrer"
				title={$t('status.update_tooltip', { version: latestVersion })}
			>
				<ArrowUpCircle size={11} />
				<span>{$t('status.update_available', { version: latestVersion })}</span>
			</a>
		{/if}
		<span class="status-item ws-status">
			<span class="status-dot" class:off={!$wsConnected}></span>
			<span>{$wsConnected ? $t('status.connected') : $t('status.disconnected')}</span>
		</span>
	</div>
</div>

<style>
	.status-bar {
		height: 1.375rem;
		background: var(--ac2);
		display: flex;
		align-items: center;
		padding: 0 0.625rem;
		font-size: 0.75rem;
		color: #fff;
		flex-shrink: 0;
		gap: 1rem;
		user-select: none;
	}

	.status-item {
		display: flex;
		align-items: center;
		gap: 0.25rem;
	}

	.status-right {
		margin-left: auto;
		display: flex;
		align-items: center;
	}

	.model-info {
		opacity: .85;
		overflow: hidden;
		white-space: nowrap;
		text-overflow: ellipsis;
		min-width: 0;
		flex: 1;
	}

	.ws-status {
		opacity: .85;
	}

	.update-badge {
		background: rgba(187, 181, 41, .2);
		padding: 0 0.5rem;
		border-radius: 0.25rem;
		color: #f0e040;
		text-decoration: none;
		transition: background .15s;
		cursor: pointer;
		line-height: 1.25rem;
	}

	.update-badge:hover {
		background: rgba(187, 181, 41, .35);
	}

	.status-dot {
		width: 0.375rem;
		height: 0.375rem;
		border-radius: 50%;
		background: #00de39;
		flex-shrink: 0;
	}

	.status-dot.off {
		background: #ff4200;
	}
</style>
