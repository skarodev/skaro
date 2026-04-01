<script>
	import { t } from '$lib/i18n/index.js';

	let { task = {}, index = 0 } = $props();
</script>

<div class="plan-task">
	<div class="pf-head">
		<h4>{task.name || 'task-' + (index + 1)}</h4>
		{#if task.priority}<span class="prio">{$t('devplan.priority')}: {task.priority}</span>{/if}
	</div>
	{#if task.description}<p class="pf-desc">{task.description}</p>{/if}
	{#if task.dependencies?.length}<p class="pf-deps">{$t('devplan.depends')}: {task.dependencies.join(', ')}</p>{/if}
</div>

<style>
	.plan-task {
		border: 0.0625rem solid var(--bd);
		border-radius: var(--r);
		padding: 0.625rem 0.875rem;
		margin-bottom: 0.5rem;
		background: var(--bg-deep);
	}

	.plan-task h4 {
		font-size: 0.875rem;
		color: var(--tx-bright);
		margin: 0;
	}

	.pf-head {
		display: flex;
		justify-content: space-between;
	}

	.pf-desc {
		font-size: 0.8125rem;
		color: var(--dm);
		margin: 0.125rem 0 0;
	}

	.pf-deps {
		font-size: 0.75rem;
		color: var(--dm2);
		margin-top: 0.125rem;
	}

	.prio {
		font-size: 0.6875rem;
		color: var(--or);
		font-family: var(--font-ui);
	}
</style>
