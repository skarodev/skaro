<script>
	import { t } from '$lib/i18n/index.js';
	import { ArrowLeft, BadgeCheck, Boxes, Trash2 } from 'lucide-svelte';
	import PhaseBar from '$lib/ui/PhaseBar.svelte';

	let { taskName, phases = {}, currentPhase = '', currentStage = 0, totalStages = 0, onBack, onDelete = undefined } = $props();

	let pct = $derived(totalStages > 0 ? Math.round((currentStage / totalStages) * 100) : 0);
	let allComplete = $derived(
		phases && Object.values(phases).length > 0
			&& Object.values(phases).every((s) => s === 'complete')
	);
	let showProgress = $derived(currentPhase === 'implement' && totalStages > 0);
</script>

<button class="back" type="button" onclick={onBack}><ArrowLeft size={14} /> {$t('task.back')}</button>

<div class="main-header">
	<h2>
		{#if allComplete}
			<span class="status-icon complete"><BadgeCheck size={24} /></span>
		{:else}
			<span class="status-icon wip"><Boxes size={24} /></span>
		{/if}
		{$t('task.detail_title', { name: taskName })}
	</h2>
	{#if onDelete}
		<button class="delete-task-btn" onclick={onDelete} title={$t('task.delete_btn')}>
			<Trash2 size={16} /> {$t('task.delete_btn')}
		</button>
	{/if}
</div>
<PhaseBar {phases} />

{#if showProgress}
	<div class="progress-label" class:progress-complete={pct >= 100}>
		{$t('task.implement_progress')}: {currentStage}/{totalStages} ({pct}%)
	</div>
	<div class="progress-bar"><div class="progress-fill" style="width: {pct}%"></div></div>
{/if}

<style>
	.back {
		display: inline-flex; align-items: center; gap: 0.25rem;
		color: var(--tx-dim); font-size: 0.8125rem; cursor: pointer; margin-bottom: 0.75rem;
		background: none; border: none; padding: 0; font-family: inherit;
	}
	.back:hover { color: var(--ac); }

	.main-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 1rem;
	}

	.status-icon { display: inline-flex; align-items: center; flex-shrink: 0; }
	.status-icon.complete { color: var(--ok); }
	.status-icon.wip { color: var(--tx-bright); }

	.delete-task-btn {
		display: inline-flex;
		align-items: center;
		gap: 0.3125rem;
		padding: 0.25rem 0.625rem;
		border: 0.0625rem solid var(--bd2);
		border-radius: var(--r2);
		background: none;
		color: var(--tx-dim);
		font-size: 0.8125rem;
		font-family: inherit;
		cursor: pointer;
		flex-shrink: 0;
		transition: color .15s, border-color .15s, background .15s;
	}
	.delete-task-btn:hover {
		color: var(--err);
		border-color: var(--err);
		background: color-mix(in srgb, var(--err) 8%, transparent);
	}

	.progress-bar { height: 0.1875rem; background: var(--bd); border-radius: 0.125rem; margin-top: 0.25rem; overflow: hidden; }
	.progress-fill { height: 100%; background: var(--ac); border-radius: 0.125rem; transition: width .3s; }
	.progress-label { font-size: 0.75rem; color: var(--tx-dim); margin-top: 0.375rem; font-family: var(--font-ui); }
	.progress-label.progress-complete { color: var(--ac); font-weight: 600; }
</style>
