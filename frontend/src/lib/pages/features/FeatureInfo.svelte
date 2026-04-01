<script>
	import { t } from '$lib/i18n/index.js';
	import { Boxes, BadgeCheck, FolderOpen } from 'lucide-svelte';
	import PhaseBar from '$lib/ui/PhaseBar.svelte';

	let { feature = {} } = $props();

	let tasks = $derived(feature?.task_details || []);
	let adrs = $derived(feature?.adr_details || []);
</script>

{#if feature.description}
	<div class="section">
		<h3 class="section-label">{$t('feature.description')}</h3>
		<p class="description">{feature.description}</p>
	</div>
{/if}

<div class="section">
	<span class="meta-line"><strong>{$t('feature.created')}:</strong> {feature.created_at || '—'}</span>
</div>

{#if tasks.length > 0}
	<div class="section">
		<h3 class="section-label">{$t('feature.linked_tasks')} ({tasks.length})</h3>
		<div class="task-list">
			{#each tasks as task}
				<a class="card task-item" href="/tasks/{encodeURIComponent(task.name)}">
					<div class="task-head">
						<h4>
							{#if task.progress_percent === 100}
								<span class="status-icon complete"><BadgeCheck size={18} /></span>
							{:else}
								<span class="status-icon wip"><Boxes size={18} /></span>
							{/if}
							{task.name}
						</h4>
						<span class="milestone-badge">{task.milestone}</span>
					</div>
					<div class="task-meta">
						<span class="phase-label">{task.current_phase}</span>
						<span class="progress-label">{task.progress_percent}%</span>
					</div>
				</a>
			{/each}
		</div>
	</div>
{/if}

{#if adrs.length > 0}
	<div class="section">
		<h3 class="section-label">{$t('feature.linked_adrs')} ({adrs.length})</h3>
		<div class="adr-list">
			{#each adrs as adr}
				<a class="card adr-item" href="/adr">
					<FolderOpen size={16} />
					<span class="adr-name">ADR-{String(adr.number).padStart(3, '0')}: {adr.title}</span>
					<span class="badge {adr.status === 'accepted' ? 'badge-accepted' : 'badge-proposed'}">
						{adr.status}
					</span>
				</a>
			{/each}
		</div>
	</div>
{/if}

{#if tasks.length === 0 && adrs.length === 0}
	<div class="section">
		<p class="empty-hint">{$t('feature.no_artifacts')}</p>
	</div>
{/if}

<style>
	.section {
		margin-bottom: 1.25rem;
	}

	.section-label {
		font-size: 0.8125rem;
		color: var(--tx-dim);
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: .03em;
		margin: 0 0 0.5rem;
	}

	.description {
		font-size: 0.875rem;
		color: var(--tx);
		margin: 0;
		line-height: 1.5;
	}

	.meta-line {
		font-size: 0.8125rem;
		color: var(--tx-dim);
		font-family: var(--font-ui);
	}

	/* ── Task list ── */
	.task-list {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}

	.task-item {
		display: block;
		text-decoration: none;
		color: inherit;
		cursor: pointer;
		transition: box-shadow .2s;
	}

	.task-item:hover {
		box-shadow: 0 .5rem 2rem rgba(0, 0, 0, .1);
		text-decoration: none;
	}

	.task-head {
		display: flex;
		justify-content: space-between;
		align-items: center;
	}

	.task-head h4 {
		margin: 0;
		display: flex;
		align-items: center;
		gap: 0.5rem;
		font-size: 0.9375rem;
	}

	.status-icon { display: flex; align-items: center; flex-shrink: 0; }
	.status-icon.complete { color: var(--ok); }
	.status-icon.wip { color: var(--tx-bright); }

	.milestone-badge {
		font-size: 0.6875rem;
		padding: 0.125rem 0.5rem;
		border-radius: 0.25rem;
		background: color-mix(in srgb, var(--ac) 12%, transparent);
		color: var(--ac);
		font-family: var(--font-ui);
		letter-spacing: 0.019rem;
		white-space: nowrap;
	}

	.task-meta {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		margin-top: 0.375rem;
		font-size: 0.75rem;
		color: var(--tx-dim);
		font-family: var(--font-ui);
	}

	/* ── ADR list ── */
	.adr-list {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}

	.adr-item {
		display: flex;
		align-items: center;
		gap: 0.625rem;
		text-decoration: none;
		color: var(--tx);
		cursor: pointer;
		transition: box-shadow .2s;
	}

	.adr-item:hover {
		box-shadow: 0 .5rem 2rem rgba(0, 0, 0, .1);
		text-decoration: none;
	}

	.adr-name {
		flex: 1;
		font-size: 0.875rem;
	}

	.badge {
		display: inline-block;
		padding: 0.125rem 0.5rem;
		border-radius: 0.625rem;
		font-size: 0.75rem;
		font-weight: 500;
		line-height: 1.125rem;
		white-space: nowrap;
	}
	.badge-proposed { background: rgba(187, 181, 41, .12); color: var(--warn); }
	.badge-accepted { background: color-mix(in srgb, var(--ok) 15%, transparent); color: var(--ok); }

	.empty-hint {
		color: var(--tx-dim);
		font-size: 0.8125rem;
	}
</style>
