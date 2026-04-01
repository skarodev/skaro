<script>
	import { t } from '$lib/i18n/index.js';
	import { Loader2, CheckCircle, X, FileText, FolderOpen } from 'lucide-svelte';

	let { proposal = {}, confirming = false, onConfirm, onDiscard } = $props();

	let title = $state('');
	let description = $state('');
	let tasks = $state([]);
	let includeAdr = $state(false);

	$effect(() => {
		if (proposal) {
			title = proposal.title || '';
			description = proposal.description || '';
			tasks = (proposal.tasks || []).map((t, i) => ({ ...t, enabled: true, _idx: i }));
			includeAdr = !!proposal.adr?.title;
		}
	});

	let enabledTasks = $derived(tasks.filter(t => t.enabled));
	let canConfirm = $derived(title.trim().length > 0 && enabledTasks.length > 0 && !confirming);

	function toggleTask(idx) {
		tasks = tasks.map((t, i) => i === idx ? { ...t, enabled: !t.enabled } : t);
	}

	function handleConfirm() {
		if (!canConfirm) return;
		const payload = {
			title: title.trim(),
			description: description.trim(),
			plan: proposal.plan || '',
			tasks: enabledTasks.map(t => ({
				name: t.name,
				milestone: t.milestone,
				description: t.description || '',
				spec: t.spec || '',
			})),
			adr: includeAdr && proposal.adr?.title ? proposal.adr : null,
		};
		onConfirm(payload);
	}
</script>

<div class="proposal-card">
	<div class="proposal-header">
		<CheckCircle size={16} />
		<span class="proposal-label">{$t('feature.proposal_title')}</span>
	</div>

	<div class="proposal-body">
		<label class="field">
			<span class="field-label">{$t('feature.prop_name')}</span>
			<input
				type="text"
				bind:value={title}
				placeholder={$t('feature.prop_name_placeholder')}
				disabled={confirming}
			/>
		</label>

		<label class="field">
			<span class="field-label">{$t('feature.prop_description')}</span>
			<textarea
				bind:value={description}
				rows="2"
				disabled={confirming}
			></textarea>
		</label>

		{#if tasks.length > 0}
			<div class="field">
				<span class="field-label">{$t('feature.prop_tasks')} ({enabledTasks.length}/{tasks.length})</span>
				<div class="task-list">
					{#each tasks as task, i}
						<label class="task-item" class:disabled={!task.enabled}>
							<input
								type="checkbox"
								checked={task.enabled}
								onchange={() => toggleTask(i)}
								disabled={confirming}
							/>
							<span class="task-name">{task.name}</span>
							<span class="task-milestone">{task.milestone}</span>
							{#if task.description}
								<span class="task-desc">{task.description}</span>
							{/if}
						</label>
					{/each}
				</div>
			</div>
		{/if}

		{#if proposal.adr?.title}
			<div class="field">
				<label class="adr-toggle">
					<input type="checkbox" bind:checked={includeAdr} disabled={confirming} />
					<FolderOpen size={14} />
					<span>{$t('feature.prop_adr')}: {proposal.adr.title}</span>
				</label>
			</div>
		{/if}
	</div>

	<div class="proposal-footer">
		<button class="btn" onclick={onDiscard} disabled={confirming}>{$t('feature.prop_discard')}</button>
		<button class="btn btn-primary" onclick={handleConfirm} disabled={!canConfirm}>
			{#if confirming}<Loader2 size={14} class="spin" />{/if}
			{confirming ? $t('feature.prop_creating') : $t('feature.prop_confirm')}
		</button>
	</div>
</div>

<style>
	.proposal-card {
		border: 0.0625rem solid var(--ac);
		border-radius: var(--r);
		background: var(--bg-deep);
		margin-bottom: 1rem;
		overflow: hidden;
	}

	.proposal-header {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.625rem 1rem;
		background: var(--sf);
		border-bottom: 0.0625rem solid var(--bd);
		color: var(--ac);
		font-weight: 600;
		font-size: 0.875rem;
	}

	.proposal-body {
		padding: 1rem;
		display: flex;
		flex-direction: column;
		gap: 0.875rem;
	}

	.field {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
	}

	.field-label {
		font-size: 0.8125rem;
		color: var(--dm);
		font-weight: 500;
	}

	input[type="text"], textarea {
		padding: 0.4375rem 0.625rem;
		border: 0.0625rem solid var(--bd2);
		border-radius: var(--r2);
		background: var(--sf);
		color: var(--tx);
		font-family: inherit;
		font-size: 0.875rem;
		resize: vertical;
	}
	input[type="text"]:focus, textarea:focus {
		outline: none;
		border-color: var(--bd-focus);
	}

	.task-list {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
	}

	.task-item {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.375rem 0.5rem;
		border: 0.0625rem solid var(--bd);
		border-radius: var(--r2);
		font-size: 0.8125rem;
		cursor: pointer;
		transition: background .1s, opacity .1s;
	}
	.task-item:hover { background: var(--sf); }
	.task-item.disabled { opacity: 0.5; }

	.task-item input[type="checkbox"] {
		accent-color: var(--ac);
		cursor: pointer;
		flex-shrink: 0;
	}

	.task-name { font-weight: 500; color: var(--tx-bright); }
	.task-milestone {
		font-family: var(--font-ui);
		font-size: 0.75rem;
		color: var(--dm);
		margin-left: auto;
	}
	.task-desc {
		display: none;
	}

	.adr-toggle {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		font-size: 0.8125rem;
		cursor: pointer;
		color: var(--tx);
	}
	.adr-toggle input { accent-color: var(--ac); cursor: pointer; }

	.proposal-footer {
		display: flex;
		gap: 0.5rem;
		justify-content: flex-end;
		padding: 0.75rem 1rem;
		border-top: 0.0625rem solid var(--bd);
	}
</style>
