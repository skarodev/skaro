<script>
	import { t } from '$lib/i18n/index.js';
	import { api } from '$lib/api/client.js';
	import { status } from '$lib/stores/statusStore.js';
	import { addLog, addError } from '$lib/stores/logStore.js';
	import { invalidate } from '$lib/api/cache.js';
	import FixChat from '$lib/ui/FixChat.svelte';
	import FeatureProposal from '$lib/pages/features/FeatureProposal.svelte';

	let { slug = '', isDraft: isDraftProp = null, onConfirmed = () => {}, modelOverride = '' } = $props();

	let proposal = $state(null);
	let confirming = $state(false);
	let autoDetectedDraft = $state(false);

	// isDraft: use prop if explicitly provided, otherwise auto-detect
	let isDraft = $derived(isDraftProp !== null ? isDraftProp : autoDetectedDraft);

	let modelDisplay = $derived.by(() => {
		const s = $status;
		if (!s?.config) return '';
		const cfg = s.config;
		if (cfg.roles?.architect) return `${cfg.roles.architect.provider} / ${cfg.roles.architect.model}`;
		return `${cfg.llm_provider} / ${cfg.llm_model}`;
	});

	function loadConversationFn() {
		return api.getFeatureConversation(slug);
	}

	function sendMessageFn(text, history, signal, scopePaths, override) {
		return api.sendFeatureChat(slug, text, history, scopePaths, signal, override);
	}

	function applyFileFn() {
		// Feature chat does not produce file blocks — proposals handled separately
		return Promise.resolve({ success: true });
	}

	function clearConversationFn() {
		return api.clearFeatureConversation(slug);
	}

	function onSendSuccess() {
		addLog($t('feature.chat_response'));
		// After each LLM response, check if proposal JSON is in the latest assistant message
		// We do this by re-reading conversation from the chat component's internal state
		// The proposal check happens via a reactive scan of conversation
	}

	/**
	 * Try to extract a JSON proposal from the last assistant message.
	 * The LLM wraps it in ```json ... ``` fences.
	 */
	function extractProposal(conversation) {
		if (!conversation?.length) return null;
		// Find last assistant message
		for (let i = conversation.length - 1; i >= 0; i--) {
			const turn = conversation[i];
			if (turn.role !== 'assistant') continue;
			const content = turn.content || '';
			const match = content.match(/```json\s*\n([\s\S]*?)\n\s*```/);
			if (!match) continue;
			try {
				const parsed = JSON.parse(match[1]);
				if (parsed.proposal === true && parsed.title) return parsed;
			} catch { /* not valid JSON */ }
			break; // Only check the last assistant message
		}
		return null;
	}

	// Watch for proposals — triggered by FixChat's conversation updates via custom event
	function handleConversationUpdate(e) {
		const conv = e?.detail?.conversation;
		if (conv) {
			proposal = extractProposal(conv);
		}
	}

	// Also check on load
	async function checkExistingProposal() {
		try {
			const data = await api.getFeatureConversation(slug);
			proposal = extractProposal(data.conversation);
		} catch { /* ignore */ }
	}

	import { onMount } from 'svelte';
	onMount(async () => {
		if (isDraftProp === null) {
			// Auto-detect draft status from API
			try {
				const data = await api.getFeature(slug);
				autoDetectedDraft = data?.status === 'draft';
				if (autoDetectedDraft) checkExistingProposal();
			} catch { /* ignore */ }
		} else if (isDraftProp) {
			checkExistingProposal();
		}
	});

	async function confirmProposal(editedProposal) {
		confirming = true;
		try {
			const result = await api.confirmFeature(slug, editedProposal);
			if (result.success) {
				addLog($t('feature.confirmed', { n: result.tasks_created?.length || 0 }));
				proposal = null;
				invalidate('features', 'status');
				status.set(await api.getStatus());
				onConfirmed();
			} else { addError(result.message, 'featureConfirm'); }
		} catch (e) { addError(e.message, 'featureConfirm'); }
		confirming = false;
	}

	function discardProposal() {
		proposal = null;
	}
</script>

<FixChat
	{modelDisplay}
	{modelOverride}
	placeholder={isDraft ? $t('feature.chat_placeholder_draft') : $t('feature.chat_placeholder')}
	errorSource="feature"
	scopeEnabled={true}
	{loadConversationFn}
	{sendMessageFn}
	loadTreeFn={() => api.getFileTree()}
	{applyFileFn}
	{clearConversationFn}
	{onSendSuccess}
	autoLoad={true}
/>

{#if isDraft && proposal}
	<FeatureProposal
		{proposal}
		{confirming}
		onConfirm={confirmProposal}
		onDiscard={discardProposal}
	/>
{/if}

<style>
	/* FixChat fills the tab content naturally */
</style>
