<script>
	import { t } from '$lib/i18n/index.js';
	import { api } from '$lib/api/client.js';
	import { addLog, addError } from '$lib/stores/logStore.js';
	import {
		RotateCcw, Check, Loader2, Pencil, Plus, Trash2, Save, Wrench,
	} from 'lucide-svelte';
	import CheckList from '$lib/ui/CheckList.svelte';
	import CommandList from '$lib/ui/CommandList.svelte';
	import TestsSummary from '$lib/ui/TestsSummary.svelte';
	import { formatIssueLabel } from '$lib/ui/testUtils.js';

	let {
		taskName = '',
		results = null,
		loading = false,
		confirmed = false,
		onRunTests = () => {},
		onConfirm = () => {},
		onFixFromIssues = (issueIds) => {},
	} = $props();

	let editingTaskCmds = $state(false);
	let editableCmds = $state([]);
	let savingCmds = $state(false);

	// ── Issues state ──
	let issues = $state([]);
	let issuesLoading = $state(false);
	let selectedIssues = $state({});

	let hasErrors = $derived(results && !results.passed);
	let hasResults = $derived(results !== null);
	let hasIssues = $derived(issues.length > 0);
	let selectedCount = $derived(Object.values(selectedIssues).filter(Boolean).length);
	let allSelected = $derived(hasIssues && selectedCount === issues.length);

	// Load issues when results change and have errors
	$effect(() => {
		// Track `results` reference directly so the effect re-runs
		// even when hasErrors stays true across consecutive test runs.
		const r = results;
		if (r && !r.passed && taskName) {
			loadIssues();
		} else {
			issues = [];
			selectedIssues = {};
		}
	});

	async function loadIssues() {
		issuesLoading = true;
		try {
			const data = await api.getTestIssues(taskName);
			issues = data.issues || [];
			// Select all by default
			const sel = {};
			for (const issue of issues) sel[issue.id] = true;
			selectedIssues = sel;
		} catch (e) {
			addError(e.message, 'loadIssues');
			issues = [];
		}
		issuesLoading = false;
	}

	function toggleIssue(id) {
		selectedIssues = { ...selectedIssues, [id]: !selectedIssues[id] };
	}

	function toggleAll() {
		const newVal = !allSelected;
		const sel = {};
		for (const issue of issues) sel[issue.id] = newVal;
		selectedIssues = sel;
	}

	function handleFixIssues() {
		const ids = issues.filter((i) => selectedIssues[i.id]).map((i) => i.id);
		if (ids.length > 0) onFixFromIssues(ids);
	}

	// ── Inline editing ──

	async function startEditingTaskCmds() {
		try {
			const data = await api.getVerifyCommands(taskName);
			editableCmds = (data.commands || []).map((c) => ({ ...c }));
		} catch {
			editableCmds = (results?.task_commands || []).map((c) => ({
				name: c.name,
				command: c.command,
			}));
		}
		editingTaskCmds = true;
	}

	function addCmd() {
		editableCmds = [...editableCmds, { name: '', command: '' }];
	}

	function removeCmd(i) {
		editableCmds = editableCmds.filter((_, idx) => idx !== i);
	}

	async function saveTaskCmds() {
		const valid = editableCmds.filter((c) => c.command.trim());
		savingCmds = true;
		try {
			await api.saveVerifyCommands(taskName, valid);
			addLog($t('tests.commands_saved'));
			editingTaskCmds = false;
		} catch (e) {
			addError(e.message, 'saveVerifyCommands');
		}
		savingCmds = false;
	}

	function cancelEditCmds() {
		editingTaskCmds = false;
		editableCmds = [];
	}
</script>

<div class="tests-panel">
	{#if hasResults}
		<!-- Checklist -->
		<div class="tests-section">
			<h4 class="section-title">{$t('tests.checklist_title')}</h4>
			<CheckList checks={results.checklist} />
		</div>

		<!-- Task commands -->
		<div class="tests-section">
			<div class="section-header">
				<h4 class="section-title">{$t('tests.task_commands_title')}</h4>
				{#if !editingTaskCmds}
					<button class="btn-icon" title={$t('tests.edit_commands')} onclick={startEditingTaskCmds}>
						<Pencil size={13} />
					</button>
				{/if}
			</div>

			{#if editingTaskCmds}
				<div class="cmd-editor">
					{#each editableCmds as cmd, i}
						<div class="cmd-edit-row">
							<input
								class="cmd-input cmd-input-name"
								placeholder={$t('tests.cmd_name_placeholder')}
								bind:value={cmd.name}
							/>
							<input
								class="cmd-input cmd-input-cmd"
								placeholder={$t('tests.cmd_command_placeholder')}
								bind:value={cmd.command}
							/>
							<button class="btn-icon btn-danger" onclick={() => removeCmd(i)} title="Remove">
								<Trash2 size={13} />
							</button>
						</div>
					{/each}
					<div class="cmd-edit-actions">
						<button class="btn btn-sm" onclick={addCmd}>
							<Plus size={13} /> {$t('tests.add_command')}
						</button>
						<div class="cmd-edit-right">
							<button class="btn btn-sm" onclick={cancelEditCmds}>{$t('tests.cancel')}</button>
							<button class="btn btn-sm btn-primary" disabled={savingCmds} onclick={saveTaskCmds}>
								{#if savingCmds}<Loader2 size={13} class="spin" />{:else}<Save size={13} />{/if}
								{$t('tests.save_commands')}
							</button>
						</div>
					</div>
				</div>
			{:else if results.task_commands && results.task_commands.length > 0}
				<CommandList commands={results.task_commands} prefix="task" />
			{:else}
				<div class="hint">{$t('tests.no_task_commands')}</div>
			{/if}
		</div>

		<!-- Summary & Actions -->
		<TestsSummary passed={results.passed} label={results.passed ? $t('tests.all_passed') : $t('tests.has_failures')} />

		<!-- Issues list (when tests have failures) -->
		{#if hasIssues}
			<div class="tests-section issues-section">
				<div class="section-header">
					<h4 class="section-title">{$t('tests.issues_title')}</h4>
					<span class="issues-count">{selectedCount}/{issues.length}</span>
				</div>
				<div class="issues-list">
					<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
					<div class="issue-row issue-select-all" onclick={toggleAll}>
						<input type="checkbox" checked={allSelected} />
						<span class="issue-label">{$t('tests.select_all')}</span>
					</div>
					{#each issues as issue (issue.id)}
						{@const fmt = formatIssueLabel(issue)}
						<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
						<div
							class="issue-row"
							class:issue-error={issue.severity === 'error'}
							class:issue-warning={issue.severity === 'warning'}
							onclick={() => toggleIssue(issue.id)}
						>
							<input type="checkbox" checked={!!selectedIssues[issue.id]} />
							<span class="issue-icon">{fmt.icon}</span>
							<span class="issue-label">{fmt.label}</span>
							{#if issue.command}
								<code class="issue-cmd">{issue.command}</code>
							{/if}
						</div>
					{/each}
				</div>
			</div>
		{/if}

		<div class="tests-actions">
			{#if hasIssues && selectedCount > 0}
				<button class="btn btn-primary" onclick={handleFixIssues}>
					<Wrench size={14} /> {$t('tests.fix_issues', { count: selectedCount })}
				</button>
			{/if}
			<button class="btn" disabled={loading} onclick={onRunTests}>
				{#if loading}<Loader2 size={14} class="spin" />{:else}<RotateCcw size={14} />{/if}
				{$t('tests.rerun')}
			</button>
			{#if !confirmed}
				<button class="btn btn-success" onclick={onConfirm}>
					<Check size={14} /> {$t('tests.confirm')}
				</button>
			{/if}
		</div>
	{:else}
		<div class="tests-empty">
			<p>{$t('tests.not_run_yet')}</p>
		</div>
	{/if}
</div>

<style>
	.tests-panel { padding: 0.5rem 0; }
	.tests-section { margin-bottom: 1.25rem; }

	.section-header { display: flex; align-items: center; gap: 0.5rem; }

	.section-title {
		font-size: 0.8125rem; font-weight: 600; color: var(--tx);
		margin-bottom: 0.5rem; text-transform: uppercase;
		letter-spacing: 0.03em; font-family: var(--font-ui);
	}

	.section-header .section-title { margin-bottom: 0; }

	.btn-icon {
		display: inline-flex; align-items: center; justify-content: center;
		background: none; border: 1px solid var(--bd); border-radius: var(--r2);
		color: var(--dm); cursor: pointer; padding: 0.25rem;
		transition: color 0.1s, border-color 0.1s;
	}
	.btn-icon:hover { color: var(--ac); border-color: var(--ac); }
	.btn-danger:hover { color: var(--rd); border-color: var(--rd); }

	.hint { font-size: 0.8125rem; color: var(--dm); padding: 0.375rem 0; }

	/* ── Inline editor ── */
	.cmd-editor { display: flex; flex-direction: column; gap: 0.375rem; margin-top: 0.5rem; }
	.cmd-edit-row { display: flex; gap: 0.375rem; align-items: center; }

	.cmd-input {
		font-size: 0.8125rem; font-family: var(--font-mono, monospace);
		background: var(--bg2); border: 1px solid var(--bd);
		border-radius: var(--r2); color: var(--tx); padding: 0.375rem 0.5rem;
	}
	.cmd-input:focus { outline: none; border-color: var(--ac); }
	.cmd-input-name { width: 10rem; flex-shrink: 0; }
	.cmd-input-cmd { flex: 1; min-width: 0; }

	.cmd-edit-actions { display: flex; align-items: center; gap: 0.5rem; margin-top: 0.25rem; }
	.cmd-edit-right { margin-left: auto; display: flex; gap: 0.375rem; }
	.btn-sm { font-size: 0.75rem; padding: 0.25rem 0.625rem; }

	/* ── Actions ── */
	.tests-actions { display: flex; gap: 0.5rem; flex-wrap: wrap; }

	.btn-success {
		background: var(--gn-bright) !important; color: #fff !important;
		border-color: var(--gn-bright) !important;
	}
	.btn-success:hover { filter: brightness(1.1); }

	.tests-empty { color: var(--dm); font-size: 0.875rem; }

	/* ── Issues list ── */
	.issues-section { margin-top: 0.5rem; }

	.issues-count {
		font-size: 0.6875rem; color: var(--dm); font-family: var(--font-ui);
	}

	.issues-list {
		display: flex; flex-direction: column; gap: 0.125rem;
		margin-top: 0.375rem;
	}

	.issue-row {
		display: flex; align-items: center; gap: 0.5rem;
		padding: 0.375rem 0.625rem;
		background: var(--bg2); border-radius: var(--r2);
		cursor: pointer; font-size: 0.8125rem; color: var(--tx);
		transition: background .1s;
	}

	.issue-row:hover { background: var(--sf2); }

	.issue-select-all {
		font-weight: 600; font-size: 0.75rem;
		text-transform: uppercase; letter-spacing: 0.03em;
		color: var(--dm); padding: 0.25rem 0.625rem;
	}

	.issue-icon { flex-shrink: 0; width: 1rem; text-align: center; }
	.issue-error .issue-icon { color: var(--rd); }
	.issue-warning .issue-icon { color: var(--yl); }

	.issue-label { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

	.issue-cmd {
		font-size: 0.6875rem; font-family: var(--font-ui);
		color: var(--dm); background: var(--bg);
		padding: 0.0625rem 0.375rem; border-radius: 0.1875rem;
		flex-shrink: 0; max-width: 16rem;
		overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
	}

	.issue-row input[type="checkbox"] {
		flex-shrink: 0; accent-color: var(--ac);
	}
</style>
