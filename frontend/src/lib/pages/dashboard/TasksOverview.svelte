<script>
	import { t } from '$lib/i18n/index.js';
	import { Package, MessageCircle, ClipboardList, Code, FlaskConical, Check, CircleCheckBig } from 'lucide-svelte';

	let { tasks = [] } = $props();

	const phaseKeys = [
		{ key: 'clarify', icon: MessageCircle },
		{ key: 'plan', icon: ClipboardList },
		{ key: 'implement', icon: Code },
		{ key: 'tests', icon: FlaskConical },
		{ key: 'done', icon: CircleCheckBig },
	];

	function isTaskDone(task) {
		return ['clarify', 'plan', 'implement', 'tests'].every(k => task.phases?.[k] === 'complete');
	}

	let doneCount = $derived(tasks.filter(isTaskDone).length);
	let openCount = $derived(tasks.length - doneCount);

	function phaseStatus(task, key) {
		if (key === 'done') return isTaskDone(task) ? 'ok' : '';
		const s = task.phases?.[key] || 'not_started';
		if (s === 'complete') return 'ok';
		if (['in_progress', 'draft', 'awaiting_review'].includes(s)) return 'wip';
		return '';
	}
</script>

<div class="widget lg card">
	<div class="section-head">
		<h3>
			<Package size={16} /> {$t('dash.tasks_overview')}
			{#if tasks?.length}
				<span class="tasks-stats">{doneCount} ✓ / {openCount} ○ / {tasks.length} {$t('dash.tasks_total')}</span>
			{/if}
		</h3>
		<a class="sec-btn" href="/tasks">{$t('dash.view_all')}</a>
	</div>
	{#if tasks?.length}
		<div class="feat-grid">
			{#each tasks as f}
				<a class="feat-item" href="/tasks/{encodeURIComponent(f.ref || f.name)}">
					<div class="feat-top">
						<span class="feat-name">{f.name}</span>
						<span class="feat-phase">{f.milestone}</span>
					</div>
					<div class="mini-phases">
						{#each phaseKeys as phase, i}
							{@const cls = phaseStatus(f, phase.key)}
							{@const Icon = phase.icon}
							<div class="mp-cell">
								{#if i < phaseKeys.length - 1}
									{@const nextCls = phaseStatus(f, phaseKeys[i + 1].key)}
									<div class="mp-line" class:mp-line-ok={cls === 'ok'} class:mp-line-half={cls === 'ok' && nextCls !== 'ok'}></div>
								{/if}
								<div class="mp-dot {cls}">
									{#if cls === 'ok'}
										<Check size={12} strokeWidth={2.5} />
									{:else}
										<Icon size={12} strokeWidth={1.5} />
									{/if}
								</div>
							</div>
						{/each}
					</div>
				</a>
			{/each}
		</div>
	{:else}
		<p class="empty-hint">{$t('dash.no_data')}</p>
	{/if}
</div>

<style>
	/* .section-head, .sec-btn → app.css */

	.feat-grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(14rem, 1fr));
		gap: 0.625rem;
		max-height: 18.75rem;
		overflow-y: auto;
	}

	.feat-item {
		background: var(--bg-deep);
		border: none;
		border-radius: var(--r2);
		padding: 0.625rem 0.75rem;
		text-decoration: none;
		transition: background .15s;
		cursor: pointer;
	}

	.feat-item:hover { background: color-mix(in srgb, var(--ac) 10%, transparent); }

	.tasks-stats {
		font-size: 0.6875rem;
		font-weight: 400;
		color: var(--tx-dim);
		margin-left: 0.5rem;
	}

	.feat-top {
		display: flex;
		align-items: center;
		justify-content: space-between;
		margin-bottom: 0.625rem;
	}

	.feat-name {
		font-size: 0.8125rem;
		font-weight: 600;
		color: var(--tx-bright);
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.feat-phase {
		font-size: 0.625rem;
		color: var(--tx-dim);
		text-transform: uppercase;
		letter-spacing: 0.025rem;
		background: var(--sf);
		padding: 0.125rem 0.375rem;
		border-radius: 0.25rem;
		flex-shrink: 0;
		margin-left: 0.5rem;
	}

	/* ── Mini phase pipeline (full-width) ── */

	.mini-phases {
		display: flex;
		align-items: center;
		width: 100%;
	}

	.mp-cell {
		flex: 1;
		display: flex;
		flex-direction: column;
		align-items: center;
		position: relative;
	}

	.mp-line {
		position: absolute;
		top: 0.625rem;
		left: 50%;
		right: -50%;
		height: 0.125rem;
		background: var(--bd);
		z-index: 0;
		transition: background .2s;
	}

	.mp-line.mp-line-ok { background: var(--ok); }
	.mp-line.mp-line-half {
		background: linear-gradient(to right, var(--ok), var(--bd));
	}

	.mp-cell:last-child .mp-line { display: none; }

	.mp-dot {
		width: 1.375rem;
		height: 1.375rem;
		border-radius: 50%;
		background: var(--bg-deep);
		border: 0.125rem solid var(--bd);
		display: flex;
		align-items: center;
		justify-content: center;
		position: relative;
		z-index: 1;
		color: var(--tx-dim);
		transition: all .2s;
	}

	.mp-dot.ok {
		background: var(--ok);
		border-color: var(--ok);
		color: #fff;
	}

	.mp-dot.wip {
		background: var(--warn);
		border-color: var(--warn);
		color: var(--bg-deep);
	}
</style>
