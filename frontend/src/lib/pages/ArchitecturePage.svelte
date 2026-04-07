<script>
	import { onMount, onDestroy } from 'svelte';
	import { t } from '$lib/i18n/index.js';
	import { api } from '$lib/api/client.js';
	import { status } from '$lib/stores/statusStore.js';
	import { addLog, addError } from '$lib/stores/logStore.js';
	import { cachedFetch, invalidate } from '$lib/api/cache.js';
	import { Layers, AlertTriangle, Info, Loader2, Pencil } from 'lucide-svelte';
	import ArchActions from './architecture/ArchActions.svelte';
	import MarkdownContent from '$lib/ui/MarkdownContent.svelte';
	import MdEditor from '$lib/ui/md-editor/MdEditor.svelte';

	let data = $state(null);
	let error = $state('');
	let approving = $state(false);
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
		} catch (e) { error = e.message; addError(e.message, 'architecture'); }
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
			<button class="btn" onclick={() => showEditor = true}>
				<Pencil size={14} /> {$t('editor.edit')}
			</button>
		</div>

	{:else if data.architecture_reviewed}
		<ArchActions
			architectureReviewed={true}
			hasDevplan={$status?.has_devplan}
			hasAdrs={(data.adr_count || 0) > 0}
			onEdit={() => showEditor = true}
		/>

	{:else}
		<ArchActions
			architectureReviewed={false}
			{approving}
			onApprove={approve}
			onEdit={() => showEditor = true}
		/>
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
	.arch-hint {
		color: var(--tx-dim);
		font-size: 0.875rem;
		margin-bottom: 0.75rem;
	}
</style>
