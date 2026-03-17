<script>
	import { t } from '$lib/i18n/index.js';
	import { ArrowUp, Square, Cpu, Crosshair } from 'lucide-svelte';

	let {
		message = $bindable(''),
		loading = false,
		tokenDisplay = '',
		modelDisplay = '',
		placeholder = '',
		scopeCount = 0,
		showScope = false,
		onSend = () => {},
		onCancel = () => {},
		onScopeClick = () => {},
	} = $props();

	let inputFocused = $state(false);
	let textareaEl = $state(null);

	function fitHeight(el) {
		el.style.height = 'auto';
		const maxH = parseFloat(getComputedStyle(el).maxHeight) || Infinity;
		el.style.height = Math.min(el.scrollHeight, maxH) + 'px';
	}

	function autoResize(e) {
		fitHeight(e.target);
	}

	function resetHeight() {
		if (textareaEl) {
			textareaEl.style.height = 'auto';
		}
	}

	function handleKeydown(e) {
		if (e.key === 'Enter') {
			if (e.shiftKey || e.ctrlKey || e.metaKey) {
				// Insert newline manually (browser doesn't do it for Ctrl/Cmd+Enter)
				e.preventDefault();
				const el = textareaEl;
				if (el) {
					const start = el.selectionStart;
					const end = el.selectionEnd;
					message = message.substring(0, start) + '\n' + message.substring(end);
					// Wait for Svelte to update the DOM, then restore cursor
					requestAnimationFrame(() => {
						el.selectionStart = el.selectionEnd = start + 1;
						fitHeight(el);
					});
				}
				return;
			}
			e.preventDefault();
			doSend();
		}
	}

	function doSend() {
		onSend();
		resetHeight();
	}
</script>

<div class="composebox" class:composebox-focus={inputFocused}>
	<textarea
		class="compose-input"
		placeholder={placeholder || $t('fix.placeholder')}
		bind:value={message}
		bind:this={textareaEl}
		onkeydown={handleKeydown}
		onfocus={() => inputFocused = true}
		onblur={() => inputFocused = false}
		oninput={autoResize}
		disabled={loading}
	></textarea>
	<div class="compose-bar">
		<div class="bar-spacer">
			{#if showScope}
				<button class="scope-pill" onclick={onScopeClick}>
					<Crosshair size={12} />
					{#if scopeCount > 0}
						<span class="scope-label">{$t('scope.n_files', { n: scopeCount })}</span>
					{:else}
						<span class="scope-label scope-empty">{$t('scope.no_scope')}</span>
					{/if}
				</button>
			{/if}
		</div>
		{#if modelDisplay}
			<span class="model-info"><Cpu size={11} /> {modelDisplay}</span>
		{/if}
		{#if loading}
			<button
				class="cancel-circle"
				onclick={onCancel}
			>
				<Square size={12} fill="currentColor" strokeWidth={0} />
			</button>
		{:else}
			<button
				class="send-circle"
				disabled={!message.trim()}
				onclick={doSend}
			>
				<ArrowUp size={16} />
			</button>
		{/if}
	</div>
</div>
<div class="token-estimate">{tokenDisplay}</div>

<style>
	.composebox {
		width: 100%;
		border: 0.0625rem solid var(--bd);
		border-radius: 1.5rem;
		background: var(--bg3);
		box-shadow: 0 .3rem .7rem rgba(0, 0, 0, .05);
		transition: all .15s;
		flex-shrink: 0;
	}

	.composebox:hover {
		border-color: var(--bd2);
		box-shadow: 0 .5rem 1rem rgba(0, 0, 0, .1);
	}

	.composebox-focus {
		border-color: var(--bd2);
		box-shadow: 0 .5rem 1rem rgba(0, 0, 0, .1);
	}

	.compose-input {
		display: block;
		width: 100%;
		border: none;
		background: transparent;
		outline: none;
		color: var(--tx-bright);
		font-size: 1rem;
		font-family: inherit;
		padding: 1rem 1.3rem .3rem;
		resize: none;
		min-height: 5rem;
		max-height: 50vh;
		line-height: 1.5;
	}

	.compose-input::placeholder {
		color: var(--dm);
	}

	.compose-input:disabled {
		opacity: .5;
	}

	.compose-bar {
		display: flex;
		align-items: center;
		padding: 0.375rem 0.625rem 0.625rem 1rem;
	}

	.bar-spacer {
		flex: 1;
		display: flex;
		align-items: center;
	}

	.scope-pill {
		display: inline-flex;
		align-items: center;
		gap: 0.3rem;
		padding: 0.1875rem 0.625rem;
		border: 0.0625rem solid var(--bd);
		border-radius: 1rem;
		background: transparent;
		color: var(--dm);
		font-size: 0.6875rem;
		font-family: var(--font-ui);
		cursor: pointer;
		transition: all 0.12s;
		white-space: nowrap;
	}

	.scope-pill:hover {
		border-color: var(--ac);
		color: var(--ac);
		background: rgba(88, 157, 246, 0.06);
	}

	.scope-label { line-height: 1; }
	.scope-empty { font-style: italic; }

	.token-estimate {
		font-size: 0.75rem;
		color: var(--dm);
		font-family: var(--font-ui);
		text-align: center;
		padding: .5rem;
	}

	.model-info {
		display: flex;
		align-items: center;
		gap: 0.25rem;
		font-size: 0.75rem;
		color: var(--dm);
		font-family: var(--font-ui);
		margin-right: 0.625rem;
	}

	.send-circle {
		width: 2rem;
		height: 2rem;
		border-radius: 50%;
		background: var(--ac);
		color: #fff;
		border: none;
		display: flex;
		align-items: center;
		justify-content: center;
		cursor: pointer;
		transition: .15s;
		flex-shrink: 0;
	}

	.send-circle:hover:not(:disabled) {
		background: var(--ac2);
	}

	.send-circle:disabled {
		background: var(--sf2);
		color: var(--dm);
		cursor: default;
	}

	.cancel-circle {
		width: 2rem;
		height: 2rem;
		border-radius: 50%;
		background: var(--tx-bright);
		color: var(--bg);
		border: none;
		display: flex;
		align-items: center;
		justify-content: center;
		cursor: pointer;
		transition: .15s;
		flex-shrink: 0;
	}

	.cancel-circle:hover {
		opacity: .8;
	}
</style>
