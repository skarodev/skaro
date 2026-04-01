<script>
	import { t } from '$lib/i18n/index.js';
	import { X, Loader2 } from 'lucide-svelte';
	import { portal } from '$lib/utils/portal.js';

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

	function handleKeydown(e) {
		if (e.key === 'Escape') onClose();
		if (e.key === 'Enter' && canSubmit) handleSubmit();
	}
</script>

<svelte:window onkeydown={handleKeydown} />

<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
<div class="overlay" use:portal role="dialog" aria-modal="true" aria-label={$t('task.create_title')} tabindex="-1" onkeydown={handleKeydown} onclick={onClose}>
	<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
	<div class="modal" onclick={(e) => e.stopPropagation()}>
		<div class="modal-header">
			<h3>{$t('task.create_title')}</h3>
			<button class="close-x" onclick={onClose}><X size={16} /></button>
		</div>

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

		<div class="modal-footer">
			<button class="btn" onclick={onClose} disabled={loading}>{$t('task.create_cancel')}</button>
			<button class="btn btn-primary" onclick={handleSubmit} disabled={!canSubmit}>
				{#if loading}<Loader2 size={14} class="spin" />{/if}
				{loading ? $t('task.create_creating') : $t('task.create_submit')}
			</button>
		</div>
	</div>
</div>

<style>
	.overlay {
		position: fixed;
		inset: 0;
		z-index: 1000;
		background: rgba(0, 0, 0, .6);
		backdrop-filter: blur(0.125rem);
		display: flex;
		align-items: center;
		justify-content: center;
	}

	.modal {
		background: var(--bg-deep);
		border: 0.0625rem solid var(--bd2);
		border-radius: var(--r);
		width: 28rem;
		max-width: 90vw;
		box-shadow: 0 0.5rem 2rem rgba(0, 0, 0, .5);
	}

	.modal-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 0.75rem 1rem;
		border-bottom: 0.0625rem solid var(--bd);
	}

	.modal-header h3 {
		margin: 0;
		font-size: 1rem;
	}

	.close-x {
		background: none;
		border: none;
		color: var(--dm);
		cursor: pointer;
		padding: 0.25rem;
	}
	.close-x:hover { color: var(--tx-bright); }

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
		color: var(--dm);
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
		border-color: var(--bd-focus);
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

	.modal-footer {
		display: flex;
		gap: 0.5rem;
		justify-content: flex-end;
		padding: 0.75rem 1rem;
		border-top: 0.0625rem solid var(--bd);
	}
</style>
