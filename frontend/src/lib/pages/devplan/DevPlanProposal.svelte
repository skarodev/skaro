<script>
	import { t } from '$lib/i18n/index.js';
	import { Check, X, Loader2 } from 'lucide-svelte';
	import MarkdownContent from '$lib/ui/MarkdownContent.svelte';
	import PlanTaskCard from './PlanTaskCard.svelte';

	let {
		mode = 'initial',
		items = [],
		proposedDevplan = '',
		rawResponse = '',
		confirming = false,
		onConfirm = () => {},
		onDiscard = () => {},
	} = $props();

	let isUpdate = $derived(mode === 'update');

	/**
	 * Detect whether items are milestones (have tasks[]) or flat tasks.
	 * API always returns milestones, but we handle both for safety.
	 */
	let isMilestoneStructure = $derived(
		items.length > 0 && Array.isArray(items[0]?.tasks)
	);

	let totalTaskCount = $derived(
		isMilestoneStructure
			? items.reduce((sum, ms) => sum + (ms.tasks?.length || 0), 0)
			: items.length
	);
</script>

{#if isUpdate}
	<div class="card" style="margin-top: 2rem">
		<h3 class="section-title">{$t('devplan.update_proposed')}</h3>
		<p class="subtitle">{$t('devplan.update_review')}</p>

		{#if proposedDevplan}
			<details class="proposal-details" open>
				<summary class="details-summary">{$t('devplan.updated_plan')}</summary>
				<MarkdownContent content={proposedDevplan} />
			</details>
		{/if}

		{#if items.length > 0}
			<details class="proposal-details" open>
				<summary class="details-summary">{$t('devplan.new_tasks', { n: totalTaskCount })}</summary>
				{#if isMilestoneStructure}
					{#each items as ms, mi}
						<div class="milestone-group">
							<div class="milestone-header">
								<span class="milestone-badge">M{mi + 1}</span>
								<h4 class="milestone-title">{ms.milestone_title || ms.milestone_slug}</h4>
								<span class="milestone-count">{ms.tasks?.length || 0}</span>
							</div>
							{#each ms.tasks || [] as task, ti}
								<PlanTaskCard {task} index={ti} />
							{/each}
						</div>
					{/each}
				{:else}
					{#each items as task, i}
						<PlanTaskCard {task} index={i} />
					{/each}
				{/if}
			</details>
		{/if}

		{#if !proposedDevplan && rawResponse}
			<details class="proposal-details" open>
				<summary class="details-summary">{$t('devplan.llm_response')}</summary>
				<MarkdownContent content={rawResponse} />
			</details>
		{/if}

		<div class="btn-group">
			<button class="btn btn-success" disabled={confirming} onclick={onConfirm}>
				{#if confirming}<Loader2 size={14} class="spin" />{/if}
				<Check size={14} /> {$t('devplan.confirm_update')}
			</button>
			<button class="btn btn-danger" onclick={onDiscard}>
				<X size={14} /> {$t('devplan.discard_update')}
			</button>
		</div>
	</div>
{:else}
	<h3 class="section-title">{$t('devplan.proposed')}</h3>
	<p class="subtitle">{$t('devplan.review_text')}</p>

	{#if isMilestoneStructure}
		{#each items as ms, mi}
			<div class="milestone-group">
				<div class="milestone-header">
					<span class="milestone-badge">M{mi + 1}</span>
					<h4 class="milestone-title">{ms.milestone_title || ms.milestone_slug}</h4>
					<span class="milestone-count">{ms.tasks?.length || 0}</span>
				</div>
				{#each ms.tasks || [] as task, ti}
					<PlanTaskCard {task} index={ti} />
				{/each}
			</div>
		{/each}
	{:else}
		{#each items as task, i}
			<PlanTaskCard {task} index={i} />
		{/each}
	{/if}

	<div class="btn-group">
		<button class="btn btn-success" disabled={confirming} onclick={onConfirm}>
			<Check size={14} /> {$t('devplan.confirm')}
		</button>
		<button class="btn btn-danger" onclick={onDiscard}>
			<X size={14} /> {$t('devplan.discard')}
		</button>
	</div>
{/if}

<style>
	.section-title {
		font-size: 1rem;
		font-weight: 600;
		color: var(--tx-bright);
		margin-bottom: 0.5rem;
	}

	.proposal-details {
		margin: 0.625rem 0;
	}

	.details-summary {
		cursor: pointer;
		color: var(--ac);
		font-size: 0.8125rem;
		font-weight: 600;
		margin-bottom: 0.375rem;
	}

	.milestone-group {
		margin-bottom: 1.25rem;
	}

	.milestone-header {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		margin-bottom: 0.5rem;
		padding: 0.5rem 0.75rem;
		border-left: 3px solid var(--ac);
		background: var(--bg-deep);
		border-radius: 0 var(--r) var(--r) 0;
	}

	.milestone-badge {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 1.75rem;
		height: 1.75rem;
		border-radius: 50%;
		background: var(--ac);
		color: var(--bg);
		font-size: 0.6875rem;
		font-weight: 700;
		flex-shrink: 0;
	}

	.milestone-title {
		font-size: 0.875rem;
		font-weight: 600;
		color: var(--tx-bright);
		margin: 0;
		flex: 1;
	}

	.milestone-count {
		font-size: 0.6875rem;
		color: var(--tx-dim);
		background: var(--bg-high, var(--bg));
		padding: 0.125rem 0.5rem;
		border-radius: 999px;
		font-family: var(--font-ui);
	}
</style>
