<script>
	import { t } from '$lib/i18n/index.js';
	import { page } from '$app/stores';
	import { status } from '$lib/stores/statusStore.js';
	import {
		chatPanelOpen, chatPanelWidth, closeChatPanel,
		MIN_WIDTH, MAX_WIDTH_VW,
	} from '$lib/stores/chatPanelStore.js';
	import { X, MessageSquare, Layers, ShieldCheck, Sparkles, PackageOpen } from 'lucide-svelte';

	import FixPanel from '$lib/pages/tasks/FixPanel.svelte';
	import ArchChat from '$lib/pages/architecture/ArchChat.svelte';
	import ProjectFixPanel from '$lib/pages/review/ProjectFixPanel.svelte';
	import FeatureChat from '$lib/pages/features/FeatureChat.svelte';

	// ── Context detection from URL ──

	let context = $derived.by(() => {
		const parts = $page.url.pathname.split('/').filter(Boolean);
		const section = parts[0];

		if (section === 'tasks' && parts[1]) {
			return { type: 'task', id: decodeURIComponent(parts[1]) };
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
		return null;
	});

	let hasContext = $derived(context !== null);
	let visible = $derived($chatPanelOpen && hasContext);

	// ── Context title & icon ──

	let contextTitle = $derived.by(() => {
		if (!context) return '';
		switch (context.type) {
			case 'task': return context.id;
			case 'architecture': return $t('chat_panel.ctx_architecture');
			case 'review': return $t('chat_panel.ctx_review');
			case 'feature': return context.id;
			default: return '';
		}
	});

	let ContextIcon = $derived.by(() => {
		if (!context) return MessageSquare;
		switch (context.type) {
			case 'task': return PackageOpen;
			case 'architecture': return Layers;
			case 'review': return ShieldCheck;
			case 'feature': return Sparkles;
			default: return MessageSquare;
		}
	});

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
			<span class="ctx-icon"><ContextIcon size={15} /></span>
			<span class="ctx-title" title={contextTitle}>{contextTitle}</span>
			<button class="close-btn" onclick={closeChatPanel} title={$t('chat_panel.close')}>
				<X size={15} />
			</button>
		</div>

		<div class="right-panel-body">
			{#key context?.type + ':' + context?.id}
				{#if context?.type === 'task'}
					<FixPanel task={context.id} />
				{:else if context?.type === 'architecture'}
					<ArchChat />
				{:else if context?.type === 'review'}
					<ProjectFixPanel />
				{:else if context?.type === 'feature'}
					<FeatureChat
						slug={context.id}
						onConfirmed={() => window.dispatchEvent(new CustomEvent('skaro:feature-confirmed', { detail: { slug: context.id } }))}
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
		background: var(--bg2);
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
		background: var(--bg0);
		user-select: none;
	}

	.ctx-icon {
		display: flex;
		align-items: center;
		color: var(--dm);
		flex-shrink: 0;
	}

	.ctx-title {
		font-size: 0.8125rem;
		font-weight: 600;
		color: var(--tx-bright);
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		flex: 1;
		min-width: 0;
	}

	.close-btn {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 1.75rem;
		height: 1.75rem;
		border: none;
		background: none;
		color: var(--dm);
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
