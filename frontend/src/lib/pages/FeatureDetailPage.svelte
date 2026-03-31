<script>
	import { goto } from '$app/navigation';
	import { onMount, onDestroy } from 'svelte';
	import { t } from '$lib/i18n/index.js';
	import { api } from '$lib/api/client.js';
	import { status } from '$lib/stores/statusStore.js';
	import { addLog, addError } from '$lib/stores/logStore.js';
	import { invalidate } from '$lib/api/cache.js';
	import { ArrowLeft, Loader2, AlertTriangle, Pencil, Sparkles, MessageSquare } from 'lucide-svelte';
	import FileTabs from '$lib/ui/FileTabs.svelte';
	import MdEditor from '$lib/ui/md-editor/MdEditor.svelte';
	import FeatureInfo from '$lib/pages/features/FeatureInfo.svelte';
	import { openChatPanel } from '$lib/stores/chatPanelStore.js';

	let { slug = '' } = $props();

	let feature = $state(null);
	let loading = $state(true);
	let error = $state('');
	let activeFileTab = $state('');
	let tabInitialized = false;
	let showEditor = $state(false);

	// Listen for feature-confirmed from RightPanel's FeatureChat
	function handleFeatureConfirmedEvent(e) {
		if (e.detail?.slug === slug) handleConfirmed();
	}

	onMount(() => {
		window.addEventListener('skaro:feature-confirmed', handleFeatureConfirmedEvent);
	});

	onDestroy(() => {
		window.removeEventListener('skaro:feature-confirmed', handleFeatureConfirmedEvent);
	});

	// Reset on slug change — same pattern as TaskDetail
	$effect(() => {
		void slug;
		activeFileTab = '';
		tabInitialized = false;
		showEditor = false;
		if (slug) load();
	});

	async function load() {
		loading = true;
		try {
			feature = await api.getFeature(slug);
			error = '';
		} catch (e) { error = e.message; addError(e.message, 'featureDetail'); }
		loading = false;
	}

	async function handleConfirmed() {
		invalidate('features', 'status');
		status.set(await api.getStatus());
		tabInitialized = false;
		await load();
	}

	async function savePlan(content) {
		try {
			const result = await api.saveFeaturePlan(slug, content);
			if (result.success) {
				addLog($t('feature.plan_saved'));
				showEditor = false;
				await load();
			} else { addError(result.message, 'featurePlan'); }
		} catch (e) { addError(e.message, 'featurePlan'); }
	}

	let isDraft = $derived(feature?.status === 'draft');

	// Auto-open chat panel for draft features (replaces old chat tab behavior)
	$effect(() => {
		if (isDraft) openChatPanel();
	});

	// ── Tabs — same pattern as TaskDetail.fileTabs ──
	let fileTabs = $derived.by(() => {
		if (!feature) return [];
		if (isDraft) return [];
		return [
			{ id: 'info', label: $t('feature.tab_info') },
			{ id: 'plan', label: $t('feature.tab_plan') },
		];
	});

	// ── Tab init — EXACT same pattern as TaskDetail ──
	$effect(() => {
		if (fileTabs.length > 0 && !tabInitialized) {
			tabInitialized = true;
			activeFileTab = fileTabs[0].id;
		}
	});

	// ── Active content for markdown-rendered tabs ──
	let activeContent = $derived.by(() => {
		if (!feature) return '';
		const id = activeFileTab || fileTabs[0]?.id || '';
		if (id === 'info') return '';
		if (id === 'plan') return feature.plan || `*${$t('feature.no_plan')}*`;
		return '';
	});

	let isTabEditable = $derived(activeFileTab === 'plan' && !isDraft);
	let displayTitle = $derived(feature?.title || feature?.slug || slug);

	function statusBadgeClass(s) {
		if (s === 'draft') return 'badge-draft';
		if (s === 'planned') return 'badge-planned';
		if (s === 'in-progress') return 'badge-progress';
		if (s === 'done') return 'badge-done';
		if (s === 'cancelled') return 'badge-cancelled';
		return '';
	}

	function goBack() { goto('/features'); }
</script>

{#if error}
	<div class="alert alert-warn"><AlertTriangle size={14} /> {error}</div>
{:else if loading}
	<div class="loading-text"><Loader2 size={14} class="spin" /> {$t('app.loading')}</div>
{:else if feature}
	<div class="detail page-with-tabs">
		<button class="back" type="button" onclick={goBack}>
			<ArrowLeft size={14} /> {$t('feature.back')}
		</button>

		<div class="main-header">
			<h2>
				<span class="status-icon"><Sparkles size={24} /></span>
				{displayTitle}
			</h2>
			<span class="badge {statusBadgeClass(feature.status)}">
				{$t('feature.status_' + feature.status)}
			</span>
		</div>

		<FileTabs
			tabs={fileTabs}
			activeTab={activeFileTab}
			content={activeContent}
			onSelectTab={(id) => activeFileTab = id}
		>
			{#snippet contentActionsSlot()}
				{#if isTabEditable}
					<div class="content-actions">
						<button class="btn btn-sm" onclick={() => showEditor = true}>
							<Pencil size={14} /> {$t('editor.edit')}
						</button>
					</div>
				{/if}
			{/snippet}

			{#snippet infoSlot()}
				<FeatureInfo {feature} />
			{/snippet}
		</FileTabs>

		{#if isDraft}
			<div class="draft-hint">
				<p>{$t('feature.draft_hint')}</p>
				<button class="btn btn-primary" onclick={openChatPanel}>
					<MessageSquare size={14} /> {$t('chat_panel.open')}
				</button>
			</div>
		{/if}
	</div>

	{#if showEditor}
		<MdEditor
			content={feature.plan || ''}
			onSave={(c) => savePlan(c)}
			onClose={() => { showEditor = false; }}
		/>
	{/if}
{/if}

<style>
	.detail { padding-bottom: 0; }

	.back {
		display: inline-flex; align-items: center; gap: 0.25rem;
		color: var(--dm); font-size: 0.8125rem; cursor: pointer; margin-bottom: 0.75rem;
		background: none; border: none; padding: 0; font-family: inherit;
	}
	.back:hover { color: var(--ac); }

	.main-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 1rem;
	}

	.main-header h2 {
		margin: 0;
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}

	.status-icon { display: inline-flex; align-items: center; color: var(--tx-bright); }

	.badge {
		display: inline-block;
		padding: 0.125rem 0.5rem;
		border-radius: 0.625rem;
		font-size: 0.75rem;
		font-weight: 500;
		line-height: 1.125rem;
		white-space: nowrap;
		flex-shrink: 0;
	}

	.badge-draft { background: rgba(130, 130, 160, .12); color: var(--dm); }
	.badge-planned { background: rgba(187, 181, 41, .12); color: var(--yl); }
	.badge-progress { background: rgba(26, 165, 194, .15); color: var(--ac); }
	.badge-done { background: rgba(106, 135, 89, .15); color: var(--gn-bright); }
	.badge-cancelled { background: rgba(180, 80, 80, .12); color: var(--rd); }

	.content-actions {
		display: flex;
		gap: 0.5rem;
		justify-content: flex-end;
		margin-bottom: 0.75rem;
	}

	.draft-hint {
		text-align: center;
		padding: 2rem 1rem;
		color: var(--dm);
		font-size: 0.875rem;
	}

	.draft-hint p {
		margin-bottom: 0.75rem;
	}
</style>
