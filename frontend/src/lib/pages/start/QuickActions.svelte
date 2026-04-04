<script>
	import { t } from '$lib/i18n/index.js';
	import { Zap, Plus, ShieldCheck, GitBranch, Sparkles } from 'lucide-svelte';

	let { status } = $props();

	let allTasksDone = $derived.by(() => {
		const tasks = status?.tasks;
		if (!tasks || tasks.length === 0) return false;
		return tasks.every(f => f.phases?.tests === 'complete');
	});

	/** Find the first in-progress task to link to */
	let currentTask = $derived.by(() => {
		const tasks = status?.tasks || [];
		return tasks.find(t => {
			return !['clarify', 'plan', 'implement', 'tests'].every(k => t.phases?.[k] === 'complete');
		});
	});

	let actions = $derived.by(() => {
		const list = [];

		if (currentTask) {
			list.push({
				id: 'current_task',
				icon: Zap,
				href: '/tasks/' + encodeURIComponent(currentTask.name),
				accent: true,
			});
		}

		list.push({
			id: 'create_task',
			icon: Plus,
			href: '/tasks',
		});

		list.push({
			id: 'new_feature',
			icon: Sparkles,
			href: '/features',
		});

		if (allTasksDone) {
			list.push({
				id: 'run_review',
				icon: ShieldCheck,
				href: '/review',
			});
		}

		list.push({
			id: 'open_git',
			icon: GitBranch,
			href: '/git',
		});

		return list;
	});
</script>

<div class="card quick-actions">
	<h3><Zap size={16} /> {$t('start.quick_actions')}</h3>
	<div class="qa-grid">
		{#each actions as action}
			{@const Icon = action.icon}
			<a class="qa-item" class:qa-accent={action.accent} href={action.href}>
				<span class="qa-icon"><Icon size={16} /></span>
				<span class="qa-label">{$t('start.action_' + action.id)}</span>
			</a>
		{/each}
	</div>
</div>

<style>
	.quick-actions {
		grid-column: span 4;
	}

	.qa-grid {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
	}

	.qa-item {
		display: flex;
		align-items: center;
		gap: 0.375rem;
		padding: 0.5rem 0.875rem;
		border-radius: var(--r);
		background: var(--bg-deep);
		border: 1px solid var(--bd);
		color: var(--tx-bright);
		font-size: 0.8125rem;
		font-weight: 500;
		text-decoration: none;
		transition: all .15s;
		cursor: pointer;
		white-space: nowrap;
	}

	.qa-item:hover {
		background: var(--sf2);
		border-color: var(--bd2);
	}

	.qa-item.qa-accent {
		border-color: color-mix(in srgb, var(--ac) 40%, transparent);
		background: color-mix(in srgb, var(--ac) 8%, transparent);
		color: var(--ac);
	}

	.qa-item.qa-accent:hover {
		background: color-mix(in srgb, var(--ac) 14%, transparent);
		border-color: color-mix(in srgb, var(--ac) 55%, transparent);
	}

	.qa-icon {
		display: flex;
		align-items: center;
		flex-shrink: 0;
	}
</style>
