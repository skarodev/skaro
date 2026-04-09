<script>
	import { t } from '$lib/i18n/index.js';
	import { renderMarkdown } from '$lib/utils/markdown.js';
	import { CirclePlus, Check, AlertTriangle, AlertCircle, Info } from 'lucide-svelte';
	import Tooltip from '$lib/ui/Tooltip.svelte';

	let {
		issue = {},
		created = false,
		onCreateTask = () => {},
	} = $props();

	const SEVERITY_META = {
		must_fix: { icon: AlertCircle, cls: 'sev-must-fix', label: 'review_issue.must_fix' },
		should_improve: { icon: AlertTriangle, cls: 'sev-should-improve', label: 'review_issue.should_improve' },
		nice_to_have: { icon: Info, cls: 'sev-nice-to-have', label: 'review_issue.nice_to_have' },
	};

	let meta = $derived(SEVERITY_META[issue.severity] || SEVERITY_META.should_improve);
</script>

<div class="issue-card" class:issue-created={created}>
	<div class="issue-header">
		<span class="sev-badge {meta.cls}">
			<svelte:component this={meta.icon} size={12} />
			{$t(meta.label)}
		</span>
		{#if issue.file}
			<span class="issue-file">{issue.file}</span>
		{/if}
	</div>

	<div class="issue-title">{issue.title}</div>

	{#if issue.description}
		<div class="issue-desc">{@html renderMarkdown(issue.description)}</div>
	{/if}

	<div class="issue-footer">
		{#if created}
			<span class="created-label">
				<Check size={13} />
				{$t('review_issue.task_created')}
			</span>
		{:else}
			<Tooltip text={$t('review_issue.create_task_tip')} placement="top">
				<button class="btn btn-sm" onclick={onCreateTask}>
					<CirclePlus size={13} />
					{$t('review_issue.create_task')}
				</button>
			</Tooltip>
		{/if}
	</div>
</div>

<style>
	.issue-card {
		border: 0.0625rem solid var(--bd);
		border-radius: var(--r);
		background: var(--bg-deep);
		padding: 0.75rem;
		margin: 0.5rem 0;
	}

	.issue-created {
		opacity: 0.7;
		border-color: var(--ok);
	}

	.issue-header {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		margin-bottom: 0.375rem;
		flex-wrap: wrap;
	}

	.sev-badge {
		display: inline-flex;
		align-items: center;
		gap: 0.25rem;
		font-size: 0.6875rem;
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.03em;
		padding: 0.125rem 0.4rem;
		border-radius: 0.25rem;
	}

	.sev-must-fix {
		background: rgb(from var(--err) r g b / 0.15);
		color: var(--err);
	}

	.sev-should-improve {
		background: rgb(from var(--warn) r g b / 0.15);
		color: var(--warn);
	}

	.sev-nice-to-have {
		background: rgb(from var(--ac) r g b / 0.10);
		color: var(--ac);
	}

	.issue-file {
		font-size: 0.75rem;
		font-family: var(--font-ui);
		color: var(--tx-dim);
	}

	.issue-title {
		font-size: 0.875rem;
		font-weight: 600;
		color: var(--tx-bright);
		margin-bottom: 0.25rem;
	}

	.issue-desc {
		font-size: 0.8125rem;
		line-height: 1.45;
		color: var(--tx);
	}

	.issue-desc :global(p) { margin: 0.125rem 0; }
	.issue-desc :global(code) {
		background: rgb(from var(--ac) r g b / 0.05);
		border-radius: var(--r2);
		padding: 0 0.2rem;
		font-size: 0.8rem;
	}

	.issue-footer {
		display: flex;
		justify-content: flex-end;
		margin-top: 0.5rem;
	}

	.created-label {
		display: inline-flex;
		align-items: center;
		gap: 0.25rem;
		font-size: 0.75rem;
		color: var(--ok);
		font-weight: 500;
	}
</style>
