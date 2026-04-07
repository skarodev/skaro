<script>
	import { t } from '$lib/i18n/index.js';
	import { ArrowUp, Square, Plus } from 'lucide-svelte';
	import AttachMenu from '$lib/ui/AttachMenu.svelte';
	import Tooltip from '$lib/ui/Tooltip.svelte';

	let {
		message = $bindable(''),
		loading = false,
		tokenDisplay = '',
		placeholder = '',
		scopeCount = 0,
		attachedFileCount = 0,
		showAttach = false,
		onSend = () => {},
		onCancel = () => {},
		onAttachFromDisk = () => {},
		onAttachFromRepo = () => {},
	} = $props();

	let inputFocused = $state(false);
	let textareaEl = $state(null);
	let attachMenuOpen = $state(false);

	let totalAttached = $derived(scopeCount + attachedFileCount);

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
				e.preventDefault();
				const el = textareaEl;
				if (el) {
					const start = el.selectionStart;
					const end = el.selectionEnd;
					message = message.substring(0, start) + '\n' + message.substring(end);
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
			{#if showAttach}
				<div class="attach-wrap">
					<Tooltip text={$t('attach.title')} placement="top">
						<button
							class="attach-btn"
							onclick={(e) => { e.stopPropagation(); attachMenuOpen = !attachMenuOpen; }}
						>
							<Plus size={20} strokeWidth={2} />
							{#if totalAttached > 0}
								<span class="attach-badge">{totalAttached}</span>
							{/if}
						</button>
					</Tooltip>
					<AttachMenu
						open={attachMenuOpen}
						{onAttachFromDisk}
						{onAttachFromRepo}
						onClose={() => attachMenuOpen = false}
					/>
				</div>
			{/if}
		</div>
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
		border: 1px solid var(--bd);
		border-radius: .75rem;
		background: var(--bg);
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
		color: var(--tx-dim);
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

	.attach-wrap {
		position: relative;
	}

	.attach-btn {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 2rem;
		height: 2rem;
		border: none;
		border-radius: var(--r2);
		background: none;
		color: var(--tx-dim);
		cursor: pointer;
		transition: background 0.12s, color 0.12s;
		position: relative;
	}

	.attach-btn:hover {
		background: var(--sf);
		color: var(--tx-bright);
	}

	.attach-badge {
		position: absolute;
		top: -0.125rem;
		right: -0.125rem;
		min-width: 1rem;
		height: 1rem;
		border-radius: 0.5rem;
		background: var(--ac);
		color: #fff;
		font-size: 0.625rem;
		font-weight: 700;
		display: flex;
		align-items: center;
		justify-content: center;
		padding: 0 0.25rem;
		font-family: var(--font-ui);
	}

	.token-estimate {
		font-size: 0.75rem;
		color: var(--tx-dim);
		font-family: var(--font-ui);
		text-align: center;
		padding: .5rem;
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
		background: var(--ac);
	}

	.send-circle:disabled {
		background: var(--sf2);
		color: var(--tx-dim);
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
