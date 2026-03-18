<script>
	import { t } from '$lib/i18n/index.js';
	import { renderMarkdown, stripFilePathBlocks, stripFileMarkers } from '$lib/utils/markdown.js';
	import { FileCode, Check, Bot } from 'lucide-svelte';

	let {
		turn = {},
		index = 0,
		appliedFiles = {},
		modelDisplay = '',
		onOpenDiff = (turnIdx, fpath, fdata) => {},
	} = $props();

	/**
	 * Content to render as markdown.
	 *
	 * File-path code blocks (```src/app.py … ```) are stripped because they
	 * are displayed by dedicated file-card UI (turn.files / DiffModal).
	 *
	 * All other code blocks (```python, ```json, bare ```) are preserved
	 * for renderMarkdown to convert into <pre><code> elements.
	 */
	let displayContent = $derived(
		turn.role === 'assistant'
			? stripFileMarkers(stripFilePathBlocks(turn.content || '')).trim()
			: (turn.content || '')
	);

	let turnIdx = $derived(turn.turnIndex ?? index);

	// ── Collapsible user message ──
	let userBodyEl = $state(null);
	let isOverflowing = $state(false);
	let expanded = $state(false);

	$effect(() => {
		if (turn.role === 'user' && userBodyEl) {
			requestAnimationFrame(() => {
				isOverflowing = userBodyEl.scrollHeight > userBodyEl.clientHeight;
			});
		}
	});
</script>

<div class="turn turn-{turn.role}">
	{#if turn.role === 'assistant'}
		<div class="turn-label"><Bot size={14} /> {modelDisplay || $t('fix.llm')}</div>
		<div class="turn-text">{@html renderMarkdown(displayContent)}</div>

		{#if turn.files && Object.keys(turn.files).length > 0}
			<div class="file-list">
				<div class="file-list-header">{$t('fix.proposed_files')}:</div>
				{#each Object.entries(turn.files) as [fpath, fdata]}
					{@const sessionApplied = !!(appliedFiles[turnIdx]?.[fpath])}
					{@const diskApplied = !fdata.is_new && fdata.old != null && fdata.old === fdata.new}
					{@const isApplied = sessionApplied || diskApplied}
					{#if isApplied}
						<div class="file-item file-applied file-applied-readonly">
							<FileCode size={13} />
							<span class="file-name">{fpath}</span>
							<Check size={13} class="applied-icon" />
						</div>
					{:else}
						<!-- svelte-ignore a11y_click_events_have_key_events -->
						<!-- svelte-ignore a11y_no_static_element_interactions -->
						<div class="file-item" onclick={() => onOpenDiff(turnIdx, fpath, fdata)}>
							<FileCode size={13} />
							<span class="file-name">{fpath}</span>
							{#if fdata.is_new}<span class="badge-new">{$t('fix.new')}</span>{/if}
						</div>
					{/if}
				{/each}
			</div>
		{/if}
	{:else}
		<div class="turn-label">{$t('fix.you')}</div>
		<div
			class="turn-body-user"
			style={expanded ? 'max-height: none' : ''}
			bind:this={userBodyEl}
		>
			<div class="turn-text user-text">{turn.content}</div>
			{#if isOverflowing && !expanded}
				<div class="user-overlay">
					<button class="expand-btn" onclick={() => expanded = true}>
						{$t('fix.expand')}
					</button>
				</div>
			{/if}
		</div>
		{#if expanded}
			<div class="user-overlay user-overlay-hidden">
				<button class="expand-btn" onclick={() => expanded = false}>
					{$t('fix.collapse')}
				</button>
			</div>
		{/if}
	{/if}
</div>

<style>
	.turn {
		margin: 2.5rem 0;
	}

	.turn:last-child {
		margin-bottom: 0;
	}

	.turn-user {
		max-width: 80%;
		margin-left: auto;
		background: var(--bg2);
		border-radius: var(--r);
		padding: 1.2rem;
		position: relative;
	}

	.turn-user .turn-label {
		color: var(--ac);
		text-align: right;
	}

	.turn-assistant .turn-label {
		color: var(--or);
	}

	.turn-label {
		font-size: 0.75rem;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: .05em;
		margin-bottom: 1rem;
		display: flex;
		align-items: center;
		gap: 0.25rem;
	}

	.turn-text {
		font-size: 1rem;
		line-height: 1.4rem;
		color: var(--tx-bright);
	}

    .turn-text :global(h1) {
        font-size: 1.2rem;
    }

	.turn-text :global(ul) {
	    margin-left: 2rem;
	}

	.turn-text :global(h2) {
		font-size: 1.3rem;
		margin-bottom: 1.2rem;
	}

	.turn-text :global(p) {
		margin: 1rem 0;
	}

    .turn-text :global(table) {
        margin: 2rem 0;
    }

	.turn-text :global(pre) {
		background: var(--bg);
		border: 0.0625rem solid var(--bd);
		border-radius: var(--r);
		padding: 0.5rem 0.625rem;
		overflow-x: auto;
		font-size: 0.75rem;
		margin: 0.375rem 0;
	}

	.turn-text :global(pre code) {
		background: none;
		padding: 0;
		border-radius: 0;
		color: inherit;
		font-size: inherit;
	}

	.user-text {
		color: var(--tx-bright);
		white-space: pre-wrap;
		font-size: 1.1rem;
	}

	/* ── Collapsible user message ── */
	.turn-body-user {
		max-height: 18rem;
		overflow: hidden;
		position: relative;
	}

	.user-overlay {
		position: relative;
		height: 2rem;
		width: 100%;
		display: flex;
		align-items: center;
	}

	.user-overlay:not(.user-overlay-hidden) {
		background: var(--bg2);
		position: absolute;
		bottom: 0;
		left: 0;
		padding: .5rem 0rem;
	}

	.user-overlay-hidden {
		margin-top: 1rem;
		height: auto;
	}

	.expand-btn {
		background: none;
		border: none;
		color: var(--tx);
		font-size: 0.8125rem;
		font-family: inherit;
		cursor: pointer;
		padding: 0 0.25rem;
		transition: color .1s;
	}

	.expand-btn:hover {
		color: var(--tx-bright);
	}

	/* ── File List ── */

	.file-list {
		margin-top: 2rem;
	}

	.file-list-header {
		font-size: 0.75rem;
		color: var(--dm);
		margin-bottom: 0.5rem;
	}

	.file-item {
		display: flex;
		align-items: center;
		gap: 0.375rem;
		padding: 0.3125rem 0.625rem;
		margin: 0.125rem 0;
		background: var(--bg);
		border: 0.0625rem solid var(--bd);
		border-radius: var(--r2);
		cursor: pointer;
		font-size: 0.8125rem;
		font-family: var(--font-ui);
		color: var(--ac);
		transition: .12s;
	}

	.file-item:hover {
		border-color: var(--ac);
		background: var(--sf-hover);
	}

	.file-applied {
		border-color: var(--gn);
	}

	.file-applied-readonly {
		cursor: default;
		opacity: 0.8;
	}

	.file-applied-readonly:hover {
		border-color: var(--gn);
		background: var(--bg);
	}

	.file-applied .file-name {
		color: var(--gn-bright);
	}

	.file-name {
		flex: 1;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.badge-new {
		background: var(--gn);
		color: #fff;
		padding: 0 0.3125rem;
		border-radius: 0.1875rem;
		font-size: 0.625rem;
	}

	:global(.applied-icon) {
		color: var(--gn-bright);
	}
</style>
