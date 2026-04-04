<script>
	import { onMount, onDestroy } from 'svelte';
	import { t } from '$lib/i18n/index.js';
	import { api } from '$lib/api/client.js';
	import { status } from '$lib/stores/statusStore.js';
	import { addLog, addError } from '$lib/stores/logStore.js';
	import { cachedFetch, invalidate } from '$lib/api/cache.js';
	import { Layers, AlertTriangle, Info, Loader2, Pencil, Sparkles, FolderOpen, MessageSquare } from 'lucide-svelte';
	import ArchActions from './architecture/ArchActions.svelte';
	import ProposedArchitecture from './architecture/ProposedArchitecture.svelte';
	import MarkdownContent from '$lib/ui/MarkdownContent.svelte';
	import MdEditor from '$lib/ui/md-editor/MdEditor.svelte';
	import { openChatPanel } from '$lib/stores/chatPanelStore.js';

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
	let showEditor = $state(false);

	onMount(() => {
		load();
		window.addEventListener('skaro:architecture-updated', handleArchUpdated);
	});

	onDestroy(() => {
		window.removeEventListener('skaro:architecture-updated', handleArchUpdated);
	});

	function handleArchUpdated() { load(); }

	async function load() {
		try {
			data = await cachedFetch('architecture', () => api.getArchitecture());
			if (!reviewResult && data.last_review) {
				reviewResult = data.last_review;
			}
		} catch (e) { error = e.message; addError(e.message, 'architecture'); }
	}

	function openChat() {
		openChatPanel();
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

	let showReviewActions = $derived(
		reviewResult && !reviewing && !proposedArchitecture
	);
</script>

<div class="main-header">
	<h2>
		{$t('arch.title')}
		{#if data?.has_architecture}
			{#if data.architecture_reviewed}
				<span class="status-badge status-badge-ok">{$t('status.approved')}</span>
			{:else}
				<span class="status-badge status-badge-pending">{$t('status.not_approved')}</span>
			{/if}
		{/if}
	</h2>
	<p>{$t('arch.subtitle')}</p>
</div>

{#if error}
	<div class="alert alert-warn"><AlertTriangle size={14} /> {error}</div>
{:else if !data}
	<div class="loading-text"><Loader2 size={14} class="spin" /> {$t('app.loading')}</div>
{:else}
	{#if !data.has_architecture}
		<div class="alert alert-info"><Info size={14} /> {$t('arch.empty')}</div>
		<p class="arch-hint">{$t('arch.generate_hint')}</p>
		<div class="btn-group">
			<button class="btn btn-primary" onclick={openChat}>
				<MessageSquare size={14} /> {$t('arch.generate_with_ai')}
			</button>
			<button class="btn" onclick={() => showEditor = true}>
				<Pencil size={14} /> {$t('editor.edit')}
			</button>
		</div>

	{:else if data.architecture_reviewed}
		<ArchActions
			architectureReviewed={true}
			hasDevplan={$status?.has_devplan}
			hasAdrs={(data.adr_count || 0) > 0}
			{reviewing}
			onReview={review}
			onEdit={() => showEditor = true}
		/>

	{:else}
		<ArchActions
			architectureReviewed={false}
			hasReviewResult={!!reviewResult}
			{reviewing} {approving}
			onReview={review} onApprove={approve}
			onEdit={() => showEditor = true}
		/>
	{/if}

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

	{#if proposedArchitecture}
		<ProposedArchitecture
			content={proposedArchitecture}
			{accepting} {accepted}
			onAccept={acceptProposed}
		/>
	{/if}

	{#if reviewResult && !reviewing}
		<div class="review-result-section">
			<h3>{$t('arch.review_result')}</h3>
			<MarkdownContent content={reviewResult} />
		</div>
	{/if}

	{#if data?.content}
		<MarkdownContent content={data.content} />
	{/if}
{/if}

{#if showEditor}
	<MdEditor
		content={data?.content || ''}
		onSave={(c) => {
			saveContent(c);
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

	.arch-hint {
		color: var(--tx-dim);
		font-size: 0.875rem;
		margin-bottom: 0.75rem;
	}

	.review-result-section {
		margin-top: 1.5rem;
		padding-top: 1rem;
		border-top: 0.0625rem solid var(--bd);
	}

	.review-result-section h3 {
		font-size: 0.875rem;
		font-weight: 600;
		color: var(--tx-dim);
		text-transform: uppercase;
		letter-spacing: 0.03em;
		margin-bottom: 0.75rem;
	}
</style>
