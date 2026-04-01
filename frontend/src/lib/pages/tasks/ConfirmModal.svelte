<script>
	import { X, Loader2 } from 'lucide-svelte';
	import { portal } from '$lib/utils/portal.js';

	let { title = '', message = '', confirmLabel = '', cancelLabel = '', loading = false, onConfirm, onClose } = $props();

	function handleKeydown(e) {
		if (e.key === 'Escape' && !loading) onClose();
	}
</script>

<svelte:window onkeydown={handleKeydown} />

<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
<div class="overlay" use:portal role="dialog" aria-modal="true" aria-label={title} tabindex="-1" onkeydown={handleKeydown} onclick={() => { if (!loading) onClose(); }}>
	<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
	<div class="modal" onclick={(e) => e.stopPropagation()}>
		<div class="modal-header">
			<h3>{title}</h3>
			<button class="close-x" onclick={onClose} disabled={loading}><X size={16} /></button>
		</div>

		<div class="modal-body">
			<p>{message}</p>
		</div>

		<div class="modal-footer">
			<button class="btn" onclick={onClose} disabled={loading}>{cancelLabel}</button>
			<button class="btn btn-danger" onclick={onConfirm} disabled={loading}>
				{#if loading}<Loader2 size={14} class="spin" />{/if}
				{confirmLabel}
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
		width: 26rem;
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

	.modal-header h3 { margin: 0; font-size: 1rem; }

	.close-x {
		background: none;
		border: none;
		color: var(--tx-dim);
		cursor: pointer;
		padding: 0.25rem;
	}
	.close-x:hover { color: var(--tx-bright); }

	.modal-body {
		padding: 1rem;
	}

	.modal-body p {
		font-size: 0.875rem;
		line-height: 1.5;
		color: var(--tx);
	}

	.modal-footer {
		display: flex;
		gap: 0.5rem;
		justify-content: flex-end;
		padding: 0.75rem 1rem;
		border-top: 0.0625rem solid var(--bd);
	}
</style>
