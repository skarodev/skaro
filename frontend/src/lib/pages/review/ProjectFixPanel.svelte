<script>
	import { t } from '$lib/i18n/index.js';
	import { api } from '$lib/api/client.js';
	import { status } from '$lib/stores/statusStore.js';
	import { addLog, addError } from '$lib/stores/logStore.js';
	import { invalidate } from '$lib/api/cache.js';
	import FixChat from '$lib/ui/FixChat.svelte';

	let { modelOverride = '' } = $props();

	let modelDisplay = $derived.by(() => {
		const s = $status;
		if (!s?.config) return '';
		const cfg = s.config;
		if (cfg.roles?.reviewer) return `${cfg.roles.reviewer.provider} / ${cfg.roles.reviewer.model}`;
		return `${cfg.llm_provider} / ${cfg.llm_model}`;
	});

	// API callbacks
	function loadConversationFn() {
		return api.loadProjectFixConversation();
	}

	function sendMessageFn(text, history, signal, scopePaths, override) {
		return api.sendProjectFix(text, history, [], scopePaths, signal, override);
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

	/**
	 * Create tasks from review issue proposals.
	 * All issues go into a dedicated 'review-fixes' milestone.
	 * @param {Array<{name: string, milestone: string, spec: string}>} tasks
	 * @returns {Promise<boolean>}
	 */
	async function handleCreateTasks(tasks) {
		try {
			const withMilestone = tasks.map(t => ({
				...t,
				milestone: t.milestone || 'review-fixes',
			}));
			const result = await api.batchCreateTasks(withMilestone);
			if (result.success) {
				const count = result.created?.length || 0;
				addLog($t('review.issues_tasks_created', { n: count }));
				invalidate('status');
				status.set(await api.getStatus());
				return true;
			} else {
				const msgs = result.errors?.join('; ') || 'Batch create failed';
				addError(msgs, 'reviewCreateTasks');
				return false;
			}
		} catch (e) {
			addError(e.message, 'reviewCreateTasks');
			return false;
		}
	}
</script>

<div class="project-fix">
	<FixChat
		{modelDisplay}
		{modelOverride}
		prefillEvent="skaro:prefill-project-fix"
		errorSource="projectFix"
		scopeEnabled={true}
		{loadConversationFn}
		{sendMessageFn}
		loadTreeFn={() => api.getFileTree()}
		{applyFileFn}
		{clearConversationFn}
		{onSendSuccess}
		onCreateTasks={handleCreateTasks}
	/>
</div>

<style>
	.project-fix { padding-bottom: 0; }
</style>
