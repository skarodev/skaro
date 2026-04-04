<script>
	import { onMount } from 'svelte';
	import { t } from '$lib/i18n/index.js';
	import { api } from '$lib/api/client.js';
	import { addError } from '$lib/stores/logStore.js';
	import { cachedFetch } from '$lib/api/cache.js';
	import { Rocket } from 'lucide-svelte';
	import ProjectIcon from '$lib/ui/icons/ProjectIcon.svelte';
	import RoadmapStepper from './start/RoadmapStepper.svelte';
	import ProjectProgress from './start/ProjectProgress.svelte';
	import GitStatusCard from './start/GitStatusCard.svelte';
	import QuickActions from './start/QuickActions.svelte';
	import PipelineCard from './dashboard/PipelineCard.svelte';
	import TasksOverview from './dashboard/TasksOverview.svelte';
	import LlmConfigCard from './dashboard/LlmConfigCard.svelte';
	import StartSkeleton from './start/StartSkeleton.svelte';

	let data = $state(null);
	let loading = $state(true);
	let error = $state('');

	onMount(async () => {
		try {
			data = await cachedFetch('start', () => api.getDashboard());
		} catch (e) { error = e.message; addError(e.message, 'start'); }
		loading = false;
	});

	let status = $derived(data?.status);

	let activeRoles = $derived.by(() => {
		if (!status?.config?.roles) return [];
		return Object.entries(status.config.roles)
			.filter(([, v]) => v !== null)
			.map(([name, cfg]) => ({ name, ...cfg }));
	});

	/**
	 * Early stage = devplan not confirmed OR no tasks exist.
	 * Once there are confirmed tasks, we switch to the active view.
	 */
	let isEarlyStage = $derived(
		!status?.devplan_confirmed || !status?.tasks?.length
	);
</script>

{#if loading}
	<StartSkeleton />
{:else if error}
	<div class="card"><p style="color:var(--err)">{error}</p></div>
{:else if data}

	{#if isEarlyStage}
		<!-- ═══ Variant A: Early-stage roadmap ═══ -->
		<div class="start-early">
			<div class="start-brand">
				<ProjectIcon size={39} />
				<span class="start-brand-name">Skaro</span>
			</div>
			<div class="start-header">
				<h2><Rocket size={22} /> {$t('start.welcome')}</h2>
				<p class="start-subtitle">{$t('start.welcome_desc')}</p>
			</div>
			<RoadmapStepper {status} />
		</div>
	{:else}
		<!-- ═══ Variant B: Active project ═══ -->
		<div class="start-grid">
			<PipelineCard {status} />

			<ProjectProgress tasks={status?.tasks} />
			<GitStatusCard />

			<TasksOverview tasks={status?.tasks} />
			<QuickActions {status} />

			<LlmConfigCard config={status?.config} roles={activeRoles} />
		</div>
	{/if}

{/if}

<style>
	/* ── Early stage layout ── */

	.start-early {
		max-width: 40rem;
		display: flex;
		flex-direction: column;
		justify-content: center;
		min-height: calc(100vh - 10rem);
	}

	.start-brand {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.5rem;
		margin-bottom: 3rem;
		color: var(--tx-bright);
	}

	.start-brand-name {
		font-size: 1.7rem;
		font-weight: 600;
        color: var(--tx);
	}

	.start-header {
		margin-bottom: 1.5rem;
	}

	.start-header h2 {
		font-size: 1.375rem;
		font-weight: 700;
		color: var(--tx-bright);
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}

	.start-subtitle {
		color: var(--tx-dim);
		font-size: 0.875rem;
		margin-top: 0.25rem;
	}

	/* ── Active project grid ── */

	:global(.main > .start-grid) {
		max-width: 100% !important;
	}

	.start-grid {
		display: grid;
		grid-template-columns: repeat(8, 1fr);
		gap: 1.5rem;
	}

	.start-grid > :global(.card) { margin-bottom: 0; }
	.start-grid > :global(.widget.lg) { grid-column: span 4; }
	.start-grid > :global(.widget.md) { grid-column: span 2; }

	@media (max-width: 1980px) {
		.start-grid > :global(.widget.lg.pipeline-card) { grid-column: span 8; }
	}
</style>
