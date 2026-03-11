<script>
	import { t } from '$lib/i18n/index.js';
	import { ArrowUp, Square, Cpu } from 'lucide-svelte';

	let {
		message = $bindable(''),
		loading = false,
		tokenDisplay = '',
		modelDisplay = '',
		placeholder = '',
		onSend = () => {},
		onCancel = () => {},
	} = $props();

	let inputFocused = $state(false);
	let textareaEl = $state(null);

	function autoResize(e) {
		const el = e.target;
		el.style.height = 'auto';
		el.style.height = Math.min(el.scrollHeight, 200) + 'px';
	}

	function resetHeight() {
		if (textareaEl) {
			textareaEl.style.height = 'auto';
		}
	}

	function handleKeydown(e) {
		if (e.key === 'Enter') {
			if (e.ctrlKey || e.metaKey) {
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
		<div class="bar-spacer"></div>
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
		max-height: 20rem;
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
	}

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
