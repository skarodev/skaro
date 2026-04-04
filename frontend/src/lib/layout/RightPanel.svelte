<script>
	import { t } from '$lib/i18n/index.js';
	import { page } from '$app/stores';
	import { status } from '$lib/stores/statusStore.js';
	import {
		chatPanelOpen, chatPanelWidth, closeChatPanel,
		chatContextMeta,
		MIN_WIDTH, MAX_WIDTH_VW,
	} from '$lib/stores/chatPanelStore.js';
	import { X } from 'lucide-svelte';

	import FixPanel from '$lib/pages/tasks/FixPanel.svelte';
	import ArchChat from '$lib/pages/architecture/ArchChat.svelte';
	import ProjectFixPanel from '$lib/pages/review/ProjectFixPanel.svelte';
	import FeatureChat from '$lib/pages/features/FeatureChat.svelte';
	import PageChat from '$lib/pages/chat/PageChat.svelte';
	import ChatModelPicker from '$lib/ui/ChatModelPicker.svelte';

	// ── Model override (persisted per context) ──

	const MODEL_STORAGE_PREFIX = 'skaro:chat-model:';

	function loadModelOverride(contextKey) {
		try {
			return localStorage.getItem(MODEL_STORAGE_PREFIX + contextKey) || '';
		} catch { return ''; }
	}

	function saveModelOverride(contextKey, value) {
		try {
			if (value) localStorage.setItem(MODEL_STORAGE_PREFIX + contextKey, value);
			else localStorage.removeItem(MODEL_STORAGE_PREFIX + contextKey);
		} catch { /* noop */ }
	}

	let modelOverrideKey = $derived(context ? `${context.type}:${context.id}` : '');
	let modelOverride = $state('');

	// Load model override when context changes.
	$effect(() => {
		if (modelOverrideKey) {
			modelOverride = loadModelOverride(modelOverrideKey);
		} else {
			modelOverride = '';
		}
	});

	function handleModelSelect(provider, model) {
		const value = `${provider}/${model}`;
		modelOverride = value;
		if (modelOverrideKey) saveModelOverride(modelOverrideKey, value);
	}

	// ── Context detection from URL + metadata ──

	let context = $derived.by(() => {
		const parts = $page.url.pathname.split('/').filter(Boolean);
		const section = parts[0];
		const meta = $chatContextMeta;

		if (section === 'tasks' && parts[1]) {
			return { type: 'task', id: decodeURIComponent(parts[1]) };
		}
		if (section === 'tasks' && !parts[1]) {
			return { type: 'tasks-list', id: 'tasks' };
		}
		if (section === 'architecture') {
			return { type: 'architecture', id: 'arch' };
		}
		if (section === 'review') {
			return { type: 'review', id: 'review' };
		}
		if (section === 'features' && parts[1]) {
			return { type: 'feature', id: decodeURIComponent(parts[1]) };
		}
		if (section === 'features' && !parts[1]) {
			return { type: 'features-list', id: 'features' };
		}
		if (section === 'constitution') {
			return { type: 'constitution', id: 'constitution' };
		}
		if (section === 'adr') {
			// Dynamic: adr-detail when an ADR is selected, adr-list otherwise.
			const adrNumber = meta?.adrNumber;
			if (adrNumber) {
				return { type: 'adr-detail', id: String(adrNumber) };
			}
			return { type: 'adr-list', id: 'adr' };
		}
		if (section === 'devplan') {
			return { type: 'devplan', id: 'devplan' };
		}
		return null;
	});

	let hasContext = $derived(context !== null);
	let visible = $derived($chatPanelOpen && hasContext);

	// ── Resizing ──

	let panelWidth = $derived($chatPanelWidth);
	let resizing = $state(false);

	function onResizeStart(e) {
		e.preventDefault();
		resizing = true;
		const startX = e.clientX;
		const startW = panelWidth;
		const maxW = Math.round(window.innerWidth * MAX_WIDTH_VW);

		function onMove(ev) {
			const delta = startX - ev.clientX;
			const newW = Math.min(Math.max(startW + delta, MIN_WIDTH), maxW);
			chatPanelWidth.set(newW);
		}

		function onUp() {
			resizing = false;
			document.removeEventListener('mousemove', onMove);
			document.removeEventListener('mouseup', onUp);
		}

		document.addEventListener('mousemove', onMove);
		document.addEventListener('mouseup', onUp);
	}

	// ── Keyboard shortcut (Escape to close) ──

	function handleKeydown(e) {
		if (e.key === 'Escape' && visible) {
			closeChatPanel();
		}
	}
</script>

<svelte:window onkeydown={handleKeydown} />

{#if visible}
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<aside
		class="right-panel"
		class:resizing
		style="width: {panelWidth}px"
	>
		<div class="resize-handle" onmousedown={onResizeStart}></div>

		<div class="right-panel-header">
			<ChatModelPicker
				value={modelOverride}
				onSelect={handleModelSelect}
			/>
			<button class="close-btn" onclick={closeChatPanel} title={$t('chat_panel.close')}>
				<X size={15} />
			</button>
		</div>

		<div class="right-panel-body">
			{#key context?.type + ':' + context?.id}
				{#if context?.type === 'task'}
					<FixPanel task={context.id} {modelOverride} />
				{:else if context?.type === 'architecture'}
					<ArchChat {modelOverride} />
				{:else if context?.type === 'review'}
					<ProjectFixPanel {modelOverride} />
				{:else if context?.type === 'feature'}
					<FeatureChat
						slug={context.id}
						{modelOverride}
						onConfirmed={() => window.dispatchEvent(new CustomEvent('skaro:feature-confirmed', { detail: { slug: context.id } }))}
					/>
				{:else if context?.type === 'constitution'}
					<PageChat
						contextType="constitution"
						roleName="architect"
						errorSource="constitutionChat"
						placeholderKey="chat_panel.placeholder_constitution"
						{modelOverride}
						onFileApplied={() => window.dispatchEvent(new CustomEvent('skaro:constitution-updated'))}
					/>
				{:else if context?.type === 'adr-list'}
					<PageChat
						contextType="adr"
						roleName="architect"
						errorSource="adrChat"
						placeholderKey="chat_panel.placeholder_adr"
						{modelOverride}
					/>
				{:else if context?.type === 'adr-detail'}
					<PageChat
						contextType="adr-detail"
						contextId={context.id}
						roleName="architect"
						errorSource="adrDetailChat"
						placeholderKey="chat_panel.placeholder_adr_detail"
						{modelOverride}
					/>
				{:else if context?.type === 'devplan'}
					<PageChat
						contextType="devplan"
						roleName="architect"
						errorSource="devplanChat"
						placeholderKey="chat_panel.placeholder_devplan"
						{modelOverride}
						onFileApplied={() => window.dispatchEvent(new CustomEvent('skaro:devplan-updated'))}
					/>
				{:else if context?.type === 'features-list'}
					<PageChat
						contextType="features"
						roleName="architect"
						errorSource="featuresChat"
						placeholderKey="chat_panel.placeholder_features"
						{modelOverride}
					/>
				{:else if context?.type === 'tasks-list'}
					<PageChat
						contextType="tasks"
						roleName="coder"
						errorSource="tasksChat"
						placeholderKey="chat_panel.placeholder_tasks"
						{modelOverride}
					/>
				{/if}
			{/key}
		</div>
	</aside>
{/if}

<style>
	.right-panel {
		display: flex;
		flex-direction: column;
		flex-shrink: 0;
		height: 100%;
		background: var(--bg-soft);
		border-left: 1px solid var(--bd);
		position: relative;
		min-width: 0;
	}

	/* Disable pointer events on iframes/etc during resize */
	.right-panel.resizing :global(*) {
		pointer-events: none;
	}
	.right-panel.resizing {
		pointer-events: auto;
	}

	/* ── Resize handle ── */
	.resize-handle {
		position: absolute;
		top: 0;
		left: -3px;
		width: 6px;
		height: 100%;
		cursor: col-resize;
		z-index: 20;
		transition: background .15s;
	}

	.resize-handle:hover,
	.resizing .resize-handle {
		background: var(--ac);
	}

	/* ── Header ── */
	.right-panel-header {
		height: 2.875rem;
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0 0.75rem;
		border-bottom: 1px solid var(--bd);
		flex-shrink: 0;
		background: var(--bg-soft);
		user-select: none;
	}

	.close-btn {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 1.75rem;
		height: 1.75rem;
		border: none;
		background: none;
		color: var(--tx-dim);
		cursor: pointer;
		border-radius: var(--r2);
		flex-shrink: 0;
		transition: color .12s, background .12s;
	}

	.close-btn:hover {
		color: var(--tx-bright);
		background: var(--sf);
	}

	/* ── Body (scroll container for chat) ── */
	.right-panel-body {
		flex: 1;
		overflow-y: auto;
		padding: 0 2rem;
        padding-bottom: 11rem;
		min-height: 0;
	}
</style>
