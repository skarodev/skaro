<script>
	import { t } from '$lib/i18n/index.js';
	import { Sun, Moon } from 'lucide-svelte';

	let { theme = $bindable('dark') } = $props();
</script>

<div class="card">
	<h3>{$t('settings.theme')}</h3>
	<div class="theme-tabs">
		<button class="tab" class:active={theme === 'dark'} onclick={() => theme = 'dark'}>
			<Moon size={14} />
			{$t('settings.theme_dark')}
		</button>
		<button class="tab" class:active={theme === 'light'} onclick={() => theme = 'light'}>
			<Sun size={14} />
			{$t('settings.theme_light')}
		</button>
	</div>
</div>

<style>
	.theme-tabs {
		display: flex;
		gap: .5rem;
	}

	.tab {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.375rem 0.875rem;
		border: solid 0.0625rem var(--bg-high);
		border-radius: var(--r);
		background: transparent;
		color: var(--dm);
		cursor: pointer;
		font-size: 0.8125rem;
		font-family: inherit;
		transition: .12s;
	}

	.tab:hover {
		color: var(--tx);
	}

	.tab.active {
		color: var(--ac);
		border: solid 0.0625rem var(--ac);
		font-weight: 600;
	}
</style>
