<script>
	/**
	 * Shared modal wrapper.
	 *
	 * Handles: portal to document.body, overlay, Esc, click-outside.
	 *
	 * Props:
	 *   title     — string for default header (h3 + close button)
	 *   width     — CSS width (default '28rem')
	 *   maxHeight — optional CSS max-height (e.g. '85vh')
	 *   onClose   — required close callback
	 *   loading   — blocks Esc / click-outside when true
	 *   ariaLabel — falls back to title
	 *
	 * Snippets:
	 *   header   — custom header (overrides title prop)
	 *   children — body content
	 *   footer   — optional footer row
	 */
	import { X } from 'lucide-svelte';
	import { portal } from '$lib/utils/portal.js';

	let {
		title = '',
		width = '28rem',
		maxHeight = '',
		onClose,
		loading = false,
		ariaLabel = '',
		header,
		children,
		footer,
	} = $props();

	let label = $derived(ariaLabel || title || 'dialog');

	function handleKeydown(e) {
		if (e.key === 'Escape' && !loading) onClose();
	}

	function handleOverlayClick() {
		if (!loading) onClose();
	}
</script>

<svelte:window onkeydown={handleKeydown} />

<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
<div class="modal-overlay" use:portal role="dialog" aria-modal="true" aria-label={label} tabindex="-1" onkeydown={handleKeydown} onclick={handleOverlayClick}>
	<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
	<div
		class="modal-container"
		style="width: {width};{maxHeight ? ` max-height: ${maxHeight};` : ''}"
		onclick={(e) => e.stopPropagation()}
	>
		<!-- Header -->
		{#if header}
			<div class="modal-header">
				{@render header()}
				<button class="modal-close" onclick={onClose} disabled={loading}><X size={16} /></button>
			</div>
		{:else if title}
			<div class="modal-header">
				<h3>{title}</h3>
				<button class="modal-close" onclick={onClose} disabled={loading}><X size={16} /></button>
			</div>
		{/if}

		<!-- Body -->
		{#if children}
			{@render children()}
		{/if}

		<!-- Footer -->
		{#if footer}
			<div class="modal-footer">
				{@render footer()}
			</div>
		{/if}
	</div>
</div>

<style>
	.modal-overlay {
		position: fixed;
		inset: 0;
		z-index: 1000;
		background: rgba(0, 0, 0, .6);
		backdrop-filter: blur(0.125rem);
		display: flex;
		align-items: center;
		justify-content: center;
	}

	.modal-container {
		background: var(--bg-deep);
		border: 1px solid var(--bd2);
		border-radius: var(--r);
		max-width: 90vw;
		display: flex;
		flex-direction: column;
		box-shadow: 0 0.5rem 2rem rgba(0, 0, 0, .5);
	}

	.modal-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.625rem;
		padding: 0.625rem 1rem;
		border-bottom: 1px solid var(--bd);
		flex-shrink: 0;
	}

	.modal-header h3 {
		margin: 0;
		font-size: 1rem;
		color: var(--tx-bright);
	}

	.modal-close {
		background: none;
		border: none;
		color: var(--tx-dim);
		cursor: pointer;
		padding: 0.25rem;
		flex-shrink: 0;
	}

	.modal-close:hover { color: var(--tx-bright); }
	.modal-close:disabled { opacity: 0.4; cursor: default; }

	.modal-footer {
		display: flex;
		gap: 0.5rem;
		align-items: center;
		padding: 0.625rem 1rem;
		border-top: 1px solid var(--bd);
		flex-shrink: 0;
	}
</style>
