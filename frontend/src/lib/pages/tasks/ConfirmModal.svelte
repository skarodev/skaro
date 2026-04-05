<script>
	import { Loader2 } from 'lucide-svelte';
	import Modal from '$lib/ui/Modal.svelte';

	let { title = '', message = '', confirmLabel = '', cancelLabel = '', loading = false, onConfirm, onClose } = $props();
</script>

<Modal {title} {onClose} {loading} width="26rem">
	<div class="modal-body">
		<p>{message}</p>
	</div>

	{#snippet footer()}
		<button class="btn" onclick={onClose} disabled={loading}>{cancelLabel}</button>
		<button class="btn btn-danger" onclick={onConfirm} disabled={loading}>
			{#if loading}<Loader2 size={14} class="spin" />{/if}
			{confirmLabel}
		</button>
	{/snippet}
</Modal>

<style>
	.modal-body {
		padding: 1rem;
	}

	.modal-body p {
		font-size: 0.875rem;
		line-height: 1.5;
		color: var(--tx);
	}
</style>
