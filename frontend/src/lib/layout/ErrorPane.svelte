<script>
	import { t } from '$lib/i18n/index.js';
	import { errorEntries } from '$lib/stores/logStore.js';
</script>

<div class="pane">
	{#if $errorEntries.length === 0}
		<div class="empty">{$t('panel.no_problems')}</div>
	{:else}
		{#each $errorEntries as entry}
			<div class="error-entry">
				<span class="err-time">{entry.time}</span>
				<span class="err-text">
					{entry.text}
					{#if entry.context}<span class="err-ctx">{entry.context}</span>{/if}
				</span>
			</div>
		{/each}
	{/if}
</div>

<style>
	.pane {
		height: 100%;
		overflow-y: auto;
	}

	.empty {
		padding: 0.75rem;
		color: var(--tx-dim);
	}

	.error-entry {
		padding: 0.25rem 0.75rem;
		display: flex;
		gap: 0.625rem;
		line-height: 1.25rem;
		border-bottom: 0.0625rem solid var(--bd);
	}

	.error-entry:hover {
		background: color-mix(in srgb, var(--err) 6%, transparent);
	}

	.err-time {
		color: var(--tx-dim);
		flex-shrink: 0;
		font-variant-numeric: tabular-nums;
		min-width: 4.375rem;
	}

	.err-text {
		color: var(--err);
	}

	.err-ctx {
		color: var(--tx-dim);
		margin-left: 0.5rem;
	}
</style>
