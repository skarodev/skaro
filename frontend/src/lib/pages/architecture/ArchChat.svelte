<script>
	import { t } from '$lib/i18n/index.js';
	import { api } from '$lib/api/client.js';
	import { status } from '$lib/stores/statusStore.js';
	import { addLog, addError } from '$lib/stores/logStore.js';
	import { invalidate } from '$lib/api/cache.js';
	import FixChat from '$lib/ui/FixChat.svelte';

	let chatHasMessages = $state(false);

	let modelDisplay = $derived.by(() => {
		const s = $status;
		if (!s?.config) return '';
		const cfg = s.config;
		if (cfg.roles?.architect) {
			const r = cfg.roles.architect;
			return `${r.provider} / ${r.model}`;
		}
		return `${cfg.llm_provider} / ${cfg.llm_model}`;
	});

	let chatPlaceholder = $derived(
		chatHasMessages ? $t('arch.chat_placeholder_reply') : $t('arch.chat_placeholder_start')
	);

	async function loadChatConversationFn() {
		const result = await api.loadArchChatConversation();
		if (result.conversation?.length > 0) {
			chatHasMessages = true;
		}
		return result;
	}

	function sendChatMessageFn(text, history, signal) {
		return api.sendArchChat(text, history, signal);
	}

	async function applyChatFileFn(filepath, content) {
		try {
			const result = await api.saveArchitecture(content);
			if (result.success) {
				addLog($t('log.arch_chat_accepted'));
				invalidate('architecture', 'status');
				status.set(await api.getStatus());
				chatHasMessages = false;
				// Notify ArchitecturePage to reload its data
				window.dispatchEvent(new CustomEvent('skaro:architecture-updated'));
			}
			return result;
		} catch (e) {
			addError(e.message, 'archChat');
			return { success: false, message: e.message };
		}
	}

	async function clearChatConversationFn() {
		chatHasMessages = false;
		return api.clearArchChatConversation();
	}

	function onChatSendSuccess() {
		chatHasMessages = true;
		addLog($t('log.arch_chat_response'));
	}
</script>

<FixChat
	{modelDisplay}
	errorSource="archChat"
	autoLoad={true}
	placeholder={chatPlaceholder}
	loadConversationFn={loadChatConversationFn}
	sendMessageFn={sendChatMessageFn}
	applyFileFn={applyChatFileFn}
	clearConversationFn={clearChatConversationFn}
	onSendSuccess={onChatSendSuccess}
/>
