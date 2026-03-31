<script>
	import { t } from '$lib/i18n/index.js';
	import { goto } from '$app/navigation';
	import { api } from '$lib/api/client.js';
	import {
		status, taskDetail,
		lastImplementResult, lastImplementStage, lastImplementTask,
	} from '$lib/stores/statusStore.js';
	import { addLog, addError } from '$lib/stores/logStore.js';
	import { invalidate } from '$lib/api/cache.js';
	import { parseClarifications } from '$lib/utils/markdown.js';
	import { Pencil, RefreshCw, Loader2 } from 'lucide-svelte';
	import MarkdownContent from '$lib/ui/MarkdownContent.svelte';
	import FileTabs from '$lib/ui/FileTabs.svelte';
	import DiffModal from '$lib/ui/DiffModal.svelte';
	import MdEditor from '$lib/ui/md-editor/MdEditor.svelte';
	import TaskHeader from './TaskHeader.svelte';
	import TaskActions from './TaskActions.svelte';
	import ClarifyForm from './ClarifyForm.svelte';
	import ImplementReview from './ImplementReview.svelte';
	import TestsPanel from './TestsPanel.svelte';
	import ConfirmModal from './ConfirmModal.svelte';
	import { openChatPanel } from '$lib/stores/chatPanelStore.js';

	let { taskName } = $props();

	let actionResult = $state('');
	let actionLoading = $state('');
	let activeFileTab = $state('');
	let clarifyAnswers = $state({});
	let draftSaving = $state(false);
	let draftSaved = $state(false);
	let implAppliedFiles = $state({});
	let implDiffModal = $state(null);
	let testsResults = $state(null);
	let tabInitialized = false;
	let lastQAKey = $state('');
	let deleteConfirmOpen = $state(false);
	let deleteLoading = $state(false);

	// ── Editor state ──
	let showEditor = $state(false);
	let editorContent = $state('');
	/** @type {{ type: 'file', filename: string } | { type: 'stage', stage: number } | null} */
	let editorTarget = $state(null);

	// Reset all local state when switching between tasks
	$effect(() => {
		// eslint-disable-next-line no-unused-expressions
		taskName; // track dependency
		actionResult = '';
		actionLoading = '';
		activeFileTab = '';
		clarifyAnswers = {};
		draftSaving = false;
		draftSaved = false;
		implAppliedFiles = {};
		implDiffModal = null;
		testsResults = null;
		tabInitialized = false;
		lastQAKey = '';
		showEditor = false;
		editorTarget = null;
	});

	let detail = $derived($taskDetail);
	let freshTask = $derived($status?.tasks?.find((f) => f.name === taskName) ?? null);
	let currentStage = $derived(freshTask?.current_stage ?? detail?.state?.current_stage ?? 0);
	let totalStages = $derived(freshTask?.total_stages ?? detail?.state?.total_stages ?? 0);
	let phases = $derived(freshTask?.phases ?? detail?.state?.phases ?? {});
	let currentPhase = $derived(freshTask?.current_phase ?? detail?.state?.current_phase ?? '');
	let testsConfirmed = $derived(phases.tests === 'complete');

	// Load tests.json from detail if available (survives page reload)
	$effect(() => {
		if (detail?.name === taskName && detail?.files?.['tests.json'] && !testsResults) {
			try {
				testsResults = JSON.parse(detail.files['tests.json']);
			} catch { /* ignore parse errors */ }
		}
	});

	// ── Clarify QA ──
	let clarifyContent = $derived(detail?.files?.['clarifications.md'] || '');
	let parsedQA = $derived(clarifyContent ? parseClarifications(clarifyContent) : []);
	let hasStructuredQA = $derived(parsedQA.length > 0);
	let hasUnanswered = $derived(hasStructuredQA && parsedQA.some((q) => !q.answer.trim()));

	$effect(() => {
		const key = parsedQA.map((q) => `${q.num}:${q.answer.length}`).join(',');
		if (hasStructuredQA && key !== lastQAKey) {
			lastQAKey = key;
			const fromFile = {};
			for (const q of parsedQA) fromFile[q.num] = q.answer || '';
			clarifyAnswers = fromFile;
			draftSaved = false;
		}
	});

	// ── File tabs ──
	/** Set of tab IDs that can be edited via MdEditor. */
	const EDITABLE_FILES = new Set(['spec.md', 'clarifications.md', 'plan.md', 'tasks.md']);

	let fileTabs = $derived.by(() => {
		if (!detail) return [];
		const tabs = [];
		if (detail.files['spec.md']) tabs.push({ id: 'spec.md', label: $t('tab.specification') });
		if (detail.files['clarifications.md'] && !hasUnanswered) tabs.push({ id: 'clarifications.md', label: $t('tab.clarifications') });
		if (detail.files['plan.md']) tabs.push({ id: 'plan.md', label: $t('tab.plan') });
		if (detail.files['tasks.md']) tabs.push({ id: 'tasks.md', label: $t('tab.tasks') });
		Object.keys(detail.stages || {}).map(Number).sort((a, b) => a - b)
			.forEach((s) => tabs.push({ id: `stage-${s}`, label: $t('tab.stage_notes', { n: s }) }));
		if (testsResults || phases.tests === 'in_progress' || phases.tests === 'complete') {
			tabs.push({ id: 'tests', label: $t('tab.tests') });
		}
		return tabs;
	});

	$effect(() => {
		if (fileTabs.length > 0 && !tabInitialized) {
			tabInitialized = true;
			activeFileTab = fileTabs[0].id;
		}
	});

	let activeContent = $derived.by(() => {
		if (!detail) return '';
		const id = activeFileTab || fileTabs[fileTabs.length - 1]?.id || '';
		if (id === 'tests') return '';
		if (id.startsWith('stage-')) return detail.stages?.[id.replace('stage-', '')] || '';
		return detail.files?.[id] || '';
	});

	/** Whether the current tab is editable. */
	let isTabEditable = $derived.by(() => {
		const id = activeFileTab;
		if (!id) return false;
		if (EDITABLE_FILES.has(id)) return true;
		if (id.startsWith('stage-')) return true;
		return false;
	});

	/** Show re-clarify button only on clarifications tab. */
	let showReClarify = $derived(
		activeFileTab === 'clarifications.md'
		&& phases.clarify === 'complete'
		&& !hasUnanswered
	);

	// ── Actions ──
	async function runClarify() {
		actionLoading = 'clarify'; actionResult = '';
		addLog($t('log.clarify_run', { name: taskName }));
		try {
			const result = await api.runClarify(taskName);
			if (result.success) { addLog($t('log.clarify_questions_saved')); lastQAKey = ''; await reloadAll(); }
			else handleActionError(result);
		} catch (e) { addError(e.message, 'runClarify'); actionResult = e.message; }
		actionLoading = '';
	}

	async function saveDraft() {
		if (!hasStructuredQA) return;
		draftSaving = true;
		try {
			const questions = parsedQA.map((q) => ({
				num: q.num,
				question: q.question,
				context: q.context || '',
				options: q.options || [],
				answer: clarifyAnswers[q.num] || '',
			}));
			await api.saveClarifyDraft(taskName, questions);
			draftSaved = true;
			addLog($t('log.clarify_draft_saved', { name: taskName }));
			setTimeout(() => { draftSaved = false; }, 2000);
		} catch (e) { addError(e.message, 'saveDraft'); }
		draftSaving = false;
	}

	async function submitAnswers() {
		const filled = Object.entries(clarifyAnswers).filter(([, v]) => v.trim());
		if (filled.length === 0) { addLog($t('clarify.no_answers')); return; }
		actionLoading = 'submit';
		try {
			await api.answerClarify(taskName, { questions: clarifyContent, answers: Object.fromEntries(filled) });
			addLog($t('log.clarify_done', { name: taskName }));
			clarifyAnswers = {}; lastQAKey = ''; await reloadAll();
		} catch (e) { addError(e.message, 'submitClarify'); actionResult = e.message; }
		actionLoading = '';
	}

	async function runPlan() {
		actionLoading = 'plan'; actionResult = '';
		addLog($t('log.plan_run', { name: taskName }));
		try {
			const result = await api.runPlan(taskName);
			if (result.success) { addLog($t('log.plan_done', { n: result.data?.stage_count || '?' })); await reloadAll(); }
			else handleActionError(result);
		} catch (e) { addError(e.message, 'runPlan'); actionResult = e.message; }
		actionLoading = '';
	}

	async function runImplement() {
		const stage = currentStage + 1;
		actionLoading = 'implement'; actionResult = '';
		addLog($t('log.impl_run', { name: taskName, n: stage }));
		try {
			const result = await api.runImplement(taskName, { stage });
			if (result.success) {
				implAppliedFiles = {};
				lastImplementResult.set(result);
				lastImplementStage.set(stage);
				lastImplementTask.set(taskName);
				addLog($t('log.impl_done', { n: stage, files: Object.keys(result.data?.files || {}).length }));
				await reloadAll();
				activeFileTab = `stage-${stage}`;
			} else handleActionError(result);
		} catch (e) { addError(e.message, 'runImplement'); actionResult = e.message; }
		actionLoading = '';
	}

	async function runTests() {
		actionLoading = 'tests'; actionResult = '';
		addLog($t('log.tests_run', { name: taskName }));
		try {
			const result = await api.runTests(taskName);
			if (result.success) {
				testsResults = result.data;
				activeFileTab = 'tests';
				addLog($t('log.tests_done', { name: taskName }));
				try { await reloadAll(); } catch { /* status refresh is non-critical */ }
			} else handleActionError(result);
		} catch (e) { addError(e.message, 'runTests'); actionResult = e.message; }
		actionLoading = '';
	}

	async function confirmTests() {
		try {
			const result = await api.confirmTests(taskName);
			if (result.success) {
				addLog($t('log.tests_confirmed', { name: taskName }));
				try { await reloadAll(); } catch { /* status refresh is non-critical */ }
			} else handleActionError(result);
		} catch (e) { addError(e.message, 'confirmTests'); }
	}

	async function fixFromIssues(issueIds) {
		openChatPanel();
		// Small delay to ensure FixChat is mounted in RightPanel
		await new Promise((r) => setTimeout(r, 150));
		window.dispatchEvent(new CustomEvent('skaro:fix-from-issues', {
			detail: { taskName, issueIds },
		}));
	}

	// ── Implement file apply ──
	function openImplDiff(filepath, fileData) {
		implDiffModal = { filepath, oldContent: fileData.old, newContent: fileData.new, isNew: fileData.is_new, applied: !!implAppliedFiles[filepath] };
	}

	/** Remove a file from the implement result store; clear store if empty. */
	function dismissImplFile(filepath) {
		lastImplementResult.update((r) => {
			if (!r?.data?.files) return r;
			const { [filepath]: _, ...rest } = r.data.files;
			if (Object.keys(rest).length === 0) return null;
			return { ...r, data: { ...r.data, files: rest } };
		});
	}

	/** Schedule file removal 2 s after successful apply. */
	function scheduleImplDismiss(filepath) {
		setTimeout(() => dismissImplFile(filepath), 2000);
	}

	async function applyImplFile(filepath, content) {
		try {
			const result = await api.applyImplementFile(taskName, filepath, content);
			if (result.success) {
				implAppliedFiles[filepath] = true;
				implAppliedFiles = { ...implAppliedFiles };
				addLog($t('log.fix_applied', { file: filepath }));
				implDiffModal = null;
				scheduleImplDismiss(filepath);
			}
			else addError(result.message, 'applyImplFile');
		} catch (e) { addError(e.message, 'applyImplFile'); }
	}

	async function applyAllImplFiles(filesMap) {
		for (const [fpath, fdata] of Object.entries(filesMap)) {
			if (!implAppliedFiles[fpath]) await applyImplFile(fpath, fdata.new);
		}
	}

	// ── MD Editor ──
	function openEditor() {
		const id = activeFileTab;
		if (!id) return;
		editorContent = activeContent;
		if (EDITABLE_FILES.has(id)) {
			editorTarget = { type: 'file', filename: id };
		} else if (id.startsWith('stage-')) {
			const stageNum = parseInt(id.replace('stage-', ''), 10);
			editorTarget = { type: 'stage', stage: stageNum };
		} else {
			return;
		}
		showEditor = true;
	}

	async function saveEditorContent(text) {
		if (!editorTarget) return;
		try {
			if (editorTarget.type === 'file') {
				await api.saveTaskFile(taskName, editorTarget.filename, text);
				addLog($t('log.task_file_saved', { file: editorTarget.filename, name: taskName }));
			} else if (editorTarget.type === 'stage') {
				await api.saveStageNotes(taskName, editorTarget.stage, text);
				addLog($t('log.task_file_saved', { file: `stage-${editorTarget.stage}`, name: taskName }));
			}
			showEditor = false;
			editorTarget = null;
			await reloadAll();
		} catch (e) {
			addError(e.message, 'saveTaskFile');
			throw e;
		}
	}

	// ── Helpers ──
	function handleActionError(result) {
		addError(result.message || $t('error.unknown'), result.error_type || '');
		actionResult = result.message || $t('error.unknown');
	}

	async function reloadAll() {
		invalidate('status', `task:${taskName}`);
		status.set(await api.getStatus());
		if (taskName) {
			taskDetail.set(await api.getTask(taskName));
		}
	}

	function goBack() {
		taskDetail.set(null);
		goto('/tasks');
	}

	// ── Delete ──
	async function handleDeleteTask() {
		deleteLoading = true;
		try {
			await api.deleteTask(taskName);
			addLog($t('log.task_deleted', { name: taskName }));

			// Close modal and navigate immediately — don't block on status refresh
			deleteConfirmOpen = false;
			deleteLoading = false;
			taskDetail.set(null);
			goto('/tasks');

			// Refresh status in background (non-blocking)
			invalidate('status');
			api.getStatus().then((s) => status.set(s)).catch(() => {});
		} catch (e) {
			addError(e.message, 'deleteTask');
			deleteLoading = false;
			deleteConfirmOpen = false;
		}
	}
</script>

<div class="detail page-with-tabs">
	<TaskHeader {taskName} {phases} {currentPhase} {currentStage} {totalStages} onBack={goBack} onDelete={() => deleteConfirmOpen = true} />

	{#if deleteConfirmOpen}
		<ConfirmModal
			title={$t('task.delete_title')}
			message={$t('task.delete_confirm', { name: taskName })}
			confirmLabel={$t('task.delete_btn')}
			cancelLabel={$t('task.delete_cancel')}
			loading={deleteLoading}
			onConfirm={handleDeleteTask}
			onClose={() => deleteConfirmOpen = false}
		/>
	{/if}

	<TaskActions
		{phases} {currentStage} {totalStages} {actionLoading} {hasUnanswered}
		onClarify={runClarify} onPlan={runPlan} onImplement={runImplement} onTests={runTests}
	/>

	{#if actionResult && !actionLoading}
		<div class="alert alert-warn">{actionResult}</div>
	{/if}

	{#if hasUnanswered}
		<ClarifyForm
			{parsedQA} bind:clarifyAnswers {actionLoading} {draftSaving} {draftSaved}
			onSubmit={submitAnswers} onSaveDraft={saveDraft} onReClarify={runClarify}
		/>
	{/if}

	{#if $lastImplementResult && $lastImplementTask === taskName}
		<ImplementReview
			stage={$lastImplementStage}
			filesMap={$lastImplementResult.data?.files || {}}
			appliedFiles={implAppliedFiles}
			onOpenDiff={openImplDiff}
			onApplyAll={() => applyAllImplFiles($lastImplementResult.data?.files || {})}
		/>
	{/if}

	{#if implDiffModal}
		<DiffModal
			filepath={implDiffModal.filepath}
			oldContent={implDiffModal.oldContent}
			newContent={implDiffModal.newContent}
			isNew={implDiffModal.isNew}
			applied={implDiffModal.applied}
			onApply={() => applyImplFile(implDiffModal.filepath, implDiffModal.newContent)}
			onClose={() => implDiffModal = null}
		/>
	{/if}

	<FileTabs
		tabs={fileTabs}
		activeTab={activeFileTab}
		content={activeContent}
		onSelectTab={(id) => activeFileTab = id}
	>
		{#snippet contentActionsSlot()}
			{#if isTabEditable || showReClarify}
				<div class="content-actions">
					{#if isTabEditable}
						<button class="btn btn-sm" onclick={openEditor}>
							<Pencil size={14} /> {$t('editor.edit')}
						</button>
					{/if}
					{#if showReClarify}
						<button class="btn btn-sm" disabled={!!actionLoading} onclick={runClarify}>
							{#if actionLoading === 'clarify'}<Loader2 size={14} class="spin" />{:else}<RefreshCw size={14} />{/if}
							{$t('action.re_clarify')}
						</button>
					{/if}
				</div>
			{/if}
		{/snippet}
		{#snippet testsSlot()}
			<TestsPanel
				{taskName}
				results={testsResults}
				loading={actionLoading === 'tests'}
				confirmed={testsConfirmed}
				onRunTests={runTests}
				onConfirm={confirmTests}
				onFixFromIssues={fixFromIssues}
			/>
		{/snippet}
	</FileTabs>
</div>

{#if showEditor}
	<MdEditor
		content={editorContent}
		onSave={saveEditorContent}
		onClose={() => { showEditor = false; editorTarget = null; }}
	/>
{/if}

<style>
	.detail { padding-bottom: 0; }

	.content-actions {
		display: flex;
		gap: 0.5rem;
		justify-content: flex-end;
		margin-bottom: 0.75rem;
	}
</style>
