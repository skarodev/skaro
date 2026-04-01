<script>
	import { t } from '$lib/i18n/index.js';
	import { Search, Check, RotateCcw, ClipboardList, FolderOpen, Pencil, Loader2 } from 'lucide-svelte';

	let {
		hasDevplan = false,
		hasAdrs = false,
		architectureReviewed = false,
		hasReviewResult = false,
		reviewing = false,
		approving = false,
		onReview,
		onApprove,
		onEdit,
	} = $props();
</script>

{#if architectureReviewed}
	<div class="btn-group">
		{#if onEdit}
			<button class="btn" onclick={onEdit}>
				<Pencil size={14} /> {$t('editor.edit')}
			</button>
		{/if}
		<button class="btn" disabled={reviewing} onclick={onReview}>
			{#if reviewing}<Loader2 size={14} class="spin" />{:else}<RotateCcw size={14} />{/if}
			{$t('arch.re_review')}
		</button>
		{#if !hasAdrs}
			<a class="hint-link" href="/adr">
				<FolderOpen size={14} /> {$t('arch.go_adr')}
			</a>
		{:else if !hasDevplan}
			<a class="hint-link" href="/devplan">
				<ClipboardList size={14} /> {$t('arch.go_devplan')}
			</a>
		{/if}
	</div>
{:else}
	<div class="btn-group">
		{#if onEdit}
			<button class="btn" onclick={onEdit}>
				<Pencil size={14} /> {$t('editor.edit')}
			</button>
		{/if}
		<button class="btn btn-primary" disabled={reviewing} onclick={onReview}>
			{#if reviewing}<Loader2 size={14} class="spin" />{:else}<Search size={14} />{/if}
			{$t('arch.review')}
		</button>
		<button class="btn btn-success" disabled={approving} onclick={onApprove}>
			{#if approving}<Loader2 size={14} class="spin" />{:else}<Check size={14} />{/if}
			{$t('arch.approve')}
		</button>
	</div>
{/if}

<style>
	.hint-link {
		display: inline-flex;
		align-items: center;
		gap: 0.25rem;
		color: var(--ac);
		font-size: 0.8125rem;
		cursor: pointer;
		padding: 0.25rem 0.5rem;
	}
	.hint-link:hover { text-decoration: underline; }
	.btn-success {
		background: var(--ok);
		color: #fff;
		border-color: var(--ok);
	}
	.btn-success:hover:not(:disabled) { filter: brightness(1.1); }
</style>
