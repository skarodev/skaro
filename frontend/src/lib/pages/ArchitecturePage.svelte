<script>
	import { onMount } from 'svelte';
	import { t } from '$lib/i18n/index.js';
	import { api } from '$lib/api/client.js';
	import { status } from '$lib/stores/statusStore.js';
	import { addLog, addError } from '$lib/stores/logStore.js';
	import { cachedFetch, invalidate } from '$lib/api/cache.js';
	import { Layers, AlertTriangle, CheckCircle, Loader2, Pencil, Sparkles, FolderOpen } from 'lucide-svelte';
	import FileTabs from '$lib/ui/FileTabs.svelte';
	import ArchActions from './architecture/ArchActions.svelte';
	import ProposedArchitecture from './architecture/ProposedArchitecture.svelte';
	import MdEditor from '$lib/ui/md-editor/MdEditor.svelte';

	let data = $state(null);
	let error = $state('');
	let reviewing = $state(false);
	let accepting = $state(false);
	let accepted = $state(false);
	let approving = $state(false);
	let applying = $state(false);
	let generatingAdrs = $state(false);
	let reviewResult = $state('');
	let proposedArchitecture = $state('');
	let activeTab = $state('document');
	let showEditor = $state(false);

	onMount(() => { load(); });

	async function load() {
		try {
			data = await cachedFetch('architecture', () => api.getArchitecture());
			if (!reviewResult && data.last_review) {
				reviewResult = data.last_review;
			}
		} catch (e) { error = e.message; addError(e.message, 'architecture'); }
	}

	async function review() {
		reviewing = true;
		reviewResult = '';
		proposedArchitecture = '';
		accepted = false;
		addLog($t('log.arch_review_start'));
		try {
			const result = await api.runArchReview('', '');
			if (result.success) {
				addLog($t('log.arch_review_done'));
				reviewResult = result.message || '';
				proposedArchitecture = result.data?.proposed_architecture || '';
				invalidate('architecture', 'status');
				status.set(await api.getStatus());
				await load();
				if (reviewResult) activeTab = 'review';
			} else {
				addError(result.message, 'archReview');
				reviewResult = result.message;
			}
		} catch (e) { addError(e.message, 'archReview'); reviewResult = e.message; }
		reviewing = false;
	}

	async function applyReview() {
		applying = true;
		proposedArchitecture = '';
		accepted = false;
		addLog($t('log.arch_apply_start'));
		try {
			const result = await api.applyArchReview();
			if (result.success && result.proposed_architecture) {
				addLog($t('log.arch_apply_done'));
				proposedArchitecture = result.proposed_architecture;
			} else {
				addError(result.message || 'No result', 'archApply');
			}
		} catch (e) { addError(e.message, 'archApply'); }
		applying = false;
	}

	async function generateAdrsFromReview() {
		generatingAdrs = true;
		addLog($t('log.adr_generate_start'));
		try {
			const result = await api.generateAdrs();
			if (result.success) {
				addLog($t('log.adr_generated', { count: result.count }));
				invalidate('adrs', 'status');
				status.set(await api.getStatus());
				await load();
			} else { addError(result.message, 'adrGenerate'); }
		} catch (e) { addError(e.message, 'adrGenerate'); }
		generatingAdrs = false;
	}

	async function acceptProposed() {
		if (!proposedArchitecture) return;
		accepting = true;
		try {
			const result = await api.acceptArchitecture(proposedArchitecture);
			if (result.success) {
				addLog($t('log.arch_accepted'));
				accepted = true;
				invalidate('architecture', 'status');
				status.set(await api.getStatus());
				await load();
			} else { addError(result.message, 'archAccept'); }
		} catch (e) { addError(e.message, 'archAccept'); }
		accepting = false;
	}

	async function approve() {
		approving = true;
		try {
			const result = await api.approveArchitecture();
			if (result.success) {
				addLog($t('log.arch_approved'));
				invalidate('architecture', 'status');
				status.set(await api.getStatus());
				await load();
			} else { addError(result.message, 'archApprove'); }
		} catch (e) { addError(e.message, 'archApprove'); }
		approving = false;
	}

	async function saveContent(content) {
		try {
			const result = await api.saveArchitecture(content);
			if (result.success) {
				addLog($t('editor.doc_saved'));
				invalidate('architecture', 'status');
				status.set(await api.getStatus());
				await load();
			} else { addError(result.message, 'archSave'); }
		} catch (e) { addError(e.message, 'archSave'); }
	}

	async function saveInvariants(content) {
		try {
			const result = await api.updateInvariants(content);
			if (result.success) {
				addLog($t('editor.doc_saved'));
				invalidate('architecture', 'status');
				status.set(await api.getStatus());
				await load();
			} else { addError(result.message, 'invSave'); }
		} catch (e) { addError(e.message, 'invSave'); }
	}

	// ── Tabs ──
	let archTabs = $derived.by(() => {
		const tabs = [];
		if (data?.content) {
			tabs.push({ id: 'document', label: $t('arch.document') });
		}
		if (reviewResult && !reviewing) {
			tabs.push({ id: 'review', label: $t('arch.review_result') });
		}
		if (data?.has_invariants) {
			tabs.push({ id: 'invariants', label: $t('arch.invariants') });
		}
		return tabs;
	});

	let archTabContent = $derived.by(() => {
		if (activeTab === 'review') return reviewResult || '';
		if (activeTab === 'invariants') return data?.invariants || '';
		return data?.content || '';
	});

	/** Show review action buttons when review tab is active and there's a review */
	let showReviewActions = $derived(
		activeTab === 'review' && reviewResult && !reviewing && !proposedArchitecture
	);

	$effect(() => {
		if (archTabs.length > 0 && !archTabs.find(t => t.id === activeTab)) {
			activeTab = archTabs[0].id;
		}
	});
</script>

<div class="page-with-tabs">
<div class="main-header">
	<h2><Layers size={24} /> {$t('arch.title')}</h2>
	<p>{$t('arch.subtitle')}</p>
</div>

{#if error}
	<div class="alert alert-warn"><AlertTriangle size={14} /> {error}</div>
{:else if !data}
	<div class="loading-text"><Loader2 size={14} class="spin" /> {$t('app.loading')}</div>
{:else}
	{#if !data.has_architecture}
		<div class="alert alert-warn"><AlertTriangle size={14} /> {$t('arch.empty')}</div>
		<div class="instructions">
			<h4>{$t('const.next_steps')}</h4>
			<ol>
				<li>{$t('arch.step1', { file: '.skaro/architecture/architecture.md' })}</li>
				<li>{$t('arch.step2')}</li>
				<li>{$t('arch.step3')}</li>
			</ol>
		</div>
		<div class="btn-group">
			<button class="btn btn-primary" onclick={() => showEditor = true}>
				<Pencil size={14} /> {$t('editor.edit')}
			</button>
		</div>

	{:else if data.architecture_reviewed}
		<div class="alert alert-success"><CheckCircle size={14} /> {$t('arch.approved')}</div>
		<ArchActions
			architectureReviewed={true}
			hasDevplan={$status?.has_devplan}
			hasAdrs={(data.adr_count || 0) > 0}
			{reviewing}
			onReview={review}
			onEdit={() => showEditor = true}
		/>

	{:else}
		<div class="alert alert-info">{$t('arch.has_arch')}</div>
		<ArchActions
			architectureReviewed={false}
			hasReviewResult={!!reviewResult}
			{reviewing} {approving}
			onReview={review} onApprove={approve}
			onEdit={() => showEditor = true}
		/>
	{/if}

	{#if archTabs.length > 0}
		<FileTabs
			tabs={archTabs}
			activeTab={activeTab}
			content={archTabContent}
			onSelectTab={(id) => activeTab = id}
		/>
	{/if}

	<!-- Review action buttons — shown below review content -->
	{#if showReviewActions}
		<div class="review-actions">
			<button class="btn btn-primary" disabled={applying} onclick={applyReview}>
				{#if applying}<Loader2 size={14} class="spin" />{:else}<Sparkles size={14} />{/if}
				{$t('arch.apply_review')}
			</button>
			<button class="btn" disabled={generatingAdrs} onclick={generateAdrsFromReview}>
				{#if generatingAdrs}<Loader2 size={14} class="spin" />{:else}<FolderOpen size={14} />{/if}
				{$t('arch.create_adrs_from_review')}
			</button>
		</div>
	{/if}

	<!-- Proposed architecture — from initial review OR from apply-review -->
	{#if proposedArchitecture && activeTab === 'review'}
		<ProposedArchitecture
			content={proposedArchitecture}
			{accepting} {accepted}
			onAccept={acceptProposed}
		/>
	{/if}
{/if}

</div>

{#if showEditor}
	<MdEditor
		content={activeTab === 'invariants' ? (data?.invariants || '') : (data?.content || '')}
		onSave={(c) => {
			if (activeTab === 'invariants') { saveInvariants(c); } else { saveContent(c); }
			showEditor = false;
		}}
		onClose={() => showEditor = false}
	/>
{/if}

<style>
	.review-actions {
		display: flex;
		gap: 0.5rem;
		margin-top: 0.75rem;
		padding: 0.75rem;
		background: var(--sf);
		border: 0.0625rem solid var(--bd);
		border-radius: var(--r);
	}
</style>
