<script>
	import { t } from '$lib/i18n/index.js';
	import { status } from '$lib/stores/statusStore.js';
	import { Loader2, CheckCircle, ListPlus, Eye, Check } from 'lucide-svelte';
	import SpecPreviewModal from './SpecPreviewModal.svelte';

	let {
		proposals = [],
		onConfirm = (/** @type {any[]} */ _tasks) => {},
		confirming = false,
	} = $props();

	let tasks = $state([]);
	let previewTask = $state(null);

	$effect(() => {
		if (proposals?.length) {
			tasks = proposals.map((p, i) => ({ ...p, enabled: true, _idx: i }));
		}
	});

	/** Set of existing task names from the global status store. */
	let existingNames = $derived(
		new Set(($status?.tasks || []).map(t => t.name))
	);

	/** All proposed tasks already exist on disk — show as created. */
	let created = $derived(
		proposals.length > 0 && proposals.every(p => existingNames.has(p.name))
	);

	let enabledTasks = $derived(tasks.filter(t => t.enabled));
	let canConfirm = $derived(enabledTasks.length > 0 && !confirming && !created);

	function toggleTask(idx) {
		tasks = tasks.map((t, i) => i === idx ? { ...t, enabled: !t.enabled } : t);
	}

	function handleConfirm() {
		if (!canConfirm) return;
		onConfirm(enabledTasks.map(t => ({
			name: t.name,
			milestone: t.milestone,
			spec: t.spec || '',
		})));
	}

	function openPreview(task) {
		previewTask = task;
	}
</script>

<div class="proposal-card" class:proposal-created={created}>
	<div class="proposal-header">
		{#if created}
			<Check size={16} />
			<span class="proposal-label">{$t('task_proposal.created_title')}</span>
		{:else}
			<ListPlus size={16} />
			<span class="proposal-label">{$t('task_proposal.title')}</span>
		{/if}
		<span class="proposal-count">{enabledTasks.length}/{tasks.length}</span>
	</div>

	<div class="proposal-body">
		<div class="task-list">
			{#each tasks as task, i}
				<div class="task-row" class:disabled={!task.enabled || created}>
					<label class="task-check">
						<input
							type="checkbox"
							checked={task.enabled}
							onchange={() => toggleTask(i)}
							disabled={confirming || created}
						/>
					</label>
					<div class="task-info">
						<span class="task-name">{task.name}</span>
						<span class="task-milestone">{task.milestone}</span>
					</div>
					{#if task.spec}
						<button
							class="preview-btn"
							onclick={() => openPreview(task)}
							title={$t('task_proposal.preview_spec')}
						>
							<Eye size={14} />
						</button>
					{/if}
				</div>
			{/each}
		</div>
	</div>

	{#if !created}
		<div class="proposal-footer">
			<button class="btn btn-primary" onclick={handleConfirm} disabled={!canConfirm}>
				{#if confirming}<Loader2 size={14} class="spin" />{/if}
				{confirming
					? $t('task_proposal.creating')
					: $t('task_proposal.confirm', { n: enabledTasks.length })}
			</button>
		</div>
	{/if}
</div>

{#if previewTask}
	<SpecPreviewModal
		name={previewTask.name}
		milestone={previewTask.milestone}
		spec={previewTask.spec}
		onClose={() => previewTask = null}
	/>
{/if}

<style>
	.proposal-card {
		border: 0.0625rem solid var(--ac);
		border-radius: var(--r);
		background: var(--bg-deep);
		margin-top: 1rem;
		overflow: hidden;
	}

	.proposal-created {
		border-color: var(--ok);
		opacity: 0.85;
	}

	.proposal-header {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.5rem 0.75rem;
		background: var(--sf);
		border-bottom: 0.0625rem solid var(--bd);
		color: var(--ac);
		font-weight: 600;
		font-size: 0.8125rem;
	}

	.proposal-created .proposal-header {
		color: var(--ok);
	}

	.proposal-count {
		margin-left: auto;
		font-size: 0.75rem;
		font-family: var(--font-ui);
		color: var(--tx-dim);
		font-weight: 400;
	}

	.proposal-body {
		padding: 0.5rem 0.75rem;
	}

	.task-list {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
	}

	.task-row {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.375rem 0.5rem;
		border: 0.0625rem solid var(--bd);
		border-radius: var(--r2);
		font-size: 0.8125rem;
		transition: background 0.1s, opacity 0.1s;
	}

	.task-row:hover {
		background: var(--sf);
	}

	.task-row.disabled {
		opacity: 0.5;
	}

	.task-check {
		display: flex;
		align-items: center;
		flex-shrink: 0;
		cursor: pointer;
	}

	.task-check input[type="checkbox"] {
		accent-color: var(--ac);
		cursor: pointer;
	}

	.task-info {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		flex: 1;
		min-width: 0;
		overflow: hidden;
	}

	.task-name {
		font-weight: 500;
		color: var(--tx-bright);
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.task-milestone {
		font-family: var(--font-ui);
		font-size: 0.6875rem;
		color: var(--tx-dim);
		flex-shrink: 0;
		background: var(--sf);
		padding: 0.0625rem 0.375rem;
		border-radius: 0.25rem;
	}

	.preview-btn {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 1.5rem;
		height: 1.5rem;
		border: none;
		background: none;
		color: var(--tx-dim);
		cursor: pointer;
		border-radius: var(--r2);
		flex-shrink: 0;
		transition: color 0.1s, background 0.1s;
	}

	.preview-btn:hover {
		color: var(--ac);
		background: var(--sf);
	}

	.proposal-footer {
		display: flex;
		justify-content: flex-end;
		padding: 0.5rem 0.75rem;
		border-top: 0.0625rem solid var(--bd);
	}
</style>
