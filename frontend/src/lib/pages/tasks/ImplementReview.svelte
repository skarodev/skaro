<script>
	import { t } from '$lib/i18n/index.js';
	import { slide } from 'svelte/transition';
	import { FileCode, Check, CheckCircle } from 'lucide-svelte';

	let {
		stage = 0,
		filesMap = {},
		appliedFiles = {},
		onOpenDiff = (fpath, fdata) => {},
		onApplyAll = () => {},
	} = $props();

	let fileEntries = $derived(Object.entries(filesMap));
	let allApplied = $derived(fileEntries.length > 0 && fileEntries.every(([f]) => appliedFiles[f]));
</script>

{#if fileEntries.length > 0}
<div class="card" style="margin-top: 2rem">
	<h3>{$t('impl.stage_complete', { n: stage })}</h3>
	<p class="subtitle">{$t('impl.files_generated')}</p>
	<div class="impl-file-list">
		{#each fileEntries as [fpath, fdata] (fpath)}
			{@const isApplied = !!appliedFiles[fpath]}
			<!-- svelte-ignore a11y_click_events_have_key_events -->
			<!-- svelte-ignore a11y_no_static_element_interactions -->
			<div
				class="impl-file-item"
				class:impl-file-applied={isApplied}
				onclick={() => onOpenDiff(fpath, fdata)}
				out:slide={{ duration: 300 }}
			>
				<FileCode size={14} />
				<span class="impl-file-name">{fpath}</span>
				{#if fdata.is_new}<span class="impl-badge-new">{$t('fix.new')}</span>{/if}
				{#if isApplied}<Check size={14} class="impl-applied-icon" />{/if}
			</div>
		{/each}
	</div>
	{#if !allApplied}
		<button class="btn btn-primary" style="margin-top: 10px" onclick={onApplyAll}>
			<CheckCircle size={14} /> {$t('impl.apply_all')}
		</button>
	{/if}
	<div class="alert alert-info" style="margin-top: 10px">{$t('impl.review_hint')}</div>
</div>
{/if}

<style>
	.impl-file-list {
		display: flex;
		flex-direction: column;
		gap: 0.125rem;
		margin-top: 0.5rem;
	}

	.impl-file-item {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.375rem 0.625rem;
		background: var(--bg-deep);
		border-radius: var(--r2);
		cursor: pointer;
		font-size: 0.8125rem;
		color: var(--tx);
		transition: background .1s;
	}

	.impl-file-item:hover {
		background: var(--sf2);
	}

	.impl-file-item.impl-file-applied {
		opacity: .6;
	}

	.impl-file-name {
		flex: 1;
		font-family: var(--font-ui);
		font-size: 0.75rem;
	}

	.impl-badge-new {
		font-size: 0.625rem;
		padding: 0.0625rem 0.3125rem;
		border-radius: 0.1875rem;
		background: rgba(106, 135, 89, .2);
		color: var(--gn-bright);
		font-family: var(--font-ui);
		text-transform: uppercase;
		letter-spacing: 0.019rem;
	}

	:global(.impl-applied-icon) {
		color: var(--gn-bright);
		flex-shrink: 0;
	}
</style>
