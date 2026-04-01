<script>
	import { onMount } from 'svelte';
	import { t } from '$lib/i18n/index.js';
	import { api } from '$lib/api/client.js';
	import { status } from '$lib/stores/statusStore.js';
	import { addLog, addError } from '$lib/stores/logStore.js';
	import { cachedFetch, invalidate } from '$lib/api/cache.js';
	import { FolderOpen, AlertTriangle, Loader2, Plus, ChevronLeft, Pencil, Sparkles, ClipboardList } from 'lucide-svelte';
	import MarkdownContent from '$lib/ui/MarkdownContent.svelte';
	import MdEditor from '$lib/ui/md-editor/MdEditor.svelte';

	/** @type {{ adrs: any[] } | null} */
	let data = $state(null);
	let error = $state('');
	let creating = $state(false);
	let generating = $state(false);
	let newTitle = $state('');
	let showCreateForm = $state(false);
	let showEditor = $state(false);

	/** @type {any | null} Currently expanded ADR */
	let selectedAdr = $state(null);

	/** @type {HTMLInputElement | null} */
	let createInput = $state(null);

	$effect(() => {
		if (showCreateForm && createInput) createInput.focus();
	});

	/** @type {number | null} ADR number whose status is being changed */
	let changingStatus = $state(null);

	let hasArchitecture = $derived($status?.has_architecture && $status?.architecture_reviewed);

	onMount(() => { load(); });

	async function load() {
		try {
			data = await cachedFetch('adrs', () => api.getAdrs());
		} catch (e) { error = e.message; addError(e.message, 'adr'); }
	}

	async function createAdr() {
		const title = newTitle.trim();
		if (!title) return;
		creating = true;
		try {
			const result = await api.createAdr(title);
			if (result.success) {
				addLog($t('log.adr_created', { n: result.number, title }));
				newTitle = '';
				showCreateForm = false;
				invalidate('adrs', 'status');
				status.set(await api.getStatus());
				await load();
			} else { addError(result.message, 'adrCreate'); }
		} catch (e) { addError(e.message, 'adrCreate'); }
		creating = false;
	}

	async function generateAdrs() {
		generating = true;
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
		generating = false;
	}

	async function changeStatus(adr, newStatus) {
		changingStatus = adr.number;
		try {
			const result = await api.updateAdrStatus(adr.number, newStatus);
			if (result.success) {
				addLog($t('log.adr_status_changed', { n: adr.number, status: newStatus }));
				invalidate('adrs', 'status');
				await load();
				if (selectedAdr?.number === adr.number) {
					selectedAdr = data?.adrs?.find(a => a.number === adr.number) || null;
				}
			} else { addError(result.message, 'adrStatus'); }
		} catch (e) { addError(e.message, 'adrStatus'); }
		changingStatus = null;
	}

	async function saveAdr(content) {
		if (!selectedAdr) return;
		try {
			const result = await api.saveAdrContent(selectedAdr.number, content);
			if (result.success) {
				addLog($t('editor.doc_saved'));
				invalidate('adrs');
				await load();
				selectedAdr = data?.adrs?.find(a => a.number === selectedAdr.number) || null;
			} else { addError(result.message, 'adrSave'); }
		} catch (e) { addError(e.message, 'adrSave'); }
	}

	function statusBadgeClass(s) {
		if (s === 'accepted') return 'badge-accepted';
		if (s === 'deprecated') return 'badge-deprecated';
		if (s === 'superseded') return 'badge-superseded';
		return 'badge-proposed';
	}

	const STATUSES = ['proposed', 'accepted', 'deprecated', 'superseded'];

	function handleCreateKeydown(e) {
		if (e.key === 'Enter') createAdr();
		if (e.key === 'Escape') { showCreateForm = false; newTitle = ''; }
	}
</script>

<div class="main-header">
	<h2><FolderOpen size={24} /> {$t('adr.title')}</h2>
	<p>{$t('adr.subtitle')}</p>
</div>

{#if error}
	<div class="alert alert-warn"><AlertTriangle size={14} /> {error}</div>
{:else if !data}
	<div class="loading-text"><Loader2 size={14} class="spin" /> {$t('app.loading')}</div>
{:else if selectedAdr}
	<!-- ══ Detail View ══ -->
	<div>
		<button class="back-btn" onclick={() => selectedAdr = null}>
			<ChevronLeft size={14} /> {$t('adr.back')}
		</button>
	</div>

	<div class="detail-header">
		<h3>ADR-{String(selectedAdr.number).padStart(3, '0')}: {selectedAdr.title}</h3>
		<span class="badge {statusBadgeClass(selectedAdr.status)}">
			{$t('adr.status_' + selectedAdr.status)}
		</span>
	</div>

	<div class="status-actions">
		{#each STATUSES.filter(s => s !== selectedAdr.status) as s}
			<button
				class="btn-status"
				disabled={changingStatus === selectedAdr.number}
				onclick={() => changeStatus(selectedAdr, s)}
			>
				→ {$t('adr.status_' + s)}
			</button>
		{/each}
		<button class="btn-status" onclick={() => showEditor = true}>
			<Pencil size={12} /> {$t('editor.edit')}
		</button>
	</div>

	<div class="card">
		<MarkdownContent content={selectedAdr.content} />
	</div>
{:else}
	<!-- ══ List View ══ -->
	{#if data.adrs.length === 0}
		<div class="card empty">
			<p>{$t('adr.empty')}</p>
			<p class="hint">{$t('adr.empty_hint')}</p>
		</div>
		<div class="btn-group">
			{#if hasArchitecture}
				<button class="btn btn-primary" disabled={generating} onclick={generateAdrs}>
					{#if generating}<Loader2 size={14} class="spin" />{:else}<Sparkles size={14} />{/if}
					{$t('adr.generate')}
				</button>
			{:else}
				<div class="alert alert-info" style="margin: 0;">
					<AlertTriangle size={14} /> {$t('adr.need_arch')}
				</div>
			{/if}
			<button class="btn" onclick={() => showCreateForm = true}>
				<Plus size={14} /> {$t('adr.create')}
			</button>
		</div>
	{:else}
		<div class="btn-group">
			{#if hasArchitecture}
				<button class="btn" disabled={generating} onclick={generateAdrs}>
					{#if generating}<Loader2 size={14} class="spin" />{:else}<Sparkles size={14} />{/if}
					{$t('adr.generate')}
				</button>
			{/if}
			<button class="btn" onclick={() => showCreateForm = true}>
				<Plus size={14} /> {$t('adr.create')}
			</button>
			{#if !$status?.has_devplan}
				<a class="hint-link" href="/devplan">
					<ClipboardList size={14} /> {$t('adr.go_devplan')}
				</a>
			{/if}
		</div>
		<div class="adr-table-wrap">
			<table class="adr-table">
				<thead>
					<tr>
						<th class="col-num">{$t('adr.col_number')}</th>
						<th class="col-title">{$t('adr.col_title')}</th>
						<th class="col-status">{$t('adr.col_status')}</th>
						<th class="col-date">{$t('adr.col_date')}</th>
					</tr>
				</thead>
				<tbody>
					{#each data.adrs as adr}
						<tr class="adr-row" onclick={() => selectedAdr = adr}>
							<td class="col-num">{String(adr.number).padStart(3, '0')}</td>
							<td class="col-title">{adr.title}</td>
							<td class="col-status">
								<span class="badge {statusBadgeClass(adr.status)}">
									{$t('adr.status_' + adr.status)}
								</span>
							</td>
							<td class="col-date">{adr.date || '—'}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{/if}

	{#if showCreateForm}
		<div class="create-form">
			<input
				type="text"
				bind:value={newTitle}
				bind:this={createInput}
				placeholder={$t('adr.create_placeholder')}
				onkeydown={handleCreateKeydown}
				disabled={creating}
			/>
			<button class="btn btn-primary" onclick={createAdr} disabled={creating || !newTitle.trim()}>
				{creating ? $t('adr.creating') : $t('adr.create')}
			</button>
			<button class="btn" onclick={() => { showCreateForm = false; newTitle = ''; }}>
				{$t('devplan.cancel')}
			</button>
		</div>
	{/if}
{/if}

{#if showEditor && selectedAdr}
	<MdEditor
		content={selectedAdr.content}
		onSave={(c) => { saveAdr(c); showEditor = false; }}
		onClose={() => showEditor = false}
	/>
{/if}

<style>
	/* ── Empty state ── */
	.card.empty {
		text-align: center;
		padding: 2rem 1.25rem;
		color: var(--dm);
	}
	.card.empty p { margin: 0.25rem 0; }
	.card.empty .hint { font-size: 0.8125rem; }

	/* ── Create form ── */
	.create-form {
		display: flex;
		gap: 0.5rem;
		align-items: center;
		margin-top: 0.75rem;
	}

	.create-form input {
		flex: 1;
		padding: 0.4375rem 0.625rem;
		border: 0.0625rem solid var(--bd);
		border-radius: var(--r);
		background: var(--bg-deep);
		color: var(--tx);
		font-size: 0.875rem;
		font-family: inherit;
	}

	.create-form input:focus {
		outline: none;
		border-color: var(--ac);
	}

	/* ── Table ── */
	.adr-table-wrap {
		margin-top: 0.75rem;
		border: 0.0625rem solid var(--bd);
		border-radius: var(--r);
		overflow: hidden;
	}

	.adr-table {
		width: 100%;
		border-collapse: collapse;
		font-size: 0.875rem;
	}

	.adr-table thead {
		background: var(--bd);
	}

	.adr-table th {
		padding: 0.5rem 0.75rem;
		text-align: left;
		color: var(--dm);
		font-weight: 600;
		font-size: 0.85rem;
		text-transform: uppercase;
		letter-spacing: .03em;
		border-bottom: 1px solid var(--bd);
	}

	.adr-table td {
		padding: 0.625rem 0.75rem;
		border-bottom: 1px solid var(--bd);
	}

	.adr-table tr:last-child td {
		border-bottom: none;
	}

	.adr-row {
		cursor: pointer;
		transition: background .1s;
	}

	.adr-row:hover {
		background: var(--bg-deep);
	}

	.col-num { width: 3.125rem; font-family: var(--font-ui); color: var(--dm); }
	.col-status { width: 6.875rem; }
	.col-date { width: 6.875rem; font-family: var(--font-ui); color: var(--dm); font-size: 0.8125rem; }

	/* ── Status badges ── */
	.badge {
		display: inline-block;
		padding: 0.125rem 0.5rem;
		border-radius: 0.625rem;
		font-size: 0.75rem;
		font-weight: 500;
		line-height: 1.125rem;
		white-space: nowrap;
	}

	.badge-proposed { background: rgba(187, 181, 41, .12); color: var(--yl); }
	.badge-accepted { background: rgba(106, 135, 89, .15); color: var(--gn-bright); }
	.badge-deprecated { background: rgba(180, 80, 80, .12); color: var(--rd); }
	.badge-superseded { background: rgba(130, 130, 160, .12); color: var(--dm); }

	/* ── Detail view ── */
	.back-btn {
		display: inline-flex;
		align-items: center;
		gap: 0.25rem;
		background: none;
		border: none;
		color: var(--ac);
		cursor: pointer;
		padding: 0.25rem 0;
		font-size: 0.875rem;
		font-family: inherit;
		margin-bottom: 0.5rem;
	}

	.back-btn:hover { text-decoration: underline; }

	.detail-header {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		margin-bottom: 0.5rem;
	}

	.detail-header h3 {
		margin: 0;
		font-size: 1.125rem;
		color: var(--tx-bright);
	}

	.status-actions {
		display: flex;
		gap: 0.375rem;
		margin-bottom: 0.75rem;
	}

	.btn-status {
		display: inline-flex;
		align-items: center;
		gap: 0.25rem;
		padding: 0.25rem 0.625rem;
		border: 0.0625rem solid var(--bd);
		border-radius: var(--r);
		background: var(--bg-deep);
		color: var(--tx);
		cursor: pointer;
		font-size: 0.75rem;
		font-family: inherit;
		transition: background .1s, border-color .1s;
	}

	.btn-status:hover {
		background: var(--sf);
		border-color: var(--ac);
	}

	.btn-status:disabled {
		opacity: .5;
		cursor: default;
	}

	/* ── Shared ── */
	.hint-link {
		display: inline-flex;
		align-items: center;
		gap: 0.25rem;
		color: var(--ac);
		font-size: 0.8125rem;
		cursor: pointer;
		padding: 0.25rem 0.5rem;
	}
	.hint-link:hover { text-decoration: underline; }
</style>
