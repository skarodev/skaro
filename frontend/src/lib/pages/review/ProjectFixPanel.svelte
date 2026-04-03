<script>
	import { t } from '$lib/i18n/index.js';
	import { api } from '$lib/api/client.js';
	import { status } from '$lib/stores/statusStore.js';
	import { addLog } from '$lib/stores/logStore.js';
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
	/>
</div>

<style>
	.project-fix { padding-bottom: 0; }
</style>
