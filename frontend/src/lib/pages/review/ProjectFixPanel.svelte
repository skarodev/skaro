<script>
	import { t } from '$lib/i18n/index.js';
	import { onMount } from 'svelte';
	import { api } from '$lib/api/client.js';
	import { status } from '$lib/stores/statusStore.js';
	import { addLog } from '$lib/stores/logStore.js';
	import { ChevronDown, ChevronRight } from 'lucide-svelte';
	import FixChat from '$lib/ui/FixChat.svelte';

	// Scope selection (unique to project-level fix)
	let scopeData = $state(null);
	let selectedTasks = $state([]);
	let scopeExpanded = $state(false);

	let allTaskNames = $derived(
		scopeData?.milestones?.flatMap((ms) => ms.tasks) || []
	);
	let allSelected = $derived(
		allTaskNames.length > 0 && selectedTasks.length === allTaskNames.length
	);

	let modelDisplay = $derived.by(() => {
		const s = $status;
		if (!s?.config) return '';
		const cfg = s.config;
		if (cfg.roles?.reviewer) return `${cfg.roles.reviewer.provider} / ${cfg.roles.reviewer.model}`;
		return `${cfg.llm_provider} / ${cfg.llm_model}`;
	});

	onMount(() => { loadScope(); });

	async function loadScope() {
		try {
			scopeData = await api.getReviewScope();
			if (scopeData?.milestones) {
				selectedTasks = scopeData.milestones.flatMap((ms) => ms.tasks);
			}
		} catch { /* ignore */ }
	}

	function toggleTask(taskName) {
		if (selectedTasks.includes(taskName)) {
			selectedTasks = selectedTasks.filter((t) => t !== taskName);
		} else {
			selectedTasks = [...selectedTasks, taskName];
		}
	}

	function toggleMilestone(tasks) {
		const msAllSelected = tasks.every((t) => selectedTasks.includes(t));
		if (msAllSelected) {
			selectedTasks = selectedTasks.filter((t) => !tasks.includes(t));
		} else {
			const toAdd = tasks.filter((t) => !selectedTasks.includes(t));
			selectedTasks = [...selectedTasks, ...toAdd];
		}
	}

	// API callbacks
	function loadConversationFn() {
		return api.loadProjectFixConversation();
	}

	function sendMessageFn(text, history, signal, scopePaths) {
		return api.sendProjectFix(text, history, allSelected ? [] : selectedTasks, scopePaths, signal);
	}

	function applyFileFn(filepath, content) {
		return api.applyProjectFixFile(filepath, content);
	}

	function clearConversationFn() {
		return api.clearProjectFixConversation();
	}

	function onSendSuccess() {
		addLog($t('review.fix_response'));
	}
</script>

<div class="project-fix">
	<!-- Scope selector (unique to project-level) -->
	{#if scopeData && scopeData.milestones?.length > 0}
		<div class="scope-section">
			<!-- svelte-ignore a11y_click_events_have_key_events -->
			<!-- svelte-ignore a11y_no_static_element_interactions -->
			<div class="scope-header" onclick={() => scopeExpanded = !scopeExpanded}>
				{#if scopeExpanded}<ChevronDown size={14} />{:else}<ChevronRight size={14} />{/if}
				<span class="scope-title">{$t('review.scope_title')}</span>
				<span class="scope-hint">
					{allSelected
						? $t('review.scope_all')
						: $t('review.scope_selected', { n: selectedTasks.length })}
				</span>
			</div>
			{#if scopeExpanded}
				<div class="scope-body">
					{#each scopeData.milestones as ms}
						<div class="scope-milestone">
							<label class="scope-ms-label">
								<input
									type="checkbox"
									checked={ms.tasks.every((t) => selectedTasks.includes(t))}
									indeterminate={ms.tasks.some((t) => selectedTasks.includes(t)) && !ms.tasks.every((t) => selectedTasks.includes(t))}
									onchange={() => toggleMilestone(ms.tasks)}
								/>
								<strong>{ms.slug}</strong>
							</label>
							<div class="scope-tasks">
								{#each ms.tasks as taskName}
									<label class="scope-task-label">
										<input
											type="checkbox"
											checked={selectedTasks.includes(taskName)}
											onchange={() => toggleTask(taskName)}
										/>
										{taskName}
									</label>
								{/each}
							</div>
						</div>
					{/each}
				</div>
			{/if}
		</div>
	{/if}

	<FixChat
		{modelDisplay}
		prefillEvent="skaro:prefill-project-fix"
		errorSource="projectFix"
		scopeEnabled={true}
		{loadConversationFn}
		{sendMessageFn}
		loadTreeFn={() => api.getFileTree()}
		{applyFileFn}
		{clearConversationFn}
		{onSendSuccess}
	/>
</div>

<style>
	.project-fix { padding-bottom: 0; }

	.scope-section {
		margin-bottom: 1rem;
		border: 1px solid var(--bd);
		border-radius: var(--r);
		overflow: hidden;
	}

	.scope-header {
		display: flex; align-items: center; gap: 0.5rem;
		padding: 0.5rem 0.75rem;
		cursor: pointer; font-size: 0.8125rem; color: var(--tx);
		transition: background 0.1s;
	}
	.scope-header:hover { background: var(--bg-deep); }
	.scope-title { font-weight: 600; }

	.scope-hint {
		margin-left: auto; font-size: 0.75rem;
		color: var(--dm); font-family: var(--font-ui);
	}

	.scope-body {
		padding: 0.5rem 0.75rem;
		border-top: 1px solid var(--bd);
		display: flex; flex-direction: column; gap: 0.5rem;
	}

	.scope-milestone { display: flex; flex-direction: column; gap: 0.25rem; }

	.scope-ms-label {
		display: flex; align-items: center; gap: 0.375rem;
		font-size: 0.8125rem; color: var(--tx); cursor: pointer;
	}

	.scope-ms-label input,
	.scope-task-label input {
		accent-color: var(--ac); cursor: pointer;
	}

	.scope-tasks {
		padding-left: 1.25rem;
		display: flex; flex-direction: column; gap: 0.125rem;
	}

	.scope-task-label {
		display: flex; align-items: center; gap: 0.375rem;
		font-size: 0.8125rem; color: var(--dm); cursor: pointer;
	}
	.scope-task-label:hover { color: var(--tx); }
</style>
