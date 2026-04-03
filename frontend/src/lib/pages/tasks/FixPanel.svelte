<script>
	import { t } from '$lib/i18n/index.js';
	import { page } from '$app/stores';
	import { api } from '$lib/api/client.js';
	import { status } from '$lib/stores/statusStore.js';
	import { addLog } from '$lib/stores/logStore.js';
	import FixChat from '$lib/ui/FixChat.svelte';

	let { task = '', modelOverride = '' } = $props();

	const TAB_ROLES = {
		constitution: null,
		architecture: 'architect',
		adr: 'architect',
		devplan: 'architect',
		tasks: 'coder',
		settings: null,
	};

	let currentTab = $derived.by(() => {
		const parts = $page.url.pathname.split('/').filter(Boolean);
		return parts[0] || 'dashboard';
	});

	function getRoleInfo(s, tab) {
		if (!s?.config) return '—';
		const roleName = TAB_ROLES[tab];
		const cfg = s.config;
		if (roleName && cfg.roles?.[roleName]) {
			const r = cfg.roles[roleName];
			return `${r.provider} / ${r.model}`;
		}
		return `${cfg.llm_provider} / ${cfg.llm_model}`;
	}

	let modelDisplay = $derived(getRoleInfo($status, currentTab));

	// API callbacks bound to current task
	function loadConversationFn() {
		return api.loadFixConversation(task);
	}

	function sendMessageFn(text, history, signal, scopePaths, override) {
		return api.sendFix(task, text, history, scopePaths, signal, override);
	}

	function applyFileFn(filepath, content) {
		return api.applyFixFile(task, filepath, content);
	}

	function clearConversationFn() {
		return api.clearFixConversation(task);
	}

	function fixFromIssuesFn(issueIds, conversation, signal, scopePaths, override) {
		return api.fixFromIssues(task, issueIds, conversation, scopePaths, signal, override);
	}

	function onSendSuccess() {
		addLog($t('log.fix_response', { name: task }));
	}
</script>

<FixChat
	{modelDisplay}
	{modelOverride}
	prefillEvent="skaro:prefill-fix"
	fixFromIssuesEvent="skaro:fix-from-issues"
	errorSource="fix"
	scopeEnabled={true}
	{loadConversationFn}
	{sendMessageFn}
	{fixFromIssuesFn}
	loadTreeFn={() => api.getFileTree()}
	{applyFileFn}
	{clearConversationFn}
	{onSendSuccess}
/>
