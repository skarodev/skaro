<script>
	import { onMount } from 'svelte';
	import { t } from '$lib/i18n/index.js';
	import { api } from '$lib/api/client.js';
	import { addError } from '$lib/stores/logStore.js';
	import { cachedFetch } from '$lib/api/cache.js';
	import { BarChart3, FileCode, Cpu, Users, Zap, Loader } from 'lucide-svelte';
	import { fmt } from '$lib/utils/format.js';
	import FileTypesChart from '$lib/ui/FileTypesChart.svelte';
	import StatsTable from '$lib/ui/StatsTable.svelte';
	import SummaryCard from './dashboard/SummaryCard.svelte';
	import RecentLogCard from './dashboard/RecentLogCard.svelte';

	let stats = $state(null);
	let loading = $state(true);
	let error = $state('');

	onMount(async () => {
		try {
			stats = await cachedFetch('stats', () => api.getStats());
		} catch (e) { error = e.message; addError(e.message, 'stats'); }
		loading = false;
	});
</script>

<div class="main-header">
	<h2>{$t('stats.title')}</h2>
	<p>{$t('stats.subtitle')}</p>
</div>

{#if loading}
	<div class="loading-text"><Loader size={14} class="spin" /> {$t('app.loading')}</div>
{:else if error}
	<div class="card"><p style="color:var(--err)">{error}</p></div>
{:else if stats}
	<!-- Summary cards -->
	<div class="summary-grid">
		<SummaryCard icon={Zap} value={fmt(stats.tokens?.total_tokens)} label={$t('stats.total_tokens')} />
		<SummaryCard icon={Cpu} value={stats.total_requests} label={$t('stats.total_requests')} />
		<SummaryCard icon={FileCode} value={stats.total_files} label={$t('stats.total_files')} />
		<SummaryCard icon={BarChart3} value={fmt(stats.total_lines)} label={$t('stats.total_lines')} />
	</div>

	<div class="grid-2">
		<StatsTable icon={Cpu} title={$t('stats.by_phase')} data={stats.by_phase} />
		<StatsTable icon={FileCode} title={$t('stats.by_task')} data={stats.by_task} />
		<StatsTable icon={Cpu} title={$t('stats.by_model')} data={stats.by_model} />
		<StatsTable icon={Users} title={$t('stats.by_role')} data={stats.by_role} />
	</div>

	<!-- Project files by type -->
	<div class="card">
		<h3><FileCode size={16} /> {$t('stats.project_files')}</h3>
		<FileTypesChart files={stats.files} totalFiles={stats.total_files} />
	</div>

	<!-- Recent log -->
	{#if stats.log_entries?.length}
		<RecentLogCard entries={stats.log_entries} />
	{/if}
{/if}

<style>
	.summary-grid {
		display: grid;
		grid-template-columns: repeat(4, 1fr);
		gap: 0.75rem;
		margin-bottom: 1rem;
	}

	.grid-2 {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 0.75rem;
		margin-bottom: 1rem;
	}

	/* Override .widget sizing from StatsTable — full width inside grid-2 */
	.grid-2 > :global(.widget) {
		grid-column: span 1;
	}
</style>
