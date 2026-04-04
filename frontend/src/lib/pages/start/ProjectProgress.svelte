<script>
	import { t } from '$lib/i18n/index.js';
	import { TrendingUp, Milestone } from 'lucide-svelte';

	let { tasks = [] } = $props();

	function isTaskDone(task) {
		return ['clarify', 'plan', 'implement', 'tests'].every(k => task.phases?.[k] === 'complete');
	}

	let doneCount = $derived(tasks.filter(isTaskDone).length);
	let totalCount = $derived(tasks.length);
	let pct = $derived(totalCount > 0 ? Math.round((doneCount / totalCount) * 100) : 0);

	/** Group tasks by milestone and compute per-milestone progress */
	let milestones = $derived.by(() => {
		const map = {};
		for (const task of tasks) {
			const ms = task.milestone || '—';
			if (!map[ms]) map[ms] = { name: ms, done: 0, total: 0 };
			map[ms].total++;
			if (isTaskDone(task)) map[ms].done++;
		}
		return Object.values(map);
	});
</script>

<div class="card proj-progress">
	<div class="section-head">
		<h3><TrendingUp size={16} /> {$t('start.project_progress')}</h3>
		<span class="pct-label">{pct}%</span>
	</div>

	<!-- Main progress bar -->
	<div class="bar-track">
		<div class="bar-fill" style="width: {pct}%"></div>
	</div>
	<div class="bar-legend">
		<span>{doneCount} / {totalCount} {$t('start.tasks_done')}</span>
	</div>

	<!-- Per-milestone breakdown -->
	{#if milestones.length > 1}
		<div class="ms-list">
			{#each milestones as ms}
				{@const msPct = ms.total > 0 ? Math.round((ms.done / ms.total) * 100) : 0}
				<div class="ms-row">
					<span class="ms-icon"><Milestone size={13} /></span>
					<span class="ms-name">{ms.name}</span>
					<div class="ms-bar-track">
						<div class="ms-bar-fill" style="width: {msPct}%"></div>
					</div>
					<span class="ms-stat">{ms.done}/{ms.total}</span>
				</div>
			{/each}
		</div>
	{/if}
</div>

<style>
	.proj-progress {
		grid-column: span 4;
	}

	.pct-label {
		font-size: 1.25rem;
		font-weight: 700;
		color: var(--tx-bright);
		font-family: var(--font-ui);
	}

	/* ── Main bar ── */

	.bar-track {
		width: 100%;
		height: 0.5rem;
		background: var(--bg-deep);
		border-radius: 0.25rem;
		overflow: hidden;
	}

	.bar-fill {
		height: 100%;
		background: var(--ok);
		border-radius: 0.25rem;
		transition: width .4s ease;
		min-width: 2px;
	}

	.bar-legend {
		font-size: 0.75rem;
		color: var(--tx-dim);
		margin-top: 0.375rem;
		font-family: var(--font-ui);
	}

	/* ── Per-milestone rows ── */

	.ms-list {
		margin-top: 0.875rem;
		display: flex;
		flex-direction: column;
		gap: 0.375rem;
	}

	.ms-row {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}

	.ms-icon {
		display: flex;
		align-items: center;
		color: var(--tx-dim);
		flex-shrink: 0;
	}

	.ms-name {
		font-size: 0.75rem;
		color: var(--tx);
		min-width: 5rem;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.ms-bar-track {
		flex: 1;
		height: 0.25rem;
		background: var(--bg-deep);
		border-radius: 0.125rem;
		overflow: hidden;
	}

	.ms-bar-fill {
		height: 100%;
		background: var(--ok);
		border-radius: 0.125rem;
		transition: width .3s ease;
		min-width: 1px;
	}

	.ms-stat {
		font-size: 0.6875rem;
		color: var(--tx-dim);
		font-family: var(--font-ui);
		flex-shrink: 0;
		min-width: 2rem;
		text-align: right;
	}
</style>
