<script>
	import { t } from '$lib/i18n/index.js';
	import Modal from '$lib/ui/Modal.svelte';

	let { filepath, diffText, onClose } = $props();

	/** Parse raw git unified diff into structured lines. */
	let diffLines = $derived(parseDiff(diffText));

	/** Counts of added/removed lines. */
	let stats = $derived.by(() => {
		let added = 0, removed = 0;
		for (const l of diffLines) {
			if (l.type === 'add') added++;
			else if (l.type === 'del') removed++;
		}
		return { added, removed };
	});

	function parseDiff(text) {
		if (!text) return [];
		const lines = text.split('\n');
		const result = [];
		let oldNum = 0, newNum = 0;

		for (const line of lines) {
			if (line.startsWith('@@')) {
				const m = line.match(/@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@/);
				if (m) {
					oldNum = parseInt(m[1], 10);
					newNum = parseInt(m[2], 10);
				}
				result.push({ type: 'sep', oldNum: '', newNum: '', text: line });
			} else if (line.startsWith('---') || line.startsWith('+++') || line.startsWith('diff ') || line.startsWith('index ')) {
				// Meta headers — skip
			} else if (line.startsWith('+')) {
				result.push({ type: 'add', oldNum: '', newNum: newNum, text: line.slice(1) });
				newNum++;
			} else if (line.startsWith('-')) {
				result.push({ type: 'del', oldNum: oldNum, newNum: '', text: line.slice(1) });
				oldNum++;
			} else if (line.startsWith(' ')) {
				result.push({ type: 'ctx', oldNum: oldNum, newNum: newNum, text: line.slice(1) });
				oldNum++;
				newNum++;
			} else if (line === '\\ No newline at end of file') {
				// skip
			}
		}
		return result;
	}
</script>

<Modal {onClose} width="62.5rem" maxHeight="85vh" ariaLabel={filepath}>
	{#snippet header()}
		<span class="file-path">{filepath}</span>
		<div class="stats">
			{#if stats.added > 0}<span class="stat-add">+{stats.added}</span>{/if}
			{#if stats.removed > 0}<span class="stat-del">-{stats.removed}</span>{/if}
		</div>
	{/snippet}

	<div class="diff-scroll">
		{#if diffLines.length === 0}
			<p class="diff-empty">(no changes)</p>
		{:else}
			<table class="diff-table">
				<tbody>
					{#each diffLines as line}
						<tr class="diff-row diff-{line.type}">
							<td class="line-num old-num">{line.oldNum}</td>
							<td class="line-num new-num">{line.newNum}</td>
							<td class="line-marker">
								{#if line.type === 'add'}+{:else if line.type === 'del'}-{:else if line.type === 'sep'}⋯{:else}&nbsp;{/if}
							</td>
							<td class="line-text"><pre>{line.text}</pre></td>
						</tr>
					{/each}
				</tbody>
			</table>
		{/if}
	</div>

	{#snippet footer()}
		<button class="btn" onclick={onClose}>{$t('fix.close')}</button>
	{/snippet}
</Modal>

<style>
	.file-path {
		font-family: var(--font-ui);
		font-size: 0.8125rem;
		color: var(--tx-bright);
		flex: 1;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.stats {
		display: flex;
		gap: 0.5rem;
		font-size: 0.75rem;
		font-family: var(--font-ui);
	}

	.stat-add { color: var(--ok); }
	.stat-del { color: var(--err); }

	.diff-scroll {
		overflow: auto;
		flex: 1;
		min-height: 0;
	}

	.diff-empty {
		padding: 2rem;
		text-align: center;
		color: var(--tx-dim);
	}

	.diff-table {
		width: 100%;
		border-collapse: collapse;
		font-size: 0.8125rem;
		font-family: var(--font-ui);
	}

	.diff-row { line-height: 1; }
	.diff-ctx { background: transparent; }
	.diff-add { background: color-mix(in srgb, var(--ok) 15%, transparent); }
	.diff-del { background: color-mix(in srgb, var(--err) 12%, transparent); }
	.diff-sep { background: var(--bg); }
	.diff-sep .line-text pre { color: var(--tx-dim); font-style: italic; }

	.line-num {
		width: 2.75rem;
		min-width: 2.75rem;
		text-align: right;
		padding: 0 0.375rem;
		color: var(--tx-dim);
		font-size: 0.75rem;
		user-select: none;
		vertical-align: top;
		border-right: 1px solid var(--bd);
	}

	.old-num { border-right: none; }

	.line-marker {
		width: 1.25rem;
		min-width: 1.25rem;
		text-align: center;
		color: var(--tx-dim);
		font-weight: 600;
		vertical-align: top;
		border-right: 1px solid var(--bd);
		user-select: none;
	}

	.diff-add .line-marker { color: var(--ok); }
	.diff-del .line-marker { color: var(--err); }

	.line-text {
		padding: 0 0.625rem;
		white-space: pre;
	}

	.line-text pre {
		margin: 0;
		font-family: inherit;
		font-size: inherit;
		white-space: pre;
		overflow-x: visible;
	}
</style>
