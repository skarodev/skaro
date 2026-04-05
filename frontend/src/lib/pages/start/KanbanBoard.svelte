<script>
	import { t } from '$lib/i18n/index.js';
	import { MessageCircle, ClipboardList, Code, FlaskConical, CircleCheckBig } from 'lucide-svelte';

	let { tasks = [] } = $props();

	/** Task-level phases in pipeline order. */
	const TASK_PHASES = ['clarify', 'plan', 'implement', 'tests'];

	/** Column definitions with phase key, icon, and color. */
	const COLUMNS = [
		{ key: 'clarify',   icon: MessageCircle,  color: 'var(--ac)' },
		{ key: 'plan',      icon: ClipboardList,   color: 'var(--warn)' },
		{ key: 'implement', icon: Code,            color: 'var(--ac)' },
		{ key: 'tests',     icon: FlaskConical,    color: 'var(--warn)' },
		{ key: 'done',      icon: CircleCheckBig,  color: 'var(--ok)' },
	];

	/** Check if all task phases are complete. */
	function isTaskDone(task) {
		return task.phases &&
			Object.keys(task.phases).length > 0 &&
			TASK_PHASES.every(k => task.phases[k] === 'complete');
	}

	/** Determine which column a task belongs to (first incomplete phase, or 'done'). */
	function taskColumn(task) {
		if (isTaskDone(task)) return 'done';
		const ph = task.phases || {};
		for (const key of TASK_PHASES) {
			if (ph[key] !== 'complete') return key;
		}
		return 'clarify';
	}

	/** Whether a task is actively being worked on (has in_progress/draft/awaiting_review). */
	function isActive(task) {
		const ph = task.phases || {};
		return Object.values(ph).some(
			s => s === 'in_progress' || s === 'draft' || s === 'awaiting_review'
		);
	}

	/** Tasks grouped by column key. */
	let columns = $derived.by(() => {
		const grouped = {};
		for (const col of COLUMNS) grouped[col.key] = [];
		for (const task of tasks) {
			const col = taskColumn(task);
			if (grouped[col]) grouped[col].push(task);
		}
		return grouped;
	});

	/** Summary counts. */
	let doneCount = $derived(tasks.filter(isTaskDone).length);
	let totalCount = $derived(tasks.length);

	/** Format milestone slug for display. */
	function fmtMilestone(slug) {
		return (slug || '')
			.replace(/^\d+-/, '')
			.replace(/-/g, ' ')
			.replace(/\b\w/g, c => c.toUpperCase()) || slug;
	}
</script>

<!-- Summary bar -->
<div class="kb-summary">
	<span class="kb-summary-count">{doneCount}<span class="kb-summary-sep">/</span>{totalCount}</span>
	<span class="kb-summary-label">{$t('start.tasks_done')}</span>
</div>

<!-- Kanban board -->
<div class="kb-board">
	{#each COLUMNS as col}
		{@const items = columns[col.key]}
		{@const Icon = col.icon}
		<div class="kb-column">
			<div class="kb-col-header">
				<Icon size={14} />
				<span class="kb-col-title">{$t('phase.' + col.key)}</span>
				<span class="kb-col-count">{items.length}</span>
			</div>
			<div class="kb-col-body">
				{#each items as task (task.name)}
					{@const active = isActive(task)}
					{@const done = col.key === 'done'}
					<a
						class="kb-card"
						class:kb-card-active={active}
						class:kb-card-done={done}
						href="/tasks/{encodeURIComponent(task.name)}"
					>
						<span class="kb-card-accent" style="background: {done ? 'var(--ok)' : active ? 'var(--warn)' : 'var(--bd)'}"></span>
						<div class="kb-card-body">
							<span class="kb-card-name">{task.name}</span>
							{#if task.context}
								<p class="kb-card-desc">{task.context}</p>
							{/if}
							{#if task.milestone}
								<span class="kb-card-ms">{fmtMilestone(task.milestone)}</span>
							{/if}
						</div>
					</a>
				{/each}
				{#if items.length === 0}
					<div class="kb-empty"></div>
				{/if}
			</div>
		</div>
	{/each}
</div>

<style>
	/* ── Summary ── */

	.kb-summary {
		display: flex;
		align-items: baseline;
		gap: 0.375rem;
		margin-bottom: 1rem;
	}

	.kb-summary-count {
		font-size: 1.125rem;
		font-weight: 700;
		color: var(--tx-bright);
		font-family: var(--font-ui);
	}

	.kb-summary-sep {
		color: var(--tx-dim);
		font-weight: 400;
		margin: 0 0.0625rem;
	}

	.kb-summary-label {
		font-size: 0.8125rem;
		color: var(--tx-dim);
	}

	/* ── Board ── */

	.kb-board {
		display: flex;
		gap: 0.625rem;
		overflow-x: auto;
		padding-bottom: 0.25rem;
		/* subtle scrollbar */
		scrollbar-width: thin;
	}

	/* ── Column ── */

	.kb-column {
		flex: 1 1 0;
		min-width: 13rem;
		display: flex;
		flex-direction: column;
		background: var(--bg-deep);
		border-radius: var(--r);
		padding: 2px;
	}

	.kb-col-header {
		display: flex;
		align-items: center;
		gap: 0.375rem;
		padding: 0.5rem 0.625rem 0.375rem;
		color: var(--tx-dim);
		font-size: 0.75rem;
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.03em;
		user-select: none;
	}

	.kb-col-title {
		flex: 1;
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.kb-col-count {
		flex-shrink: 0;
		min-width: 1.125rem;
		padding: 0 0.25rem;
		border-radius: 0.375rem;
		background: var(--sf);
		color: var(--tx-dim);
		font-size: 0.6875rem;
		font-family: var(--font-ui);
		line-height: 1.125rem;
		text-align: center;
	}

	/* ── Card list ── */

	.kb-col-body {
		display: flex;
		flex-direction: column;
		gap: 2px;
		flex: 1;
		min-height: 2rem;
	}

	.kb-empty {
		flex: 1;
		min-height: 2rem;
	}

	/* ── Card ── */

	.kb-card {
		display: flex;
		background: var(--bg);
		border-radius: var(--r);
		text-decoration: none;
		color: inherit;
		overflow: hidden;
		transition: background .15s, box-shadow .15s;
		cursor: pointer;
	}

	.kb-card:hover {
		background: var(--bg-high);
		box-shadow: 0 1px 4px rgba(0, 0, 0, .12);
	}

	.kb-card-accent {
		width: 3px;
		flex-shrink: 0;
		border-radius: var(--r) 0 0 var(--r);
	}

	.kb-card-body {
		flex: 1;
		min-width: 0;
		padding: 0.5rem 0.625rem;
	}

	.kb-card-name {
		display: block;
		font-size: 0.8125rem;
		font-weight: 600;
		color: var(--tx-bright);
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.kb-card-done .kb-card-name {
		text-decoration: line-through;
		color: var(--tx-dim);
	}

	.kb-card-desc {
		font-size: 0.75rem;
		color: var(--tx-dim);
		line-height: 1.45;
		margin: 0.25rem 0 0;
		display: -webkit-box;
		-webkit-line-clamp: 2;
		-webkit-box-orient: vertical;
		overflow: hidden;
	}

	.kb-card-ms {
		display: inline-block;
		font-size: 0.625rem;
		color: var(--tx-dim);
		background: var(--sf);
		padding: 0.0625rem 0.3125rem;
		border-radius: 0.25rem;
		margin-top: 0.375rem;
		text-transform: uppercase;
		letter-spacing: 0.02em;
	}

	/* ── Responsive ── */

	@media (max-width: 768px) {
		.kb-board {
			gap: 0.5rem;
		}

		.kb-column {
			min-width: 11rem;
		}
	}
</style>
