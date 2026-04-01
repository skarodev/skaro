<script>
	import { t } from '$lib/i18n/index.js';
	import MarkdownContent from '$lib/ui/MarkdownContent.svelte';

	/** @type {{ content: string }} */
	let { content = '' } = $props();
</script>

<div class="preview-pane">
	<div class="pane-header">{$t('editor.preview')}</div>
	<div class="pane-body">
		{#if content.trim()}
			<MarkdownContent {content} />
		{:else}
			<p class="empty-hint">{$t('editor.preview_empty')}</p>
		{/if}
	</div>
</div>

<style>
	.preview-pane {
		display: flex;
		flex-direction: column;
		min-width: 0;
		height: 100%;
		overflow: hidden;
	}

	.pane-header {
		font-size: 0.6875rem;
		text-transform: uppercase;
		letter-spacing: 0.0312rem;
		color: var(--tx-dim);
		font-weight: 600;
		padding: 0.375rem 0.75rem;
		border-bottom: 0.0625rem solid var(--bd);
		flex-shrink: 0;
	}

	.pane-body {
		flex: 1;
		overflow-y: auto;
		padding: 0.75rem 1rem;
	}

	.empty-hint {
		color: var(--tx-dim);
		font-style: italic;
		font-size: 0.8125rem;
	}
</style>
