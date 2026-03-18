<script>
	import { t } from '$lib/i18n/index.js';
	import { onMount, onDestroy } from 'svelte';
	import { addLog, addError } from '$lib/stores/logStore.js';
	import { Loader2 } from 'lucide-svelte';
	import ChatMessage from '$lib/ui/ChatMessage.svelte';
	import ComposeBox from '$lib/ui/ComposeBox.svelte';
	import DiffModal from '$lib/ui/DiffModal.svelte';
	import ScopeModal from '$lib/ui/ScopeModal.svelte';

	/**
	 * @type {{
	 *   modelDisplay?: string,
	 *   prefillEvent?: string,
	 *   placeholder?: string,
	 *   scopeEnabled?: boolean,
	 *   loadConversationFn: () => Promise<{conversation: any[], context_tokens: number}>,
	 *   sendMessageFn: (text: string, history: any[], signal: AbortSignal, scopePaths: string[]) => Promise<any>,
	 *   loadTreeFn?: () => Promise<{tree: any[]}>,
	 *   applyFileFn: (filepath: string, content: string) => Promise<any>,
	 *   clearConversationFn: () => Promise<void>,
	 *   onSendSuccess?: () => void,
	 *   errorSource?: string,
	 *   autoLoad?: boolean,
	 * }}
	 */
	let {
		modelDisplay = '',
		prefillEvent = '',
		fixFromIssuesEvent = '',
		placeholder = '',
		scopeEnabled = false,
		loadConversationFn,
		sendMessageFn,
		fixFromIssuesFn = null,
		loadTreeFn = null,
		applyFileFn,
		clearConversationFn,
		onSendSuccess = () => {},
		errorSource = 'fix',
		autoLoad = true,
	} = $props();

	let message = $state('');
	let loading = $state(false);
	let conversationLoading = $state(false);
	let conversation = $state([]);
	let contextTokens = $state(0);
	let initialLoaded = $state(false);
	let appliedFiles = $state({});
	let diffModal = $state(null);

	// Scope state
	let scopePaths = $state([]);
	let fileTree = $state([]);
	let showScopeModal = $state(false);
	let treeLoaded = $state(false);

	/** @type {AbortController | null} */
	let abortController = $state(null);

	$effect(() => {
		if (autoLoad && !initialLoaded) {
			initialLoaded = true;
			loadConversation();
		}
	});

	// Auto-scroll when conversation changes
	$effect(() => {
		void conversation.length;
		void loading;
		scrollToEnd('smooth');
	});

	function scrollToEnd(behavior = 'instant') {
		requestAnimationFrame(() => {
			const main = document.querySelector('.main');
			if (main) main.scrollTo({ top: main.scrollHeight, behavior });
		});
	}

	onMount(() => {
		requestAnimationFrame(() => {
			requestAnimationFrame(() => scrollToEnd());
		});
	});

	// Prefill from external events (e.g. TestsPanel "Send to LLM")
	function handlePrefill(e) {
		const text = e.detail?.message;
		if (text) {
			message = text;
			scrollToEnd('smooth');
		}
	}

	// Fix from issues — triggered by TestsPanel "Fix Issues" button
	async function handleFixFromIssues(e) {
		const { issueIds } = e.detail || {};
		if (!issueIds?.length || !fixFromIssuesFn || loading) return;

		loading = true;
		const controller = new AbortController();
		abortController = controller;

		// Show a synthetic user message summarizing what's happening
		const issueLabel = issueIds.length === 1 ? '1 issue' : `${issueIds.length} issues`;
		conversation = [...conversation, {
			role: 'user',
			content: `Fix ${issueLabel} from test results`,
		}];

		try {
			const history = conversation.slice(0, -1).map((turn) => ({
				role: turn.role, content: turn.content,
			}));
			const result = await fixFromIssuesFn(issueIds, history, controller.signal, scopePaths);
			if (result.success) {
				conversation = [...conversation, {
					role: 'assistant', content: result.message,
					files: result.files || {}, turnIndex: conversation.length,
				}];
				onSendSuccess();
			} else {
				addError(result.message || 'Request failed', errorSource);
			}
		} catch (e) {
			if (e.name === 'AbortError') {
				conversation = conversation.slice(0, -1);
				addLog('Cancelled');
			} else {
				addError(e.message, errorSource);
			}
		}
		abortController = null;
		loading = false;
	}

	onMount(() => {
		if (prefillEvent) window.addEventListener(prefillEvent, handlePrefill);
		if (fixFromIssuesEvent) window.addEventListener(fixFromIssuesEvent, handleFixFromIssues);
	});
	onDestroy(() => {
		if (prefillEvent) window.removeEventListener(prefillEvent, handlePrefill);
		if (fixFromIssuesEvent) window.removeEventListener(fixFromIssuesEvent, handleFixFromIssues);
	});

	async function loadConversation() {
		conversationLoading = true;
		try {
			const data = await loadConversationFn();
			if (data.conversation?.length > 0) conversation = data.conversation;
			contextTokens = data.context_tokens || 0;
		} catch {
			// Empty conversation is fine
		}
		conversationLoading = false;
	}

	let conversationTokens = $derived(
		Math.round(conversation.reduce((sum, t) => sum + (t.content?.length || 0), 0) / 4)
	);
	let messageTokens = $derived(Math.round(message.length / 4));

	// Estimate tokens from scope-selected files based on file sizes from tree
	let scopeTokens = $derived.by(() => {
		if (scopePaths.length === 0 || fileTree.length === 0) return 0;
		const selectedSet = new Set(scopePaths);
		let bytes = 0;
		function walk(nodes) {
			for (const n of nodes) {
				if (n.type === 'file' && selectedSet.has(n.path)) bytes += n.size || 0;
				if (n.children) walk(n.children);
			}
		}
		walk(fileTree);
		return Math.round(bytes / 4);
	});

	let totalTokens = $derived(contextTokens + conversationTokens + messageTokens + scopeTokens);
	let tokenDisplay = $derived.by(() => {
		const k = totalTokens / 1000;
		return k >= 1 ? `~${k.toFixed(0)}k ${$t('fix.tokens')}` : `~${totalTokens} ${$t('fix.tokens')}`;
	});

	async function openScopeModal() {
		if (!treeLoaded && loadTreeFn) {
			try {
				const data = await loadTreeFn();
				fileTree = data.tree || [];
				treeLoaded = true;
			} catch (e) {
				addError(e.message, errorSource);
				return;
			}
		}
		showScopeModal = true;
	}

	function handleScopeConfirm(paths) {
		scopePaths = paths;
		showScopeModal = false;
	}

	async function sendMessage() {
		const text = message.trim();
		if (!text || loading) return;
		loading = true;
		message = '';
		conversation = [...conversation, { role: 'user', content: text }];

		const controller = new AbortController();
		abortController = controller;

		try {
			const history = conversation.slice(0, -1).map((turn) => ({ role: turn.role, content: turn.content }));
			const result = await sendMessageFn(text, history, controller.signal, scopePaths);
			if (result.success) {
				conversation = [...conversation, {
					role: 'assistant', content: result.message,
					files: result.files || {}, turnIndex: conversation.length,
				}];
				onSendSuccess();
			} else {
				addError(result.message || 'Request failed', errorSource);
			}
		} catch (e) {
			if (e.name === 'AbortError') {
				// Remove the user message that was added optimistically
				conversation = conversation.slice(0, -1);
				addLog($t('fix.cancelled'));
			} else {
				addError(e.message, errorSource);
			}
		}
		abortController = null;
		loading = false;
	}

	function cancelRequest() {
		if (abortController) abortController.abort();
	}

	async function applyFile(turnIndex, filepath, content) {
		try {
			const result = await applyFileFn(filepath, content);
			if (result.success) {
				if (!appliedFiles[turnIndex]) appliedFiles[turnIndex] = {};
				appliedFiles[turnIndex][filepath] = true;
				appliedFiles = { ...appliedFiles };
				addLog($t('log.fix_applied', { file: filepath }));
				diffModal = null;
			} else {
				addError(result.message, errorSource);
			}
		} catch (e) {
			addError(e.message, errorSource);
		}
	}

	function openDiff(turnIndex, filepath, fileData) {
		diffModal = {
			filepath, oldContent: fileData.old, newContent: fileData.new,
			isNew: fileData.is_new, applied: !!(appliedFiles[turnIndex]?.[filepath]),
			turnIndex,
		};
	}

	async function clearConversation() {
		conversation = [];
		appliedFiles = {};
		message = '';
		try { await clearConversationFn(); } catch {}
	}
</script>

{#if conversationLoading}
	<div class="fix-conversation">
		<!-- Skeleton: user message -->
		<div class="turn turn-user skel-turn">
			<div class="skel-label skel-pulse" style="width: 3rem"></div>
			<div class="skel-body-user">
				<div class="skel-line skel-pulse" style="width: 90%"></div>
				<div class="skel-line skel-pulse" style="width: 70%"></div>
			</div>
		</div>
		<!-- Skeleton: assistant message -->
		<div class="turn turn-assistant skel-turn">
			<div class="skel-label skel-pulse" style="width: 8rem"></div>
			<div class="skel-body-assistant">
				<div class="skel-line skel-pulse" style="width: 100%"></div>
				<div class="skel-line skel-pulse" style="width: 95%"></div>
				<div class="skel-line skel-pulse" style="width: 60%"></div>
				<div class="skel-line skel-pulse" style="width: 85%"></div>
				<div class="skel-line skel-pulse" style="width: 40%"></div>
			</div>
			<div class="skel-file skel-pulse"></div>
		</div>
	</div>
{:else if conversation.length > 0}
	<div class="fix-conversation">
		{#each conversation as turn, i}
			<ChatMessage {turn} index={i} {appliedFiles} {modelDisplay} onOpenDiff={openDiff} />
		{/each}
		{#if loading}
			<div class="turn turn-assistant">
				<div class="turn-label">{modelDisplay || $t('fix.llm')}</div>
				<div class="thinking"><Loader2 size={14} class="spin" /> {$t('fix.thinking')}</div>
			</div>
		{/if}
	</div>
{/if}

{#if conversation.length > 0}
	<div class="clear-row">
		<button class="btn btn-sm" onclick={clearConversation}>{$t('fix.clear')}</button>
	</div>
{/if}

{#if showScopeModal}
	<ScopeModal
		tree={fileTree}
		selected={scopePaths}
		onConfirm={handleScopeConfirm}
		onClose={() => showScopeModal = false}
	/>
{/if}

{#if diffModal}
	<DiffModal
		filepath={diffModal.filepath}
		oldContent={diffModal.oldContent}
		newContent={diffModal.newContent}
		isNew={diffModal.isNew}
		applied={diffModal.applied}
		onApply={() => applyFile(diffModal.turnIndex, diffModal.filepath, diffModal.newContent)}
		onClose={() => diffModal = null}
	/>
{/if}

<div class="fix-bar">
	<ComposeBox
		bind:message
		{loading}
		{tokenDisplay}
		{modelDisplay}
		{placeholder}
		showScope={scopeEnabled}
		scopeCount={scopePaths.length}
		onSend={sendMessage}
		onCancel={cancelRequest}
		onScopeClick={openScopeModal}
	/>
</div>

<style>
	.fix-conversation { padding-bottom: 1rem; }

	.fix-bar {
		position: sticky; bottom: 0;
		background: var(--bg);
		padding: 0; z-index: 10;
	}

	.thinking {
		display: flex; align-items: center; gap: 0.375rem;
		color: var(--dm); font-size: 0.8125rem;
	}

	.turn-label {
		font-size: 0.6875rem; font-weight: 700;
		text-transform: uppercase; letter-spacing: .05em;
		margin-bottom: 0.25rem; color: var(--or);
	}

	.clear-row {
		display: flex; justify-content: center;
		padding: 0.5rem 0;
	}

	.btn-sm { font-size: 0.75rem; padding: 0.25rem 0.625rem; }

	/* ── Skeleton ── */
	.skel-turn { pointer-events: none; }
	.skel-pulse {
		background: var(--bg2); border-radius: var(--r);
		animation: skel-shimmer 1.5s ease-in-out infinite;
	}
	@keyframes skel-shimmer { 0%, 100% { opacity: .4; } 50% { opacity: .15; } }
	.skel-label { height: .75rem; margin-bottom: .5rem; border-radius: .25rem; }
	.skel-line { height: .85rem; margin-bottom: .5rem; border-radius: .25rem; }

	.skel-body-user {
		max-width: 80%; margin-left: auto;
		background: var(--bg2); border-radius: var(--r); padding: 1.2rem;
	}
	.skel-body-user .skel-line { background: var(--bg3); }
	.skel-body-assistant { padding: .25rem 0; }

	.skel-file {
		height: 2rem; width: 14rem;
		margin-top: .5rem; border-radius: var(--r);
	}

	.turn-user .skel-label { margin-left: auto; }
</style>
