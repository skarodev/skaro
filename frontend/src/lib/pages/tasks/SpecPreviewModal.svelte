<script>
	import { t } from '$lib/i18n/index.js';
	import { renderMarkdown } from '$lib/utils/markdown.js';
	import Modal from '$lib/ui/Modal.svelte';

	let { name = '', milestone = '', spec = '', onClose } = $props();
</script>

<Modal {onClose} width="50rem" maxHeight="80vh" ariaLabel={name}>
	{#snippet header()}
		<div class="spec-header">
			<span class="spec-name">{name}</span>
			<span class="spec-milestone">{milestone}</span>
		</div>
	{/snippet}

	<div class="spec-scroll">
		<div class="spec-content">{@html renderMarkdown(spec)}</div>
	</div>

	{#snippet footer()}
		<button class="btn" onclick={onClose}>{$t('fix.close')}</button>
	{/snippet}
</Modal>

<style>
	.spec-header {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		flex: 1;
		min-width: 0;
	}

	.spec-name {
		font-family: var(--font-ui);
		font-size: 0.875rem;
		font-weight: 600;
		color: var(--tx-bright);
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.spec-milestone {
		font-family: var(--font-ui);
		font-size: 0.75rem;
		color: var(--tx-dim);
		flex-shrink: 0;
	}

	.spec-scroll {
		overflow: auto;
		flex: 1;
		min-height: 0;
		padding: 1.25rem;
	}

	.spec-content {
		font-size: 0.875rem;
		line-height: 1.6;
		color: var(--tx);
	}

	.spec-content :global(h1) { font-size: 1.2rem; color: var(--tx-bright); }
	.spec-content :global(h2) { font-size: 1.1rem; margin: 0.75rem 0 0.25rem; color: var(--tx-bright); }
	.spec-content :global(h3) { font-size: 1rem; margin: 0.5rem 0 0.25rem; color: var(--tx-bright); }
	.spec-content :global(p) { margin: 0.25rem 0; }
	.spec-content :global(ul), .spec-content :global(ol) { margin: 0.25rem 0 0.25rem 1.25rem; }
	.spec-content :global(li) { margin: 0.125rem 0; }
	.spec-content :global(code) {
		background: rgb(from var(--ac) r g b / 0.05);
		border-radius: var(--r);
		padding: 0 0.2rem;
		color: var(--ac);
		font-size: 0.85rem;
	}
	.spec-content :global(pre) {
		background: var(--bg-deep);
		border-radius: var(--r);
		padding: 0.625rem 0.875rem;
		overflow-x: auto;
		font-size: 0.85rem;
		margin: 0.5rem 0;
	}
	.spec-content :global(pre code) {
		background: none; padding: 0; border-radius: 0; color: inherit;
	}
</style>
