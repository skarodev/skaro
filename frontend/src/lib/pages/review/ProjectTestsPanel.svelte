<script>
	import { t } from '$lib/i18n/index.js';
	import { Send, RotateCcw, Loader2 } from 'lucide-svelte';
	import CheckList from '$lib/ui/CheckList.svelte';
	import CommandList from '$lib/ui/CommandList.svelte';
	import TestsSummary from '$lib/ui/TestsSummary.svelte';
	import { buildErrorSummary } from '$lib/ui/testUtils.js';

	let {
		results = null,
		loading = false,
		onRunTests = () => {},
		onSendToFix = () => {},
	} = $props();

	let hasErrors = $derived(results && !results.passed);
	let hasResults = $derived(results !== null);

	function handleSendToFix() {
		onSendToFix(buildErrorSummary(results?.checklist, results?.global_commands));
	}
</script>

<div class="tests-panel">
	{#if hasResults}
		<div class="tests-section">
			<h4 class="section-title">{$t('review.checklist_title')}</h4>
			<CheckList checks={results.checklist} />
		</div>

		{#if results.global_commands && results.global_commands.length > 0}
			<div class="tests-section">
				<h4 class="section-title">{$t('review.global_commands_title')}</h4>
				<CommandList commands={results.global_commands} prefix="global" />
			</div>
		{/if}

		<TestsSummary
			passed={results.passed}
			label={results.passed ? $t('review.all_passed') : $t('review.has_failures')}
			timestamp={results.timestamp || ''}
		/>

		<div class="tests-actions">
			{#if hasErrors}
				<button class="btn btn-primary" onclick={handleSendToFix}>
					<Send size={14} /> {$t('review.send_to_fix')}
				</button>
			{/if}
			<button class="btn" disabled={loading} onclick={onRunTests}>
				{#if loading}<Loader2 size={14} class="spin" />{:else}<RotateCcw size={14} />{/if}
				{$t('review.rerun')}
			</button>
		</div>
	{:else}
		<div class="tests-empty">
			<p>{$t('review.not_run_yet')}</p>
			<button class="btn btn-primary" disabled={loading} onclick={onRunTests}>
				{#if loading}<Loader2 size={14} class="spin" />{/if}
				{$t('review.run_tests')}
			</button>
		</div>
	{/if}
</div>

<style>
	.tests-panel { padding: 0.5rem 0; }
	.tests-section { margin-bottom: 1.25rem; }

	.section-title {
		font-size: 0.8125rem; font-weight: 600; color: var(--tx);
		margin-bottom: 0.5rem; text-transform: uppercase;
		letter-spacing: 0.03em; font-family: var(--font-ui);
	}

	.tests-actions { display: flex; gap: 0.5rem; flex-wrap: wrap; }

	.tests-empty {
		color: var(--tx-dim); font-size: 0.875rem;
		display: flex; flex-direction: column; align-items: center;
		gap: 1rem; padding: 2rem 0;
	}
</style>
