<script>
	import { t } from '$lib/i18n/index.js';
	import { renderMarkdown, stripFilePathBlocks, stripFileMarkers } from '$lib/utils/markdown.js';
	import { FileCode, Check, Bot, ChevronDown, ChevronUp } from 'lucide-svelte';

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
			class:turn-body-expanded={expanded}
			bind:this={userBodyEl}
		>
			<div class="turn-text user-text">{turn.content}</div>
		</div>
		{#if isOverflowing}
			<button class="expand-btn" onclick={() => expanded = !expanded}>
				{#if expanded}
					<ChevronUp size={14} />
					{$t('fix.collapse')}
				{:else}
					<ChevronDown size={14} />
					{$t('fix.expand')}
				{/if}
			</button>
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
		max-width: 92%;
		margin-left: auto;
		background: var(--bg-high);
		border-radius: var(--r);
		padding: 1.2rem;
		position: relative;
	}

	.turn-user .turn-label {
		color: var(--ac);
		text-align: right;
	}

	.turn-assistant .turn-label {
		color: var(--ac);
	}

	.turn-label {
		font-size: 0.75rem;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: .05em;
		margin-bottom: 0.5rem;
		display: flex;
		align-items: center;
		gap: 0.25rem;
	}

	/* ── Turn text (assistant markdown) ── */

	.turn-text {
		font-size: 1rem;
		line-height: 1.65;
		color: var(--tx);
	}

	.turn-text :global(h1) {
		font-size: 1.3rem;
		margin: 1rem 0 0.5rem;
		color: var(--tx-bright);
	}

	.turn-text :global(h2) {
		font-size: 1.2rem;
		margin: 1rem 0 0.5rem;
		color: var(--ac);
	}

	.turn-text :global(h3) {
		font-size: 1.1rem;
		margin: 1rem 0 0.5rem;
		color: var(--tx-bright);
	}

	.turn-text :global(p) {
		margin: 0.75rem 0;
	}

	.turn-text :global(ul),
	.turn-text :global(ol) {
		margin: 0.25rem 0 0.25rem 1.25rem;
	}

	.turn-text :global(li) {
		margin: 0.125rem 0;
	}

	.turn-text :global(strong) {
		color: var(--tx-bright);
	}

	.turn-text :global(code) {
		background: rgb(from var(--ac) r g b / 0.05);
		border-radius: var(--r2);
		padding: 0.08rem 0.25rem 0.1rem;
		color: var(--ac);
		font-size: 1rem;
		border: solid 1px rgb(from var(--ac) r g b / 0.25);
	}

	.turn-text :global(pre) {
		position: relative;
		background: var(--bg-soft);
		border: none;
		border-radius: var(--r);
		padding: 0.75rem 1rem;
		overflow-x: auto;
		font-size: 1rem;
		margin: 0.5rem 0;
	}

	.turn-text :global(pre code) {
		background: none;
		padding: 0;
		border-radius: 0;
		color: inherit;
		font-size: inherit;
		border: none;
	}

	.turn-text :global(blockquote) {
		border-left: 0.1875rem solid var(--ac);
		padding-left: 0.625rem;
		color: var(--tx-dim);
		margin: 0.375rem 0;
	}

	.turn-text :global(table) {
		border-collapse: separate;
		border-spacing: 0;
		width: 100%;
		margin: 0.75rem 0;
		background: var(--bg-deep);
		border-radius: var(--r);
		overflow: hidden;
		border: 1px solid var(--bd);
	}

	.turn-text :global(thead) {
		background: var(--bd);
	}

	.turn-text :global(th),
	.turn-text :global(td) {
		border-bottom: 0.0625rem solid var(--bd);
		border-right: 0.0625rem solid var(--bd);
		padding: 0.4375rem 0.625rem;
		text-align: left;
		font-size: 0.9rem;
		word-wrap: break-word;
		overflow-wrap: break-word;
	}

	.turn-text :global(th:last-child),
	.turn-text :global(td:last-child) {
		border-right: none;
	}

	.turn-text :global(tr:last-child td) {
		border-bottom: none;
	}

	.turn-text :global(th) {
		color: var(--tx-bright);
		font-weight: 600;
	}

	.turn-text :global(hr) {
		border: none;
		border-top: 1px solid var(--bd);
		margin: 0.625rem 0;
	}

	/* ── User message text ── */

	.user-text {
		color: var(--tx-bright);
		white-space: pre-wrap;
		font-size: 1rem;
		line-height: 1.5;
	}

	/* ── Collapsible user message (7 lines) ── */
	.turn-body-user {
		max-height: calc(1.5em * 7);
		overflow: hidden;
		position: relative;
	}

	.turn-body-user.turn-body-expanded {
		max-height: none;
	}

	.expand-btn {
		display: inline-flex;
		align-items: center;
		gap: 0.25rem;
		background: none;
		border: none;
		color: var(--tx-dim);
		font-size: 0.75rem;
		font-family: inherit;
		cursor: pointer;
		padding: 0.375rem 0;
		transition: color 0.1s;
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
		color: var(--tx-dim);
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
		border-color: var(--ok);
	}

	.file-applied-readonly {
		cursor: default;
		opacity: 0.8;
	}

	.file-applied-readonly:hover {
		border-color: var(--ok);
		background: var(--bg);
	}

	.file-applied .file-name {
		color: var(--ok);
	}

	.file-name {
		flex: 1;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.badge-new {
		background: var(--ok);
		color: #fff;
		padding: 0 0.3125rem;
		border-radius: 0.1875rem;
		font-size: 0.625rem;
	}

	:global(.applied-icon) {
		color: var(--ok);
	}
</style>
