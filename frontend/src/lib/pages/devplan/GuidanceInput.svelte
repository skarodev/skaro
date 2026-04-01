<script>
	import { t } from '$lib/i18n/index.js';
	import { RefreshCw, X, Loader2 } from 'lucide-svelte';

	let {
		guidance = $bindable(''),
		updating = false,
		onRun = () => {},
		onCancel = () => {},
	} = $props();
</script>

<h3>{$t('devplan.update_title')}</h3>
<p class="subtitle">{$t('devplan.update_hint')}</p>
<textarea
	class="guidance-input"
	rows="4"
	placeholder={$t('devplan.update_placeholder')}
	bind:value={guidance}
></textarea>
<div class="btn-group">
	<button class="btn btn-primary" disabled={updating} onclick={onRun}>
		{#if updating}<Loader2 size={14} class="spin" />{:else}<RefreshCw size={14} />{/if}
		{$t('devplan.run_update')}
	</button>
	<button class="btn" onclick={onCancel}>
		<X size={14} /> {$t('devplan.cancel')}
	</button>
</div>

<style>
	.guidance-input {
		width: 100%;
		padding: 0.5rem 0.75rem;
		background: var(--bg-deep);
		border: 0.0625rem solid var(--bd);
		border-radius: var(--r);
		color: var(--tx);
		font-size: 0.875rem;
		font-family: inherit;
		resize: vertical;
		min-height: 3.75rem;
		margin-bottom: 0.5rem;
	}

	.guidance-input:focus {
		outline: none;
		border-color: var(--ac);
		box-shadow: 0 0 0 0.0625rem var(--ac2);
	}
</style>
