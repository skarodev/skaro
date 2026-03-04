<script>
	import { onMount } from 'svelte';
	import { t } from '$lib/i18n/index.js';
	import { api } from '$lib/api/client.js';
	import { addError } from '$lib/stores/logStore.js';
	import { cachedFetch } from '$lib/api/cache.js';
	import { Zap, Cpu, FileCode, BarChart3, Users } from 'lucide-svelte';
	import FileTypesChart from '$lib/ui/FileTypesChart.svelte';
	import { fmt } from '$lib/utils/format.js';
	import PipelineCard from './dashboard/PipelineCard.svelte';
	import SummaryCard from './dashboard/SummaryCard.svelte';
	import TasksOverview from './dashboard/TasksOverview.svelte';
	import LlmConfigCard from './dashboard/LlmConfigCard.svelte';
	import StatsTable from '$lib/ui/StatsTable.svelte';
	import RecentLogCard from './dashboard/RecentLogCard.svelte';
	import DashboardSkeleton from './dashboard/DashboardSkeleton.svelte';

	let data = $state(null);
	let loading = $state(true);
	let error = $state('');

	onMount(async () => {
		try {
			data = await cachedFetch('dashboard', () => api.getDashboard());
		} catch (e) { error = e.message; addError(e.message, 'dashboard'); }
		loading = false;
	});

	let status = $derived(data?.status);
	let stats = $derived(data?.stats);

	let activeRoles = $derived.by(() => {
		if (!status?.config?.roles) return [];
		return Object.entries(status.config.roles)
			.filter(([, v]) => v !== null)
			.map(([name, cfg]) => ({ name, ...cfg }));
	});
</script>

{#if loading}
	<DashboardSkeleton />
{:else if error}
	<div class="card"><p style="color:var(--rd)">{error}</p></div>
{:else if data}
	<div class="dash-grid">

		<!-- Row 1: pipeline + 4× summary -->
		<PipelineCard {status} />
		<SummaryCard icon={Zap} value={fmt(stats?.tokens?.total_tokens)} label={$t('stats.total_tokens')} />
		<SummaryCard icon={Cpu} value={stats?.total_requests || 0} label={$t('stats.total_requests')} />
		<SummaryCard icon={FileCode} value={stats?.total_files || 0} label={$t('stats.total_files')} />
		<SummaryCard icon={BarChart3} value={fmt(stats?.total_lines)} label={$t('stats.total_lines')} />

		<!-- Row 2: tasks overview + files by type -->
		<TasksOverview tasks={status?.tasks} />

		<div class="widget lg card">
			<h3><FileCode size={16} /> {$t('stats.project_files')}</h3>
			{#if stats?.total_files > 0}
				<FileTypesChart files={stats.files} totalFiles={stats.total_files} />
			{:else}
				<p class="empty-hint">{$t('dash.no_data')}</p>
			{/if}
		</div>

		<!-- Row 3: LLM config + by model + by role -->
		<LlmConfigCard config={status?.config} roles={activeRoles} />
		<StatsTable icon={Cpu} title={$t('stats.by_model')} data={stats?.by_model} />
		<StatsTable icon={Users} title={$t('stats.by_role')} data={stats?.by_role} />

		<!-- Row 4: recent log + by phase + by task -->
		<RecentLogCard entries={stats?.log_entries} />
		<StatsTable icon={Cpu} title={$t('stats.by_phase')} data={stats?.by_phase} />
		<StatsTable icon={FileCode} title={$t('stats.by_task')} data={stats?.by_task} />

	</div>
{/if}

<style>
	:global(.main > .dash-header),
	:global(.main > .loading-text),
	:global(.main > .dash-grid) {
		max-width: 100% !important;
	}

	.dash-grid {
		display: grid;
		grid-template-columns: repeat(8, 1fr);
		gap: 1.5rem;
	}

	.dash-grid > :global(.card) { margin-bottom: 0; }
	.dash-grid > :global(.widget.lg) { grid-column: span 4; }
	.dash-grid > :global(.widget.md) { grid-column: span 2; }
	.dash-grid > :global(.widget.sm) { grid-column: span 1; }

	@media (max-width: 1980px) {
		.dash-grid > :global(.widget.lg.pipeline-card) { grid-column: span 8; }
		.dash-grid > :global(.widget.sm) { grid-column: span 2; }
	}
</style>
