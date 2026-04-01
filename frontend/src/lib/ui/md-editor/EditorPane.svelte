<script>
	import { t } from '$lib/i18n/index.js';

	/** @type {{ value: string, textareaEl?: HTMLTextAreaElement | null }} */
	let { value = $bindable(''), textareaEl = $bindable(null) } = $props();

	function handleKeydown(e) {
		if (e.key === 'Tab') {
			e.preventDefault();
			const el = textareaEl;
			if (!el) return;
			const { selectionStart: s, selectionEnd: end } = el;
			value = value.slice(0, s) + '\t' + value.slice(end);
			requestAnimationFrame(() => {
				el.selectionStart = el.selectionEnd = s + 1;
			});
		}
	}
</script>

<div class="editor-pane">
	<div class="pane-header">{$t('editor.source')}</div>
	<textarea
		class="editor-textarea"
		bind:this={textareaEl}
		bind:value
		onkeydown={handleKeydown}
		spellcheck="false"
		placeholder={$t('editor.placeholder')}
	></textarea>
</div>

<style>
	.editor-pane {
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
		color: var(--dm);
		font-weight: 600;
		padding: 0.375rem 0.75rem;
		border-bottom: 0.0625rem solid var(--bd);
		flex-shrink: 0;
	}

	.editor-textarea {
		flex: 1;
		width: 100%;
		resize: none;
		border: none;
		outline: none;
		background: var(--bg-deep);
		color: var(--tx);
		font-family: var(--font-ui);
		font-size: 0.8125rem;
		line-height: 1.6;
		padding: 0.75rem 1rem;
		tab-size: 4;
		overflow-y: auto;
	}

	.editor-textarea::placeholder {
		color: var(--dm2);
	}
</style>
