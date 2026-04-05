<script>
	import { t } from '$lib/i18n/index.js';
	import { api } from '$lib/api/client.js';
	import { status } from '$lib/stores/statusStore.js';
	import { addLog, addError } from '$lib/stores/logStore.js';
	import { invalidate } from '$lib/api/cache.js';
	import FixChat from '$lib/ui/FixChat.svelte';

	/**
	 * @type {{
	 *   contextType: string,
	 *   contextId?: string,
	 *   roleName?: string,
	 *   errorSource?: string,
	 *   placeholderKey?: string,
	 *   onFileApplied?: () => void,
	 * }}
	 */
	let {
		contextType = '',
		contextId = '',
		roleName = 'architect',
		errorSource = 'chat',
		placeholderKey = 'chat_panel.placeholder_default',
		onFileApplied = () => {},
		modelOverride = '',
	} = $props();

	let modelDisplay = $derived.by(() => {
		const s = $status;
		if (!s?.config) return '';
		const cfg = s.config;
		if (roleName && cfg.roles?.[roleName]) {
			const r = cfg.roles[roleName];
			return `${r.provider} / ${r.model}`;
		}
		return `${cfg.llm_provider} / ${cfg.llm_model}`;
	});

	let chatPlaceholder = $derived($t(placeholderKey));

	async function loadConversationFn() {
		const params = contextId
			? `?context_id=${encodeURIComponent(contextId)}`
			: '';
		return api.loadChatConversation(contextType, params);
	}

	function sendMessageFn(text, history, signal, scopePaths, override) {
		return api.sendChat(contextType, text, history, contextId, scopePaths, signal, override);
	}

	async function applyFileFn(filepath, content) {
		try {
			const result = await api.applyChatFile(contextType, filepath, content);
			if (result.success) {
				// Invalidate relevant caches based on context.
				if (contextType === 'constitution') {
					invalidate('constitution', 'status');
					status.set(await api.getStatus());
				} else if (contextType === 'devplan') {
					invalidate('devplan', 'status');
					status.set(await api.getStatus());
				}
				onFileApplied();
			}
			return result;
		} catch (e) {
			addError(e.message, errorSource);
			return { success: false, message: e.message };
		}
	}

	function clearConversationFn() {
		const params = contextId
			? `?context_id=${encodeURIComponent(contextId)}`
			: '';
		return api.clearChatConversation(contextType, params);
	}

	function onSendSuccess() {
		addLog($t('chat_panel.response_received'));
	}

	/**
	 * Batch create tasks from a chat proposal.
	 * Only active when contextType is 'tasks'.
	 * @param {Array<{name: string, milestone: string, spec: string}>} tasks
	 * @returns {Promise<boolean>}
	 */
	async function handleCreateTasks(tasks) {
		try {
			const result = await api.batchCreateTasks(tasks);
			if (result.success) {
				const count = result.created?.length || 0;
				addLog($t('task_proposal.batch_created', { n: count }));
				invalidate('status');
				status.set(await api.getStatus());
				return true;
			} else {
				const msgs = result.errors?.join('; ') || 'Batch create failed';
				addError(msgs, errorSource);
				return false;
			}
		} catch (e) {
			addError(e.message, errorSource);
			return false;
		}
	}

	let createTasksFn = $derived(contextType === 'tasks' ? handleCreateTasks : null);
</script>

<FixChat
	{modelDisplay}
	{modelOverride}
	errorSource={errorSource}
	autoLoad={true}
	placeholder={chatPlaceholder}
	scopeEnabled={true}
	loadConversationFn={loadConversationFn}
	sendMessageFn={sendMessageFn}
	loadTreeFn={() => api.getFileTree()}
	applyFileFn={applyFileFn}
	clearConversationFn={clearConversationFn}
	onSendSuccess={onSendSuccess}
	onCreateTasks={createTasksFn}
/>
