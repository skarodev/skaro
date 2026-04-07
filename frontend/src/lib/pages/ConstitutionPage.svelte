<script>
	import { onMount } from 'svelte';
	import { t } from '$lib/i18n/index.js';
	import { api } from '$lib/api/client.js';
	import { addLog, addError } from '$lib/stores/logStore.js';
	import { cachedFetch, invalidate } from '$lib/api/cache.js';
	import { status } from '$lib/stores/statusStore.js';
	import { FileText, AlertTriangle, CheckCircle, Loader2, Pencil } from 'lucide-svelte';
	import MarkdownContent from '$lib/ui/MarkdownContent.svelte';
	import MdEditor from '$lib/ui/md-editor/MdEditor.svelte';
	import TemplatePicker from '$lib/pages/constitution/TemplatePicker.svelte';

	let data = $state(null);
	let approving = $state(false);
	let error = $state('');
	let showEditor = $state(false);
	let editorContent = $state('');
	let selectedPresetId = $state(/** @type {string|null} */ (null));

	onMount(() => { load(); });

	async function load() {
		try { data = await cachedFetch('constitution', () => api.getConstitution()); }
		catch (e) { error = e.message; addError(e.message, 'constitution'); }
	}

	async function approve() {
		approving = true;
		try {
			await api.approveConstitution();
			addLog($t('const.approved_log'));
			invalidate('status');
			status.set(await api.getStatus());
		} catch (e) { addError(e.message, 'approveConstitution'); error = e.message; }
		approving = false;
	}

	async function saveContent(text) {
		try {
			await api.saveConstitution(text, selectedPresetId);
			selectedPresetId = null;
			invalidate('constitution', 'status');
			status.set(await api.getStatus());
			await load();
			addLog($t('editor.doc_saved'));
			showEditor = false;
		} catch (e) { addError(e.message, 'constitutionSave'); throw e; }
	}

	function openPreset(content, presetId) {
		selectedPresetId = presetId;
		editorContent = content;
		showEditor = true;
	}

	function openEditor() {
		selectedPresetId = null;
		editorContent = data?.content || '';
		showEditor = true;
	}

	let isValidated = $derived($status?.constitution_validated);
</script>

<div class="main-header">
	<h2>
		{$t('const.title')}
		{#if data?.has_constitution}
			{#if isValidated}
				<span class="status-badge status-badge-ok">{$t('status.approved')}</span>
			{:else}
				<span class="status-badge status-badge-pending">{$t('status.not_approved')}</span>
			{/if}
		{/if}
	</h2>
	<p>{$t('const.subtitle')}</p>
</div>

{#if error}
	<div class="alert alert-warn"><AlertTriangle size={14} /> {error}</div>
{:else if !data}
	<div class="loading-text"><Loader2 size={14} class="spin" /> {$t('app.loading')}</div>
{:else}
	{#if !data.has_constitution}
		<div class="alert alert-info"><AlertTriangle size={14} /> {$t('const.empty')}</div>
		<TemplatePicker onSelect={openPreset} />
		<div class="btn-group">
			<button class="btn" onclick={openEditor}>
				<Pencil size={14} /> {$t('editor.edit')}
			</button>
		</div>
	{:else}
		<div class="btn-group">
			{#if !isValidated}
				<button class="btn btn-primary" disabled={approving} onclick={approve}>
					{#if approving}<Loader2 size={14} class="spin" />{:else}<CheckCircle size={14} />{/if}
					{$t('const.approve')}
				</button>
			{/if}
			<button class="btn" onclick={openEditor}>
				<Pencil size={14} /> {$t('editor.edit')}
			</button>
		</div>
	{/if}

	{#if data.content}
        <MarkdownContent content={data.content} />
	{/if}

	{#if showEditor}
		<MdEditor
			content={editorContent}
			onSave={saveContent}
			onClose={() => showEditor = false}
		/>
	{/if}
{/if}
