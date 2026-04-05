<script>
	import { t } from '$lib/i18n/index.js';
	import { Check, FilePlus } from 'lucide-svelte';
	import { computeUnifiedDiff, diffStats } from '$lib/utils/diff.js';
	import Modal from '$lib/ui/Modal.svelte';

	let { filepath, oldContent, newContent, isNew, applied, onApply, onClose } = $props();

	let diffLines = $derived(computeUnifiedDiff(oldContent, newContent, isNew));
	let stats = $derived(diffStats(diffLines));
</script>

<Modal {onClose} width="62.5rem" maxHeight="85vh" ariaLabel={filepath}>
	{#snippet header()}
		<div class="file-path">
			{#if isNew}<FilePlus size={14} class="new-icon" />{/if}
			{filepath}
		</div>
		<div class="stats">
			{#if stats.added > 0}<span class="stat-add">+{stats.added}</span>{/if}
			{#if stats.removed > 0}<span class="stat-del">-{stats.removed}</span>{/if}
			{#if isNew}<span class="badge-new">{$t('fix.new_file')}</span>{/if}
		</div>
	{/snippet}

	<div class="diff-scroll">
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
	</div>

	{#snippet footer()}
		{#if applied}
			<span class="applied-badge"><Check size={14} /> {$t('fix.already_applied')}</span>
		{:else}
			<button class="btn btn-success" onclick={onApply}>
				<Check size={14} /> {$t('fix.apply_file')}
			</button>
		{/if}
		<button class="btn" onclick={onClose}>{$t('fix.close')}</button>
	{/snippet}
</Modal>

<style>
	.file-path {
		font-family: var(--font-ui);
		font-size: 0.8125rem;
		color: var(--tx-bright);
		display: flex;
		align-items: center;
		gap: 0.375rem;
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

	.badge-new {
		background: var(--ok);
		color: #fff;
		padding: 0.0625rem 0.375rem;
		border-radius: 0.1875rem;
		font-size: 0.6875rem;
	}

	.diff-scroll {
		overflow: auto;
		flex: 1;
		min-height: 0;
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

	.applied-badge {
		display: inline-flex;
		align-items: center;
		gap: 0.25rem;
		color: var(--ok);
		font-size: 0.8125rem;
	}

	:global(.new-icon) { color: var(--ok); }
</style>
