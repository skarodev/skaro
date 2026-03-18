<script>
	import { onMount } from 'svelte';
	import { t } from '$lib/i18n/index.js';
	import { api } from '$lib/api/client.js';
	import { addLog, addError } from '$lib/stores/logStore.js';
	import { status } from '$lib/stores/statusStore.js';
	import { invalidate } from '$lib/api/cache.js';
	import { BarChart3, Upload, FileText, Loader2, Trash2, AlertTriangle, CheckCircle, Play, Pencil, ChevronLeft, ListChecks, Sparkles } from 'lucide-svelte';
	import MarkdownContent from '$lib/ui/MarkdownContent.svelte';

	let data = $state(null);
	let loading = $state(true);
	let error = $state('');
	let running = $state(false);
	let uploading = $state(false);
	let cleaning = $state(false);

	// TS editor state
	let showEditor = $state(false);
	let editorContent = $state('');
	/** @type {HTMLInputElement | null} */
	let fileInput = $state(null);

	// Requirements list/detail state
	/** @type {any | null} */
	let selectedReq = $state(null);

	onMount(() => { load(); });

	async function load() {
		loading = true;
		try {
			data = await api.getAnalytics();
		} catch (e) {
			error = e.message;
			addError(e.message, 'analytics');
		}
		loading = false;
	}

	async function saveTs() {
		if (!editorContent.trim()) return;
		try {
			await api.saveTz(editorContent);
			addLog($t('nav.analytics') + ': TS saved');
			showEditor = false;
			await load();
		} catch (e) {
			error = e.message;
			addError(e.message, 'analyticsSave');
		}
	}

	function openEditor() {
		editorContent = data?.tz_content || '';
		showEditor = true;
	}

	function triggerUpload() {
		fileInput?.click();
	}

	async function handleFileUpload(event) {
		const file = event.target?.files?.[0];
		if (!file) return;

		uploading = true;
		error = '';
		try {
			const result = await api.uploadTz(file);
			addLog(`${$t('nav.analytics')}: ${result.message}`);
			await load();
		} catch (e) {
			error = e.message;
			addError(e.message, 'analyticsUpload');
		}
		uploading = false;
		if (fileInput) fileInput.value = '';
	}

	async function runAnalytics() {
		running = true;
		error = '';
		addLog($t('nav.analytics') + ': Running analytics...');
		try {
			const result = await api.runAnalytics();
			addLog($t('nav.analytics') + ': ' + result.message);
			invalidate('status');
			status.set(await api.getStatus());
			await load();
		} catch (e) {
			error = e.message;
			addError(e.message, 'analyticsRun');
		}
		running = false;
	}

	async function cleanTs() {
		cleaning = true;
		error = '';
		addLog($t('nav.analytics') + ': Cleaning TS via LLM...');
		try {
			const result = await api.cleanTs();
			addLog($t('nav.analytics') + ': ' + result.message);
			await load();
		} catch (e) {
			error = e.message;
			addError(e.message, 'analyticsClean');
		}
		cleaning = false;
	}

	async function clearAll() {
		if (!confirm('Clear TS and analytics report?')) return;
		try {
			await api.clearAnalytics();
			addLog($t('nav.analytics') + ': Data cleared');
			invalidate('status');
			status.set(await api.getStatus());
			await load();
		} catch (e) {
			error = e.message;
			addError(e.message, 'analyticsClear');
		}
	}

	// ── Parse requirements from report ──

	/** @type {{ id: string, title: string, content: string }[]} */
	let requirements = $derived.by(() => {
		if (!data?.report_content) return [];
		const report = data.report_content;
		const reqs = [];

		// Split by ## headers to get individual requirements/sections
		const sections = report.split(/^## /m).filter(s => s.trim());

		for (let i = 0; i < sections.length; i++) {
			const section = sections[i];
			const lines = section.split('\n');
			const title = lines[0]?.trim() || `Section ${i + 1}`;
			const content = lines.slice(1).join('\n').trim();

			// Extract ID from title (e.g. "1. Complexity" → "FR-001")
			const idMatch = title.match(/^(\d+)/);
			const id = idMatch ? `FR-${idMatch[1].padStart(3, '0')}` : `FR-${String(i + 1).padStart(3, '0')}`;

			reqs.push({ id, title, content });
		}
		return reqs;
	});
</script>

<div class="main-header">
	<h2><BarChart3 size={24} /> {$t('nav.analytics')}</h2>
	<p>Анализ технического задания: сложность, риски, зависимости, оценка усилий</p>
</div>

{#if error}
	<div class="alert alert-warn"><AlertTriangle size={14} /> {error}</div>
{/if}

{#if loading}
	<div class="loading-text"><Loader2 size={14} class="spin" /> {$t('app.loading')}</div>
{:else}
	<!-- ══ TS INPUT (Top) ══ -->
	<div class="section">
		<h3><FileText size={18} /> Technical Specification</h3>

		{#if !data?.has_tz}
			<div class="alert alert-info">
				<AlertTriangle size={14} />
				Загрузите TS (docx/md) или вставьте текст вручную
			</div>
		{/if}

		<div class="btn-group">
			<button class="btn" onclick={triggerUpload} disabled={uploading}>
				{#if uploading}
					<Loader2 size={14} class="spin" />
				{:else}
					<Upload size={14} />
				{/if}
				Загрузить файл (.docx / .md)
			</button>

			<button class="btn" onclick={openEditor}>
				<Pencil size={14} />
				{data?.has_tz ? 'Редактировать TS' : 'Ввести вручную'}
			</button>

			{#if data?.has_tz}
				<button class="btn" onclick={cleanTs} disabled={cleaning}>
					{#if cleaning}
						<Loader2 size={14} class="spin" />
					{:else}
						<Sparkles size={14} />
					{/if}
					Почистить LLM
				</button>
			{/if}

			{#if data?.has_tz || data?.has_report}
				<button class="btn btn-ghost" onclick={clearAll}>
					<Trash2 size={14} /> Очистить
				</button>
			{/if}
		</div>

		<!-- Hidden file input -->
		<input
			bind:this={fileInput}
			type="file"
			accept=".docx,.md,.txt,.markdown"
			style="display: none;"
			onchange={handleFileUpload}
		/>

		{#if data?.has_tz && !showEditor}
			<div class="card ts-card">
				<MarkdownContent content={data.tz_content} />
			</div>
		{/if}

		{#if showEditor}
			<div class="editor-panel">
				<textarea
					class="ts-editor"
					bind:value={editorContent}
					placeholder="Вставьте текст технического задания..."
					rows="15"
				></textarea>
				<div class="btn-group">
					<button class="btn btn-primary" onclick={saveTs} disabled={!editorContent.trim()}>
						<CheckCircle size={14} /> Сохранить TS
					</button>
					<button class="btn" onclick={() => showEditor = false}>Отмена</button>
				</div>
			</div>
		{/if}
	</div>

	<!-- ══ SEPARATOR + RUN BUTTON ══ -->
	<div class="run-section">
		<div class="separator"></div>
		<button
			class="btn btn-run"
			onclick={runAnalytics}
			disabled={running || !data?.has_tz}
		>
			{#if running}
				<Loader2 size={18} class="spin" /> Анализ...
			{:else}
				<Play size={18} /> Запустить аналитику
			{/if}
		</button>
		<div class="separator"></div>
	</div>

	<!-- ══ OUTPUT: Formal Requirements (Bottom) ══ -->
	<div class="section">
		<h3><ListChecks size={18} /> Формальные требования</h3>

		{#if !data?.has_report}
			<div class="card empty">
				<p>Нет результатов аналитики</p>
				<p class="hint">Загрузите TS и запустите аналитику</p>
			</div>
		{:else if selectedReq}
			<!-- Detail view -->
			<div>
				<button class="back-btn" onclick={() => selectedReq = null}>
					<ChevronLeft size={14} /> К списку требований
				</button>
			</div>

			<div class="detail-header">
				<span class="req-id">{selectedReq.id}</span>
				<h3>{selectedReq.title}</h3>
			</div>

			<div class="card">
				<MarkdownContent content={selectedReq.content} />
			</div>
		{:else}
			<!-- List view (table like ADR) -->
			{#if $status?.analytics_done}
				<div class="alert alert-success">
					<CheckCircle size={14} /> Аналитика завершена
				</div>
			{/if}

			<div class="req-table-wrap">
				<table class="req-table">
					<thead>
						<tr>
							<th class="col-id">ID</th>
							<th class="col-title">Раздел</th>
							<th class="col-preview">Фрагмент</th>
						</tr>
					</thead>
					<tbody>
						{#each requirements as req}
							<tr class="req-row" onclick={() => selectedReq = req}>
								<td class="col-id">{req.id}</td>
								<td class="col-title">{req.title}</td>
								<td class="col-preview">{req.content.substring(0, 80)}...</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}
	</div>
{/if}

<style>
	.main-header {
		margin-bottom: 1.5rem;
	}

	.main-header h2 {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		margin: 0 0 0.25rem 0;
	}

	.main-header p {
		color: var(--dm);
		margin: 0;
	}

	.section {
		margin-bottom: 2rem;
	}

	.section h3 {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		margin: 0 0 1rem 0;
	}

	.btn-group {
		display: flex;
		gap: 0.5rem;
		flex-wrap: wrap;
		margin-bottom: 1rem;
	}

	.card {
		background: var(--bg2);
		border-radius: var(--r);
		padding: 1.5rem;
		margin-top: 1rem;
	}

	.card.empty {
		text-align: center;
		padding: 2rem 1.25rem;
		color: var(--dm);
	}

	.card.empty p { margin: 0.25rem 0; }
	.card.empty .hint { font-size: 0.8125rem; }

	.card-header {
		font-weight: 600;
		margin-bottom: 1rem;
		padding-bottom: 0.5rem;
		border-bottom: 1px solid var(--bd);
		display: flex;
		align-items: center;
		justify-content: space-between;
	}

	.btn-sm {
		display: inline-flex;
		align-items: center;
		gap: 0.25rem;
		padding: 0.25rem 0.5rem;
		font-size: 0.75rem;
	}

	/* ── TS Editor ── */
	.editor-panel {
		margin-top: 1rem;
	}

	.ts-editor {
		width: 100%;
		min-height: 300px;
		padding: 1rem;
		border: 1px solid var(--bd);
		border-radius: var(--r);
		background: var(--bg);
		color: var(--tx);
		font-family: var(--font-mono);
		font-size: 0.875rem;
		line-height: 1.5;
		resize: vertical;
	}

	.ts-editor:focus {
		outline: none;
		border-color: var(--ac);
	}

	.ts-card {
		max-height: 300px;
		overflow-y: auto;
	}

	/* ── Run Section (separator + button) ── */
	.run-section {
		display: flex;
		align-items: center;
		gap: 1rem;
		margin: 1.5rem 0;
	}

	.separator {
		flex: 1;
		height: 1px;
		background: var(--bd);
	}

	.btn-run {
		display: inline-flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.625rem 1.25rem;
		font-size: 0.9375rem;
		font-weight: 600;
		border: none;
		border-radius: var(--r);
		background: var(--ac);
		color: white;
		cursor: pointer;
		white-space: nowrap;
		transition: opacity .15s;
	}

	.btn-run:hover:not(:disabled) {
		opacity: 0.9;
	}

	.btn-run:disabled {
		opacity: 0.5;
		cursor: default;
	}

	/* ── Requirements Table (like ADR) ── */
	.req-table-wrap {
		margin-top: 0.75rem;
		border: 0.0625rem solid var(--bd);
		border-radius: var(--r);
		overflow: hidden;
	}

	.req-table {
		width: 100%;
		border-collapse: collapse;
		font-size: 0.875rem;
	}

	.req-table thead {
		background: var(--sf);
	}

	.req-table th {
		padding: 0.5rem 0.75rem;
		text-align: left;
		color: var(--dm);
		font-weight: 600;
		font-size: 0.75rem;
		text-transform: uppercase;
		letter-spacing: .03em;
		border-bottom: 0.0625rem solid var(--bd);
	}

	.req-table td {
		padding: 0.625rem 0.75rem;
		border-bottom: 0.0625rem solid var(--bd);
	}

	.req-table tr:last-child td {
		border-bottom: none;
	}

	.req-row {
		cursor: pointer;
		transition: background .1s;
	}

	.req-row:hover {
		background: var(--bg2);
	}

	.col-id {
		width: 5rem;
		font-family: var(--font-ui);
		color: var(--dm);
		font-weight: 600;
	}

	.col-preview {
		color: var(--dm);
		font-size: 0.8125rem;
		max-width: 20rem;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

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
		margin-bottom: 0.75rem;
	}

	.detail-header h3 {
		margin: 0;
		font-size: 1.125rem;
		color: var(--tx-bright);
	}

	.req-id {
		display: inline-block;
		padding: 0.125rem 0.5rem;
		border-radius: 0.375rem;
		background: rgba(59, 130, 246, 0.15);
		color: var(--ac);
		font-size: 0.75rem;
		font-weight: 600;
		font-family: var(--font-ui);
		white-space: nowrap;
	}

	/* ── Shared ── */
	.alert-info {
		background: rgba(59, 130, 246, 0.1);
		border: 1px solid rgba(59, 130, 246, 0.3);
		color: var(--tx);
	}

	.alert-success {
		background: rgba(34, 197, 94, 0.1);
		border: 1px solid rgba(34, 197, 94, 0.3);
	}

	.btn-ghost {
		background: transparent;
		border: 1px solid var(--bd);
	}
</style>