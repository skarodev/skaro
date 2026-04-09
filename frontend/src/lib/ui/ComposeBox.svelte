<script>
	import { t } from '$lib/i18n/index.js';
	import { ArrowUp, Square, Plus, X } from 'lucide-svelte';
	import AttachMenu from '$lib/ui/AttachMenu.svelte';
	import Tooltip from '$lib/ui/Tooltip.svelte';

	let {
		message = $bindable(''),
		loading = false,
		tokenDisplay = '',
		placeholder = '',
		scopeCount = 0,
		attachedFiles = [],
		showAttach = false,
		onSend = () => {},
		onCancel = () => {},
		onRemoveFile = (/** @type {number} */ _idx) => {},
		onAttachFromDisk = () => {},
		onAttachFromRepo = () => {},
	} = $props();

	let inputFocused = $state(false);
	let textareaEl = $state(null);
	let attachMenuOpen = $state(false);

	let totalAttached = $derived(scopeCount + attachedFiles.length);

	/** Extract uppercase extension label from filename. */
	function extLabel(name) {
		const dot = name.lastIndexOf('.');
		if (dot < 0) return '?';
		return name.slice(dot + 1).toUpperCase();
	}

	/** Pick badge color class based on extension group. */
	function extClass(name) {
		const ext = name.split('.').pop()?.toLowerCase() || '';
		if (['py','js','ts','jsx','tsx','go','rs','java','rb','c','cpp','cs','swift','kt','php','lua','r','svelte','vue'].includes(ext)) return 'ext-code';
		if (['json','yaml','yml','toml','ini','xml','env','conf','dockerfile','tf','proto'].includes(ext)) return 'ext-config';
		if (['md','txt','rst','csv','sql'].includes(ext)) return 'ext-doc';
		if (['html','css','scss','less'].includes(ext)) return 'ext-web';
		return 'ext-other';
	}

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
	{#if attachedFiles.length > 0}
		<div class="file-strip">
			{#each attachedFiles as file, i}
				<div class="file-card">
					<button class="file-remove" onclick={() => onRemoveFile(i)}>
						<X size={11} />
					</button>
					<span class="file-name">{file.name}</span>
					<span class="file-ext {extClass(file.name)}">{extLabel(file.name)}</span>
				</div>
			{/each}
		</div>
	{/if}
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
				disabled={!message.trim() && attachedFiles.length === 0}
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

	/* ── File strip ── */

	.file-strip {
		display: flex;
		gap: 0.5rem;
		padding: 0.75rem 1rem 0;
		overflow-x: auto;
		scrollbar-width: thin;
	}

	.file-card {
		position: relative;
		flex-shrink: 0;
		width: 6rem;
		height: 6rem;
		border-radius: var(--r);
		background: var(--bg-deep);
		border: 1px solid var(--bd);
		display: flex;
		flex-direction: column;
		justify-content: space-between;
		padding: 0.375rem 0.5rem;
		overflow: hidden;
		transition: border-color 0.12s;
	}

	.file-card:hover {
		border-color: var(--bd2);
	}

	.file-remove {
		position: absolute;
		top: 0.25rem;
		right: 0.25rem;
		width: 1.25rem;
		height: 1.25rem;
		border-radius: 50%;
		border: none;
		background: var(--bg-soft);
		color: var(--tx-dim);
		display: flex;
		align-items: center;
		justify-content: center;
		cursor: pointer;
		transition: background 0.1s, color 0.1s;
		padding: 0;
	}

	.file-remove:hover {
		background: var(--err);
		color: #fff;
	}

	.file-name {
		font-size: 0.625rem;
		font-family: var(--font-ui);
		color: var(--tx);
		line-height: 1.3;
		word-break: break-all;
		overflow: hidden;
		display: -webkit-box;
		-webkit-line-clamp: 3;
		-webkit-box-orient: vertical;
		padding-right: 1rem;
	}

	.file-ext {
		align-self: flex-start;
		font-size: 0.5625rem;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.04em;
		padding: 0.0625rem 0.3rem;
		border-radius: 0.1875rem;
		font-family: var(--font-ui);
	}

	.ext-code {
		background: rgb(from var(--ac) r g b / 0.15);
		color: var(--ac);
	}

	.ext-config {
		background: rgb(from var(--warn) r g b / 0.15);
		color: var(--warn);
	}

	.ext-doc {
		background: rgb(from var(--ok) r g b / 0.15);
		color: var(--ok);
	}

	.ext-web {
		background: rgb(from var(--info, var(--ac)) r g b / 0.15);
		color: var(--info, var(--ac));
	}

	.ext-other {
		background: var(--sf);
		color: var(--tx-dim);
	}

	/* ── Textarea ── */

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
