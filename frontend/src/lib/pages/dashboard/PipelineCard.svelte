<script>
	import { t } from '$lib/i18n/index.js';
	import { CheckCircle2, Circle, Clock, ChevronRight, FileText } from 'lucide-svelte';

	let { status } = $props();

	let allTasksDone = $derived.by(() => {
		const tasks = status?.tasks;
		if (!tasks || tasks.length === 0) return false;
		return tasks.every(f => f.phases?.tests === 'complete');
	});

	let pipeline = $derived.by(() => {
		if (!status?.initialized) return [];
		return [
			{
				id: 'analytics',
				label: $t('dash.pipe_analytics'),
				done: status.analytics_done,
				active: status.has_spec && !status.analytics_done,
				href: '/analytics',
			},
			{
				id: 'constitution',
				label: $t('dash.pipe_constitution'),
				done: status.constitution_validated,
				active: status.has_constitution && !status.constitution_validated,
				href: '/constitution',
			},
			{
				id: 'architecture',
				label: $t('dash.pipe_architecture'),
				done: status.architecture_reviewed,
				active: status.has_architecture && !status.architecture_reviewed,
				href: '/architecture',
			},
			{
				id: 'adr',
				label: $t('dash.pipe_adr'),
				done: status.architecture_reviewed && (status.adr_count || 0) > 0,
				active: status.architecture_reviewed && (status.adr_count || 0) === 0,
				href: '/adr',
			},
			{
				id: 'devplan',
				label: $t('dash.pipe_devplan'),
				done: status.devplan_confirmed,
				active: status.has_devplan && !status.devplan_confirmed,
				href: '/devplan',
			},
			{
				id: 'tasks',
				label: $t('dash.pipe_tasks'),
				done: allTasksDone,
				active: (status.tasks?.length || 0) > 0 && !allTasksDone,
				href: '/tasks',
			},
			{
				id: 'review',
				label: $t('dash.pipe_review'),
				done: status.review_passed === true,
				active: allTasksDone && status.review_passed !== true,
				href: '/review',
			},
			{
				id: 'cicd',
				label: $t('dash.pipe_cicd'),
				done: status.cicd_done,
				active: status.review_passed === true && !status.cicd_done,
				href: '/cicd',
			},
		];
	});
</script>

<div class="widget lg pipeline-card card">
	<h3>{$t('dash.pipeline')}</h3>
	<div class="pipeline">
		{#each pipeline as step, i}
			<a class="pipe-step" class:done={step.done} class:active={step.active && !step.done} href={step.href}>
				<span class="pipe-icon">
					{#if step.done}
						<CheckCircle2 size={20} />
					{:else if step.active}
						<Clock size={20} />
					{:else}
						<Circle size={20} />
					{/if}
				</span>
				<span class="pipe-label">{step.label}</span>
			</a>
			{#if i < pipeline.length - 1}
				<span class="pipe-arrow"><ChevronRight size={16} /></span>
			{/if}
		{/each}
	</div>
</div>

<style>
	.pipeline-card {
		display: flex;
		flex-direction: column;
		justify-content: center;
	}

	.pipeline {
		display: flex;
		align-items: center;
		gap: 0.25rem;
		margin-top: 0.5rem;
		flex-wrap: wrap;
		row-gap: 0.5rem;
	}

	.pipe-step {
		display: flex;
		align-items: center;
		gap: 0.375rem;
		padding: 0.5rem 0.875rem;
		border-radius: var(--r);
		background: var(--bg2);
		border: 0.0625rem solid var(--bd);
		color: var(--dm);
		font-size: 0.8125rem;
		font-weight: 500;
		text-decoration: none;
		transition: all .15s;
		cursor: pointer;
		white-space: nowrap;
		min-width: 0;
		flex-shrink: 0;
	}

	.pipe-step:hover { background: var(--sf2); border-color: var(--bd2); }

	.pipe-step.done {
		color: var(--gn-bright);
		border-color: rgba(106, 135, 89, .35);
		background: rgba(106, 135, 89, .08);
	}

	.pipe-step.active {
		color: var(--yl);
		border-color: rgba(255, 198, 109, .35);
		background: rgba(255, 198, 109, .08);
	}

	.pipe-icon { display: flex; align-items: center; flex-shrink: 0; }
	.pipe-arrow { color: var(--dm2); display: flex; align-items: center; flex-shrink: 0; }

	@media (max-width: 768px) {
		.pipeline {
			flex-direction: column;
			align-items: stretch;
			gap: 0.375rem;
		}

		.pipe-step {
			justify-content: flex-start;
		}

		.pipe-arrow {
			display: none;
		}
	}
</style>
