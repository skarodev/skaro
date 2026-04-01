<script>
	import { t } from '$lib/i18n/index.js';
	import { BadgeCheck, Boxes } from 'lucide-svelte';
	import PhaseBar from '$lib/ui/PhaseBar.svelte';
	/** @type {{ task: any, href: string }} */
	let { task, href } = $props();
	let pct = $derived(
		task.total_stages > 0
			? Math.round((task.current_stage / task.total_stages) * 100)
			: 0
	);
	let allComplete = $derived(
		task.phases && Object.values(task.phases).length > 0
			&& Object.values(task.phases).every((s) => s === 'complete')
	);
	let showProgress = $derived(
		task.current_phase === 'implement' && task.total_stages > 0
	);
	let milestoneLabel = $derived(
		(task.milestone || '')
			.replace(/^\d+-/, '')
			.replace(/-/g, ' ')
			.replace(/\b\w/g, (c) => c.toUpperCase()) || '—'
	);
</script>

<a class="card task-item" {href} draggable="false">
	<div class="task-head">
		<h3>
			{#if allComplete}
				<span class="status-icon complete"><BadgeCheck size={20} /></span>
			{:else}
				<span class="status-icon wip"><Boxes size={20} /></span>
			{/if}
			{task.name}
		</h3>
		<span class="milestone-badge">{milestoneLabel}</span>
	</div>
	<PhaseBar phases={task.phases} />
	{#if showProgress}
		<div class="progress-label" class:progress-complete={pct >= 100}>
			{$t('task.implement_progress')}: {task.current_stage}/{task.total_stages} ({pct}%)
		</div>
		<div class="progress-bar"><div class="progress-fill" style="width: {pct}%"></div></div>
	{/if}
</a>

<style>
	.task-item {
		cursor: pointer;
		transition: box-shadow .2s;
		display: block;
		text-decoration: none;
		color: inherit;
	}

	.task-item:hover {
		box-shadow: 0 .5rem 2rem rgba(0, 0, 0, .1);
		text-decoration: none;
	}

	.task-head {
		display: flex;
		justify-content: space-between;
		align-items: center;
	}

	h3 {
		margin: 0;
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}

	.status-icon {
		display: flex;
		align-items: center;
		justify-content: center;
		flex-shrink: 0;
	}

	.status-icon.complete {
		color: var(--ok);
	}

	.status-icon.wip {
		color: var(--tx-bright);
	}

	.milestone-badge {
		font-size: 0.6875rem;
		padding: 0.125rem 0.5rem;
		border-radius: 0.25rem;
		background: color-mix(in srgb, var(--ac) 12%, transparent);
		border: none;
		color: var(--ac);
		font-family: var(--font-ui);
		letter-spacing: 0.019rem;
		white-space: nowrap;
	}

	.progress-bar {
		height: 0.1875rem;
		background: var(--bd);
		border-radius: 0.125rem;
		margin-top: 0.25rem;
		overflow: hidden;
	}

	.progress-fill {
		height: 100%;
		background: var(--ac);
		border-radius: 0.125rem;
		transition: width .3s;
	}

	.progress-label {
		font-size: 0.75rem;
		color: var(--tx-dim);
		margin-top: 0.25rem;
		font-family: var(--font-ui);
	}

	.progress-label.progress-complete {
		color: var(--ac);
		font-weight: 600;
	}
</style>
