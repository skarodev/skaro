<script>
	import { t } from '$lib/i18n/index.js';
	import { X, Check, FilePlus } from 'lucide-svelte';
	import { computeUnifiedDiff, diffStats } from '$lib/utils/diff.js';
	import { portal } from '$lib/utils/portal.js';

	let { filepath, oldContent, newContent, isNew, applied, onApply, onClose } = $props();

	let diffLines = $derived(computeUnifiedDiff(oldContent, newContent, isNew));
	let stats = $derived(diffStats(diffLines));

	function handleKeydown(e) {
		if (e.key === 'Escape') onClose();
	}
</script>

<svelte:window onkeydown={handleKeydown} />

<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
<div class="overlay" use:portal role="dialog" aria-modal="true" aria-label={filepath} tabindex="-1" onkeydown={handleKeydown} onclick={onClose}>
	<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
	<div class="modal" role="document" onclick={(e) => e.stopPropagation()}>
		<div class="modal-header">
			<div class="file-path">
				{#if isNew}<FilePlus size={14} class="new-icon" />{/if}
				{filepath}
			</div>
			<div class="stats">
				{#if stats.added > 0}<span class="stat-add">+{stats.added}</span>{/if}
				{#if stats.removed > 0}<span class="stat-del">-{stats.removed}</span>{/if}
				{#if isNew}<span class="badge-new">{$t('fix.new_file')}</span>{/if}
			</div>
			<button class="close-x" onclick={onClose}><X size={16} /></button>
		</div>

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

		<div class="modal-footer">
			{#if applied}
				<span class="applied-badge"><Check size={14} /> {$t('fix.already_applied')}</span>
			{:else}
				<button class="btn btn-success" onclick={onApply}>
					<Check size={14} /> {$t('fix.apply_file')}
				</button>
			{/if}
			<button class="btn" onclick={onClose}>{$t('fix.close')}</button>
		</div>
	</div>
</div>

<style>
	.overlay {
		position: fixed;
		inset: 0;
		z-index: 1000;
		background: rgba(0, 0, 0, .6);
		backdrop-filter: blur(0.125rem);
		display: flex;
		align-items: center;
		justify-content: center;
	}

	.modal {
		background: var(--bg-deep);
		border: 0.0625rem solid var(--bd2);
		border-radius: var(--r);
		width: 90vw;
		max-width: 62.5rem;
		max-height: 85vh;
		display: flex;
		flex-direction: column;
		box-shadow: 0 0.5rem 2rem rgba(0, 0, 0, .5);
	}

	.modal-header {
		display: flex;
		align-items: center;
		gap: 0.625rem;
		padding: 0.625rem 1rem;
		border-bottom: 0.0625rem solid var(--bd);
		flex-shrink: 0;
	}

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

	.close-x {
		background: none;
		border: none;
		color: var(--tx-dim);
		cursor: pointer;
		padding: 0.25rem;
	}

	.close-x:hover { color: var(--tx-bright); }

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
		border-right: 0.0625rem solid var(--bd);
	}

	.old-num { border-right: none; }

	.line-marker {
		width: 1.25rem;
		min-width: 1.25rem;
		text-align: center;
		color: var(--tx-dim);
		font-weight: 600;
		vertical-align: top;
		border-right: 0.0625rem solid var(--bd);
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

	.modal-footer {
		display: flex;
		gap: 0.5rem;
		padding: 0.625rem 1rem;
		border-top: 0.0625rem solid var(--bd);
		flex-shrink: 0;
		align-items: center;
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
