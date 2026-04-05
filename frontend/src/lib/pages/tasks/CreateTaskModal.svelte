<script>
	import { t } from '$lib/i18n/index.js';
	import { Loader2 } from 'lucide-svelte';
	import Modal from '$lib/ui/Modal.svelte';

	let { milestones = [], loading = false, onConfirm, onClose } = $props();

	let name = $state('');
	let selectedMilestone = $state('');
	let newMilestone = $state('');
	let useNewMilestone = $state(false);

	/* Auto-select first existing milestone */
	$effect(() => {
		if (milestones.length && !selectedMilestone && !useNewMilestone) {
			selectedMilestone = milestones[0];
		}
	});

	let milestone = $derived(useNewMilestone ? newMilestone.trim() : selectedMilestone);
	let canSubmit = $derived(name.trim().length > 0 && milestone.length > 0 && !loading);

	function handleSubmit() {
		if (!canSubmit) return;
		onConfirm({ name: name.trim(), milestone });
	}
</script>

<svelte:window onkeydown={(e) => { if (e.key === 'Enter' && canSubmit) handleSubmit(); }} />

<Modal title={$t('task.create_title')} {onClose} {loading}>
	<div class="modal-body">
		<label class="field">
			<span class="field-label">{$t('task.create_name')}</span>
			<input
				type="text"
				bind:value={name}
				placeholder={$t('task.create_name_placeholder')}
				disabled={loading}
			/>
		</label>

		<div class="field">
			<span class="field-label">{$t('task.create_milestone')}</span>
			{#if milestones.length > 0 && !useNewMilestone}
				<select bind:value={selectedMilestone} disabled={loading}>
					{#each milestones as ms}
						<option value={ms}>{ms}</option>
					{/each}
				</select>
				<button class="link-btn" onclick={() => { useNewMilestone = true; }} type="button">
					{$t('task.create_milestone_new')}
				</button>
			{:else}
				<input
					type="text"
					bind:value={newMilestone}
					placeholder={$t('task.create_milestone_placeholder')}
					disabled={loading}
				/>
				{#if milestones.length > 0}
					<button class="link-btn" onclick={() => { useNewMilestone = false; }} type="button">
						← {$t('task.create_milestone')}
					</button>
				{/if}
			{/if}
		</div>
	</div>

	{#snippet footer()}
		<button class="btn" onclick={onClose} disabled={loading}>{$t('task.create_cancel')}</button>
		<button class="btn btn-primary" onclick={handleSubmit} disabled={!canSubmit}>
			{#if loading}<Loader2 size={14} class="spin" />{/if}
			{loading ? $t('task.create_creating') : $t('task.create_submit')}
		</button>
	{/snippet}
</Modal>

<style>
	.modal-body {
		padding: 1rem;
		display: flex;
		flex-direction: column;
		gap: 1rem;
	}

	.field {
		display: flex;
		flex-direction: column;
		gap: 0.375rem;
	}

	.field-label {
		font-size: 0.8125rem;
		color: var(--tx-dim);
		font-weight: 500;
	}

	input, select {
		padding: 0.4375rem 0.625rem;
		border: 0.0625rem solid var(--bd2);
		border-radius: var(--r2);
		background: var(--sf);
		color: var(--tx);
		font-family: inherit;
		font-size: 0.875rem;
	}
	input:focus, select:focus {
		outline: none;
		border-color: var(--ac);
	}

	.link-btn {
		background: none;
		border: none;
		color: var(--ac);
		font-size: 0.75rem;
		cursor: pointer;
		padding: 0;
		text-align: left;
		font-family: inherit;
	}
	.link-btn:hover { text-decoration: underline; }
</style>
