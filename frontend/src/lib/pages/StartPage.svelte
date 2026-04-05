<script>
	import { onMount } from 'svelte';
	import { t } from '$lib/i18n/index.js';
	import { api } from '$lib/api/client.js';
	import { addError } from '$lib/stores/logStore.js';
	import { cachedFetch } from '$lib/api/cache.js';
	import { Rocket, GitBranch, FileUp, FileWarning, ArrowRight } from 'lucide-svelte';
	import ProjectIcon from '$lib/ui/icons/ProjectIcon.svelte';
	import RoadmapStepper from './start/RoadmapStepper.svelte';
	import KanbanBoard from './start/KanbanBoard.svelte';
	import StartSkeleton from './start/StartSkeleton.svelte';

	const TASK_PHASES = ['clarify', 'plan', 'implement', 'tests'];

	let data = $state(null);
	let loading = $state(true);
	let error = $state('');
	let gitData = $state(null);

	onMount(async () => {
		try {
			const [dashboard, git] = await Promise.all([
				cachedFetch('start', () => api.getDashboard()),
				api.getGitStatus().catch(() => null),
			]);
			data = dashboard;
			gitData = git;
		} catch (e) { error = e.message; addError(e.message, 'start'); }
		loading = false;
	});

	let status = $derived(data?.status);

	/**
	 * Early stage = devplan not confirmed OR no tasks exist.
	 * Once there are confirmed tasks, we switch to the kanban view.
	 */
	let isEarlyStage = $derived(
		!status?.devplan_confirmed || !status?.tasks?.length
	);

	/** First incomplete task — entry point to continue work. */
	let activeTask = $derived.by(() => {
		const tasks = status?.tasks || [];
		return tasks.find(t =>
			!TASK_PHASES.every(k => t.phases?.[k] === 'complete')
		) || null;
	});

	/** Git counts. */
	let stagedCount = $derived(gitData?.files?.filter(f => f.status === 'staged').length || 0);
	let changedCount = $derived(gitData?.files?.filter(f => f.status !== 'staged').length || 0);
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
		<!-- ═══ Variant B: Active project — Kanban board ═══ -->
		<div class="start-kanban">
			<div class="kb-toolbar">
				{#if gitData}
					<a class="kb-git" href="/git">
						<GitBranch size={14} />
						<span class="mono">{gitData.branch || '—'}</span>
						{#if stagedCount > 0}
							<span class="status-badge status-badge-ok"><FileUp size={11} /> {stagedCount}</span>
						{/if}
						{#if changedCount > 0}
							<span class="status-badge status-badge-warn"><FileWarning size={11} /> {changedCount}</span>
						{/if}
					</a>
				{/if}
				{#if activeTask}
					<a class="btn btn-sm kb-continue" href="/tasks/{encodeURIComponent(activeTask.name)}">
						{$t('start.action_current_task')} <ArrowRight size={13} />
					</a>
				{/if}
			</div>
			<KanbanBoard tasks={status?.tasks} />
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

	/* ── Kanban layout — full width ── */

	:global(.main > .start-kanban) {
		max-width: 100% !important;
	}

	/* ── Toolbar ── */

	.kb-toolbar {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.75rem;
		margin-bottom: 1rem;
	}

	.kb-git {
		display: inline-flex;
		align-items: center;
		gap: 0.375rem;
		color: var(--tx-dim);
		font-size: 0.8125rem;
		text-decoration: none;
		transition: color .15s;
	}

	.kb-git:hover {
		color: var(--tx-bright);
	}

	.kb-git .mono {
		font-family: var(--font-ui);
		color: var(--tx);
	}

	.kb-git .status-badge {
		display: inline-flex;
		align-items: center;
		gap: 0.2rem;
	}

	.status-badge-warn {
		background: color-mix(in srgb, var(--warn) 12%, transparent);
		color: var(--warn);
	}

	.kb-continue {
		border-color: color-mix(in srgb, var(--ac) 40%, transparent);
		background: color-mix(in srgb, var(--ac) 8%, transparent);
		color: var(--ac);
		margin-left: auto;
	}

	.kb-continue:hover {
		background: color-mix(in srgb, var(--ac) 14%, transparent);
		border-color: color-mix(in srgb, var(--ac) 55%, transparent);
	}
</style>
