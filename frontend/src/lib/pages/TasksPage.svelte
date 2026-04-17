<script>
	import { t } from '$lib/i18n/index.js';
	import { status } from '$lib/stores/statusStore.js';
	import { addLog, addError } from '$lib/stores/logStore.js';
	import { invalidate } from '$lib/api/cache.js';
	import { api } from '$lib/api/client.js';
	import { Plus, GripVertical, Rocket } from 'lucide-svelte';
	import TaskListItem from '$lib/pages/tasks/TaskListItem.svelte';
	import CreateTaskModal from '$lib/pages/tasks/CreateTaskModal.svelte';
	import AutopilotOverlay from '$lib/pages/tasks/AutopilotOverlay.svelte';
	import BtnGroup from '$lib/ui/BtnGroup.svelte';
	import { startAutopilot, autopilotRunning } from '$lib/stores/autopilotStore.js';
	import Tooltip from '$lib/ui/Tooltip.svelte';

	let architectureReady = $derived(!!$status?.architecture_reviewed);

	let activeTab = $state('__all__');
	let statusFilter = $state('all');

	let statusFilterItems = $derived([
		{ value: 'all', label: $t('task.filter_all') },
		{ value: 'active', label: $t('task.filter_active') },
		{ value: 'done', label: $t('task.filter_done') },
	]);

	// ── Create modal ──
	let showCreateModal = $state(false);
	let createLoading = $state(false);

	// ── Drag & Drop state ──
	let dragIndex = $state(-1);
	let overIndex = $state(-1);

	/** Returns true when all relevant phases of a task are complete. */
	function isTaskDone(task) {
		const phases = task.phases;
		if (!phases || Object.keys(phases).length === 0) return false;
		return ['clarify', 'plan', 'implement', 'tests'].every(
			(k) => phases[k] === 'complete'
		);
	}

	/** Whether there are incomplete tasks that autopilot can process. */
	let hasActiveTasks = $derived(
		($status?.tasks || []).some((t) => !isTaskDone(t))
	);

	/** Apply status filter to a task list. */
	function applyStatusFilter(tasks) {
		if (statusFilter === 'done') return tasks.filter(isTaskDone);
		if (statusFilter === 'active') return tasks.filter((t) => !isTaskDone(t));
		return tasks;
	}

	/** Sorted unique milestones extracted from all tasks. */
	let milestones = $derived.by(() => {
		const tasks = $status?.tasks || [];
		const set = new Set();
		for (const task of tasks) {
			if (task.milestone) set.add(task.milestone);
		}
		return [...set].sort();
	});

	/** Tasks for a given tab (milestone filter only). */
	function tasksForTab(tabId) {
		const tasks = $status?.tasks || [];
		return tabId === '__all__' ? tasks : tasks.filter((t) => t.milestone === tabId);
	}

	/** Tabs: "All" + one per milestone. */
	let tabs = $derived.by(() => [
		{ id: '__all__', label: $t('task.all_milestones') },
		...milestones.map((ms) => ({ id: ms, label: formatMilestone(ms) })),
	]);

	/** Tasks visible in the content area - both filters applied. */
	let filteredTasks = $derived.by(() =>
		applyStatusFilter(tasksForTab(activeTab))
	);

	/** Name of the first non-done task — only this one gets the "active" highlight. */
	let firstActiveName = $derived.by(() => {
		const tasks = filteredTasks;
		for (const task of tasks) {
			if (!isTaskDone(task)) return task.ref || task.name;
		}
		return '';
	});

	/** DnD is available when status filter is "all" (so ordering is unambiguous). */
	let canReorder = $derived(statusFilter === 'all');

	function formatMilestone(slug) {
		return (slug || '')
			.replace(/^\d+-/, '')
			.replace(/-/g, ' ')
			.replace(/\b\w/g, (c) => c.toUpperCase()) || slug;
	}

	/** Badge count for a tab - respects the active status filter. */
	function tabCount(tabId) {
		return applyStatusFilter(tasksForTab(tabId)).length;
	}

	// ── Create Task ──
	async function handleCreate({ name, milestone }) {
		createLoading = true;
		try {
			await api.createTask(name, milestone);
			addLog($t('log.task_created', { name, milestone }));
			invalidate('status');
			status.set(await api.getStatus());
			showCreateModal = false;
		} catch (e) {
			addError(e.message, 'createTask');
		}
		createLoading = false;
	}

	// ── Drag & Drop ──
	/** Milestone of the task currently being dragged. */
	let dragMilestone = $state('');

	function handleDragStart(e, idx) {
		dragIndex = idx;
		dragMilestone = filteredTasks[idx]?.milestone || '';
		e.dataTransfer.effectAllowed = 'move';
		e.dataTransfer.setData('text/plain', String(idx));
	}

	function handleDragOver(e, idx) {
		e.preventDefault();
		// Only show drop indicator for same-milestone tasks
		const targetTask = filteredTasks[idx];
		if (targetTask && targetTask.milestone === dragMilestone) {
			e.dataTransfer.dropEffect = 'move';
			overIndex = idx;
		} else {
			e.dataTransfer.dropEffect = 'none';
			overIndex = -1;
		}
	}

	function handleDragLeave() {
		overIndex = -1;
	}

	function handleDrop(e) {
		e.preventDefault();
		if (dragIndex < 0 || overIndex < 0 || dragIndex === overIndex) {
			resetDrag();
			return;
		}

		const tasks = [...filteredTasks];
		const draggedTask = tasks[dragIndex];
		const targetTask = tasks[overIndex];

		// Safety: only reorder within same milestone
		if (!draggedTask || !targetTask || draggedTask.milestone !== targetTask.milestone) {
			resetDrag();
			return;
		}

		const milestone = draggedTask.milestone;

		// Extract just this milestone's tasks in their current order
		const milestoneTasks = tasks.filter((t) => t.milestone === milestone);
		const dragMsIdx = milestoneTasks.indexOf(draggedTask);
		const overMsIdx = milestoneTasks.indexOf(targetTask);

		const [moved] = milestoneTasks.splice(dragMsIdx, 1);
		milestoneTasks.splice(overMsIdx, 0, moved);

		const newOrder = milestoneTasks.map((t) => t.name);
		resetDrag();
		persistOrder(milestone, newOrder);
	}

	function handleDragEnd() {
		resetDrag();
	}

	function resetDrag() {
		dragIndex = -1;
		overIndex = -1;
		dragMilestone = '';
	}

	async function persistOrder(milestone, taskNames) {
		try {
			await api.reorderTasks(milestone, taskNames);
			addLog($t('log.tasks_reordered'));
			invalidate('status');
			status.set(await api.getStatus());
		} catch (e) {
			addError(e.message, 'reorderTasks');
		}
	}
</script>

<div class="page-with-tabs">
	<div class="main-header">
		<div class="header-left">
			<h2>{$t('task.title')}</h2>
		</div>
		<div class="header-right">
            <div class="header-right-group">
                {#if $status?.tasks?.length}
                    <BtnGroup items={statusFilterItems} bind:value={statusFilter} />
                {/if}

                <div class="task-actions">
                    {#if hasActiveTasks}
                        <Tooltip text={!architectureReady ? $t('gate.need_architecture') : ''} placement="bottom">
                        <button
                                class="btn btn-autopilot"
                                disabled={$autopilotRunning || !architectureReady}
                                onclick={startAutopilot}
                        >
                            <Rocket size={14} /> {$t('autopilot.run_all')}
                        </button>
                        </Tooltip>
                    {/if}
                    <Tooltip text={!architectureReady ? $t('gate.need_architecture') : ''} placement="bottom">
                    <button class="btn btn-primary" onclick={() => showCreateModal = true} disabled={!architectureReady}>
                        <Plus size={14} /> {$t('task.create')}
                    </button>
                    </Tooltip>
                </div>
            </div>
		</div>
	</div>

	{#if !$status?.tasks?.length}
		<div class="card empty">
			<p>{$t('task.empty')}</p>
			<p class="hint">{$t('task.empty_hint')}</p>
			<div class="btn-group" style="justify-content: center;">
				<Tooltip text={!architectureReady ? $t('gate.need_architecture') : ''} placement="bottom">
				<button class="btn btn-primary" onclick={() => showCreateModal = true} disabled={!architectureReady}>
					<Plus size={14} /> {$t('task.create')}
				</button>
				</Tooltip>
			</div>
		</div>
	{:else}
		<div class="milestone-tabs-layout">
			<nav class="milestone-tabs-nav">
				{#each tabs as tab}
					{@const count = tabCount(tab.id)}
					<button
						class="tab-item"
						class:active={activeTab === tab.id}
						onclick={() => activeTab = tab.id}
					>
						<span class="tab-label">{tab.label}</span>
						<span class="tab-badge" class:tab-badge-active={activeTab === tab.id}>{count}</span>
					</button>
				{/each}
			</nav>
			<div class="milestone-tabs-content roadmap" role="list">
				{#each filteredTasks as task, i (task.ref || task.name)}
					{@const isDragging = dragIndex === i}
					{@const isOver = overIndex === i && dragIndex !== i}
					{@const sameMilestone = dragMilestone === '' || task.milestone === dragMilestone}
					<div
						class="drag-wrapper"
						class:drag-active={isDragging}
						class:drag-over-above={isOver && dragIndex > i}
						class:drag-over-below={isOver && dragIndex < i}
						class:drag-foreign={dragIndex >= 0 && !isDragging && !sameMilestone}
						draggable={canReorder}
						ondragstart={(e) => handleDragStart(e, i)}
						ondragover={(e) => handleDragOver(e, i)}
						ondragleave={handleDragLeave}
						ondrop={handleDrop}
						ondragend={handleDragEnd}
						role="listitem"
					>
						{#if canReorder}
							<span class="drag-grip"><GripVertical size={16} /></span>
						{/if}
						<div class="drag-card-wrap">
							<TaskListItem
								{task}
								href="/tasks/{encodeURIComponent(task.ref || task.name)}"
								isFirst={i === 0}
								isLast={i === filteredTasks.length - 1}
								isActive={(task.ref || task.name) === firstActiveName}
							/>
						</div>
					</div>
				{/each}
				{#if filteredTasks.length === 0}
					<div class="card empty">
						<p class="hint">{$t('task.filter_empty_' + statusFilter)}</p>
					</div>
				{/if}
			</div>
		</div>
	{/if}
</div>

<!-- Create Task Modal -->
{#if showCreateModal}
	<CreateTaskModal
		milestones={milestones}
		loading={createLoading}
		onConfirm={handleCreate}
		onClose={() => showCreateModal = false}
	/>
{/if}

<!-- Autopilot Mission Control overlay -->
<AutopilotOverlay />

<style>
	.main-header {
		display: flex;
		gap: 1rem;
	}

	.header-left {
		width: 12rem;
	}

	.header-right {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		flex-shrink: 0;
        padding-left: 2.2rem;
        flex: 1 1 0;
        min-width: 0;
	}

    .header-right-group {
        display: flex;
        justify-content: space-between;
        width: 100%;
    }

    .task-actions {
        display: flex;
        align-items: center;
        gap: 0.75rem;
    }

	/* Layout */
	.milestone-tabs-layout {
		display: flex;
		gap: 1.5rem;
		margin-top: 1rem;
	}

	.milestone-tabs-nav {
		position: sticky;
		top: 0;
		width: 12rem;
		flex-shrink: 0;
		align-self: flex-start;
		display: flex;
		flex-direction: column;
		gap: .1rem;
		padding: 0;
	}

	/* Tab items */
	.tab-item {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.5rem;
		width: 100%;
		padding: .25rem .5rem;
		border: none;
		border-radius: var(--r);
		background: none;
		color: var(--tx-bright);
		font-size: 1rem;
		font-family: inherit;
		text-align: left;
		cursor: pointer;
		transition: background .1s;
	}

	.tab-item:hover {
		background: var(--bg-high);
	}

	.tab-item.active {
		background: var(--bg-deep);
		color: var(--tx-bright);
	}

	.tab-label {
		flex: 1;
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	/* Tab badge */
	.tab-badge {
		flex-shrink: 0;
		min-width: 1.25rem;
		padding: 0 0.375rem;
		border-radius: 0.5rem;
		background: var(--sf);
		color: var(--tx-dim);
		font-size: 0.75rem;
		font-family: var(--font-ui);
		line-height: 1.25rem;
		text-align: center;
		transition: background .1s, color .1s;
	}

	.tab-badge-active {
		background: color-mix(in srgb, var(--ac) 15%, transparent);
		color: var(--ac);
	}

	/* Content area */
	.milestone-tabs-content {
		flex: 1;
		min-width: 0;
		display: flex;
		flex-direction: column;
		gap: 0;
	}

	/* Roadmap continuous connector layout */
	.roadmap {
		position: relative;
	}

	/* ── Drag & Drop ── */
	.drag-wrapper {
		display: flex;
		align-items: stretch;
		gap: 0;
		border-radius: var(--r);
		transition: opacity .15s;
		position: relative;
	}

	.drag-wrapper .drag-card-wrap {
		flex: 1;
		min-width: 0;
	}

	.drag-grip {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 1.75rem;
		flex-shrink: 0;
		color: var(--tx-dim);
		cursor: grab;
		opacity: 0;
		transition: opacity .15s;
		user-select: none;
	}

	.drag-wrapper:hover .drag-grip {
		opacity: 1;
	}

	.drag-grip:active { cursor: grabbing; }

	.drag-active {
		opacity: 0.4;
	}

	/* Dim cards from other milestones while dragging */
	.drag-foreign {
		opacity: 0.3;
		pointer-events: none;
	}

	.drag-over-above {
		box-shadow: 0 -0.125rem 0 0 var(--ac);
	}

	.drag-over-below {
		box-shadow: 0 0.125rem 0 0 var(--ac);
	}

	/* Autopilot button */
	.btn-autopilot {
		background: linear-gradient(135deg, rgba(88, 157, 246, 0.12), rgba(152, 118, 170, 0.12));
		border: 1px solid var(--ac);
		color: var(--ac);
		transition: all 0.2s;
	}

	.btn-autopilot:hover:not(:disabled) {
		background: linear-gradient(135deg, rgba(88, 157, 246, 0.22), rgba(152, 118, 170, 0.22));
		border-color: var(--ac);
		box-shadow: 0 0 12px rgba(88, 157, 246, 0.15);
	}

	.btn-autopilot:disabled {
		opacity: 0.4;
		cursor: not-allowed;
	}
</style>
