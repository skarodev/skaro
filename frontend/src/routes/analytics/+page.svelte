<script>
	import { onMount } from 'svelte';
	import { t } from '$lib/i18n/index.js';
	import { api } from '$lib/api/client.js';
	import { addLog, addError } from '$lib/stores/logStore.js';
	import { status } from '$lib/stores/statusStore.js';
	import { invalidate } from '$lib/api/cache.js';
	import {
		BarChart3, Upload, FileText, Loader2, Trash2, AlertTriangle,
		CheckCircle, Pencil, ChevronLeft, ChevronRight, ListChecks, Sparkles,
		ClipboardCheck, Eye, MessageSquare
	} from 'lucide-svelte';
	import MarkdownContent from '$lib/ui/MarkdownContent.svelte';
	import MdEditor from '$lib/ui/md-editor/MdEditor.svelte';

	let data = $state(null);
	let loading = $state(true);
	let error = $state('');
	let running = $state(false);
	let uploading = $state(false);
	let cleaning = $state(false);
	let generatingReqs = $state(false);
	let generatingFromSel = $state(false);
	let reviewing = $state(false);
	let reviewingReqs = $state(false);
	let clearingReqs = $state(false);

	// TS editor state
	let tsEditorContent = $state('');
	/** @type {HTMLInputElement | null} */
	let fileInput = $state(null);

	// Output tabs
	let activeTab = $state('requirements');

	// Requirements detail
	/** @type {any | null} */
	let selectedReq = $state(null);
	let changingStatus = $state(null);

	// MdEditor state (shared for TS and requirements)
	let showEditor = $state(false);
	let editorContent = $state('');
	let editorTarget = $state(''); // 'ts' or req id

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

	// ── TS Operations ──

	function openTsEditor() {
		editorTarget = 'ts';
		editorContent = data?.tz_content || '';
		showEditor = true;
	}

	async function saveEditor(content) {
		try {
			if (editorTarget === 'ts') {
				await api.saveTz(content);
				addLog($t('nav.analytics') + ': TS saved');
			} else {
				await api.saveRequirementContent(editorTarget, content);
				addLog($t('nav.analytics') + ': Requirement saved');
			}
			await load();
			showEditor = false;
		} catch (e) {
			error = e.message;
			throw e;
		}
	}

	function triggerUpload() { fileInput?.click(); }

	async function handleFileUpload(event) {
		const file = event.target?.files?.[0];
		if (!file) return;
		uploading = true;
		error = '';
		try {
			const result = await api.uploadTz(file);
			addLog(`${$t('nav.analytics')}: ${result.message}`);
			await load();
		} catch (e) { error = e.message; }
		uploading = false;
		if (fileInput) fileInput.value = '';
	}

	async function cleanTs() {
		cleaning = true;
		error = '';
		addLog($t('nav.analytics') + ': Cleaning TS via LLM...');
		try {
			const result = await api.cleanTs();
			addLog($t('nav.analytics') + ': ' + result.message);
			await load();
		} catch (e) { error = e.message; }
		cleaning = false;
	}

	// ── Requirements Operations ──

	async function generateRequirements() {
		generatingReqs = true;
		error = '';
		addLog($t('nav.analytics') + ': Generating requirements...');
		try {
			const result = await api.generateRequirements();
			addLog($t('nav.analytics') + ': ' + result.message);
			invalidate('status');
			status.set(await api.getStatus());
			await load();
			activeTab = 'requirements';
		} catch (e) { error = e.message; }
		generatingReqs = false;
	}

	async function generateFromSelection() {
		const selection = window.getSelection()?.toString()?.trim();
		if (!selection) {
			error = 'Выделите текст в TS перед нажатием этой кнопки';
			return;
		}
		generatingFromSel = true;
		error = '';
		addLog($t('nav.analytics') + ': Generating requirement from selection...');
		try {
			const result = await api.generateRequirement(selection);
			addLog($t('nav.analytics') + ': ' + result.message);
			await load();
			activeTab = 'requirements';
		} catch (e) { error = e.message; }
		generatingFromSel = false;
	}

	async function changeReqStatus(req, newStatus) {
		changingStatus = req.id;
		try {
			const result = await api.updateRequirementStatus(req.id, newStatus);
			if (result.success) {
				addLog(`${$t('nav.analytics')}: ${req.id} → ${newStatus}`);
				await load();
				if (selectedReq?.id === req.id) {
					selectedReq = data?.requirements?.find(r => r.id === req.id) || null;
				}
			}
		} catch (e) { error = e.message; }
		changingStatus = null;
	}

	// Navigation between requirements
	let currentReqIndex = $derived(
		selectedReq ? filteredRequirements.findIndex(r => r.id === selectedReq.id) : -1
	);
	let hasPrevReq = $derived(currentReqIndex > 0);
	let hasNextReq = $derived(currentReqIndex >= 0 && currentReqIndex < filteredRequirements.length - 1);

	function goToPrevReq() {
		if (hasPrevReq) selectedReq = filteredRequirements[currentReqIndex - 1];
	}
	function goToNextReq() {
		if (hasNextReq) selectedReq = filteredRequirements[currentReqIndex + 1];
	}

	function openReqEditor(req) {
		editorTarget = req.id;
		editorContent = req.content;
		showEditor = true;
	}

	// ── Review ──

	async function reviewTs() {
		reviewing = true;
		error = '';
		addLog($t('nav.analytics') + ': Reviewing TS...');
		try {
			const result = await api.reviewTs();
			addLog($t('nav.analytics') + ': ' + result.message);
			await load();
			activeTab = 'review';
		} catch (e) { error = e.message; }
		reviewing = false;
	}

	async function reviewRequirements() {
		reviewingReqs = true;
		error = '';
		addLog($t('nav.analytics') + ': Reviewing requirements...');
		try {
			const result = await api.reviewRequirements();
			addLog($t('nav.analytics') + ': ' + result.message);
			await load();
			activeTab = 'req-review';
		} catch (e) { error = e.message; }
		reviewingReqs = false;
	}

	// ── Requirements Delete ──

	async function deleteRequirement(req) {
		if (!confirm(`Удалить требование ${req.id}?`)) return;
		try {
			const result = await api.deleteRequirement(req.id);
			addLog($t('nav.analytics') + ': ' + result.message);
			await load();
		} catch (e) { error = e.message; }
	}

	async function clearRequirements() {
		if (!confirm('Удалить ВСЕ требования?')) return;
		clearingReqs = true;
		error = '';
		try {
			await api.clearRequirements();
			addLog($t('nav.analytics') + ': All requirements cleared');
			await load();
		} catch (e) { error = e.message; }
		clearingReqs = false;
	}

	// ── Clear ──

	async function clearAll() {
		if (!confirm('Clear TS, requirements, and review?')) return;
		try {
			await api.clearAnalytics();
			addLog($t('nav.analytics') + ': Data cleared');
			invalidate('status');
			status.set(await api.getStatus());
			await load();
		} catch (e) { error = e.message; }
	}

	// ── Helpers ──

	let requirements = $derived(data?.requirements || []);
	let typeCounts = $derived(data?.type_counts || {});
	let hasReview = $derived(data?.has_review || false);
	let hasReqReview = $derived(!!data?.req_review_content);

	const REQ_TYPES = [
		{ code: 'all', label: 'Все', color: 'var(--tx-bright)' },
		{ code: 'FR', label: 'Функциональные', color: 'var(--ac)' },
		{ code: 'NFR', label: 'Нефункциональные', color: 'var(--yl)' },
		{ code: 'IR', label: 'Интеграционные', color: '#a78bfa' },
		{ code: 'DR', label: 'Данные', color: '#34d399' },
		{ code: 'BR', label: 'Бизнес-правила', color: '#f97316' },
		{ code: 'CR', label: 'Соответствие', color: '#ec4899' },
		{ code: 'UR', label: 'UI/UX', color: '#06b6d4' },
	];

	let selectedType = $state('all');
	let filteredRequirements = $derived(
		selectedType === 'all' ? requirements : requirements.filter(r => r.type === selectedType)
	);

	const STATUSES = ['proposed', 'accepted', 'deprecated', 'superseded'];
	const STATUS_LABELS = {
		proposed: 'Предложено',
		accepted: 'Принято',
		deprecated: 'Устарело',
		superseded: 'Заменено',
	};

	function statusBadgeClass(s) {
		if (s === 'accepted') return 'badge-accepted';
		if (s === 'deprecated') return 'badge-deprecated';
		if (s === 'superseded') return 'badge-superseded';
		return 'badge-proposed';
	}
</script>

<div class="main-header">
	<h2><BarChart3 size={24} /> {$t('nav.analytics')}</h2>
	<p>Анализ технического задания: требования, ревью, оценка</p>
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
				{#if uploading}<Loader2 size={14} class="spin" />{:else}<Upload size={14} />{/if}
				Загрузить (.docx / .md)
			</button>

			<button class="btn" onclick={openTsEditor}>
				<Pencil size={14} />
				{data?.has_tz ? 'Редактировать' : 'Ввести вручную'}
			</button>

			{#if data?.has_tz}
				<button class="btn" onclick={cleanTs} disabled={cleaning}>
					{#if cleaning}<Loader2 size={14} class="spin" />{:else}<Sparkles size={14} />{/if}
					Почистить LLM
				</button>
			{/if}

			{#if data?.has_tz || data?.has_report || requirements.length > 0}
				<button class="btn btn-ghost" onclick={clearAll}>
					<Trash2 size={14} /> Очистить
				</button>
			{/if}
		</div>

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
	</div>

	<!-- ══ SEPARATOR + ACTION BUTTONS ══ -->
	<div class="run-section">
		<div class="separator"></div>
		<div class="run-buttons">
			<button class="btn btn-action" onclick={generateRequirements}
				disabled={generatingReqs || !data?.has_tz}>
				{#if generatingReqs}<Loader2 size={16} class="spin" />{:else}<ListChecks size={16} />{/if}
				Сгенерировать требования
			</button>

			<button class="btn btn-action" onclick={generateFromSelection}
				disabled={generatingFromSel || !data?.has_tz}>
				{#if generatingFromSel}<Loader2 size={16} class="spin" />{:else}<MessageSquare size={16} />{/if}
				Из выделенного текста
			</button>

			<button class="btn btn-action" onclick={reviewTs}
				disabled={reviewing || !data?.has_tz}>
				{#if reviewing}<Loader2 size={16} class="spin" />{:else}<Eye size={16} />{/if}
				Ревью ТЗ
			</button>

			{#if requirements.length > 0}
				<button class="btn btn-action" onclick={reviewRequirements}
					disabled={reviewingReqs}>
					{#if reviewingReqs}<Loader2 size={16} class="spin" />{:else}<Eye size={16} />{/if}
					Ревью требований
				</button>
				<button class="btn btn-action btn-action-danger" onclick={clearRequirements}
					disabled={clearingReqs}>
					{#if clearingReqs}<Loader2 size={16} class="spin" />{:else}<Trash2 size={16} />{/if}
					Очистить требования
				</button>
			{/if}
		</div>
		<div class="separator"></div>
	</div>

	<!-- ══ OUTPUT: Tabs (Bottom) ══ -->
	<div class="section">
		<div class="tabs">
			<button class="tab" class:active={activeTab === 'requirements'}
				onclick={() => { activeTab = 'requirements'; selectedReq = null; }}>
				<ClipboardCheck size={16} />
				Требования
				{#if requirements.length > 0}
					<span class="tab-badge">{requirements.length}</span>
				{/if}
			</button>
			<button class="tab" class:active={activeTab === 'review'}
				onclick={() => activeTab = 'review'}>
				<Eye size={16} />
				Ревью ТЗ
				{#if hasReview}
					<span class="tab-badge ok">✓</span>
				{/if}
			</button>
			<button class="tab" class:active={activeTab === 'req-review'}
				onclick={() => activeTab = 'req-review'}>
				<Eye size={16} />
				Ревью требований
				{#if hasReqReview}
					<span class="tab-badge ok">✓</span>
				{/if}
			</button>
		</div>

		<!-- ══ Requirements Tab ══ -->
		{#if activeTab === 'requirements'}
			{#if requirements.length === 0}
				<div class="card empty">
					<p>Нет требований</p>
					<p class="hint">Загрузите TS и нажмите «Сгенерировать требования»</p>
				</div>
			{:else if selectedReq}
				<!-- Detail View -->
				<div>
					<button class="back-btn" onclick={() => selectedReq = null}>
						<ChevronLeft size={14} /> К списку требований
					</button>
				</div>

				<div class="detail-header">
					<span class="req-id">{selectedReq.id}</span>
					<span class="badge {statusBadgeClass(selectedReq.status)}">
						{STATUS_LABELS[selectedReq.status] || selectedReq.status}
					</span>
					<h3>{selectedReq.title}</h3>
				</div>

				<div class="status-actions">
					<button class="btn-status" onclick={goToPrevReq} disabled={!hasPrevReq}>
						<ChevronLeft size={14} /> Предыдущее
					</button>
					<span class="req-counter">{currentReqIndex + 1} / {filteredRequirements.length}</span>
					<button class="btn-status" onclick={goToNextReq} disabled={!hasNextReq}>
						Следующее <ChevronRight size={14} />
					</button>
					<span class="status-separator"></span>
					{#each STATUSES.filter(s => s !== selectedReq.status) as s}
						<button class="btn-status"
							disabled={changingStatus === selectedReq.id}
							onclick={() => changeReqStatus(selectedReq, s)}>
							→ {STATUS_LABELS[s]}
						</button>
					{/each}
					<button class="btn-status" onclick={() => openReqEditor(selectedReq)}>
						<Pencil size={12} /> Редактировать
					</button>
				</div>

				<div class="card">
					<MarkdownContent content={selectedReq.content} />
				</div>
			{:else}
				<!-- Type filter tabs -->
				<div class="type-tabs">
					{#each REQ_TYPES as rt}
						{@const count = rt.code === 'all' ? requirements.length : (typeCounts[rt.code] || 0)}
						{#if count > 0 || rt.code === 'all'}
							<button
								class="type-tab"
								class:active={selectedType === rt.code}
								style="--tab-color: {rt.color}"
								onclick={() => selectedType = rt.code}
							>
								{rt.label}
								<span class="type-count">{count}</span>
							</button>
						{/if}
					{/each}
				</div>

				<!-- List View (table like ADR) -->
				<div class="req-table-wrap">
					<table class="req-table">
						<thead>
							<tr>
								<th class="col-id">ID</th>
								<th class="col-type">Тип</th>
								<th class="col-title">Требование</th>
								<th class="col-status">Статус</th>
								<th class="col-date">Дата</th>
								<th class="col-actions"></th>
							</tr>
						</thead>
						<tbody>
							{#each filteredRequirements as req}
								<tr class="req-row" onclick={() => selectedReq = req}>
									<td class="col-id">{req.id}</td>
									<td class="col-type">
										<span class="type-badge" style="background: {REQ_TYPES.find(t => t.code === req.type)?.color || 'var(--dm)'}20; color: {REQ_TYPES.find(t => t.code === req.type)?.color || 'var(--dm)'}">
											{req.type || 'FR'}
										</span>
									</td>
									<td class="col-title">{req.title}</td>
									<td class="col-status">
										<span class="badge {statusBadgeClass(req.status)}">
											{STATUS_LABELS[req.status] || req.status}
										</span>
									</td>
									<td class="col-date">{req.date || '—'}</td>
									<td class="col-actions">
										<button class="btn-icon" title="Удалить"
											onclick={(e) => { e.stopPropagation(); deleteRequirement(req); }}>
											<Trash2 size={14} />
										</button>
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			{/if}
		{/if}

		<!-- ══ Review TS Tab ══ -->
		{#if activeTab === 'review'}
			{#if !hasReview}
				<div class="card empty">
					<p>Нет ревью</p>
					<p class="hint">Нажмите «Ревью ТЗ» для анализа</p>
				</div>
			{:else}
				<div class="card">
					<MarkdownContent content={data.review_content} />
				</div>
			{/if}
		{/if}

		<!-- ══ Requirements Review Tab ══ -->
		{#if activeTab === 'req-review'}
			{#if !hasReqReview}
				<div class="card empty">
					<p>Нет ревью требований</p>
					<p class="hint">Нажмите «Ревью требований» для анализа</p>
				</div>
			{:else}
				<div class="card">
					<MarkdownContent content={data.req_review_content} />
				</div>
			{/if}
		{/if}
	</div>
{/if}

<!-- ══ MdEditor (shared for TS and requirements) ══ -->
{#if showEditor}
	<MdEditor
		content={editorContent}
		onSave={saveEditor}
		onClose={() => showEditor = false}
	/>
{/if}

<style>
	.main-header { margin-bottom: 1.5rem; }
	.main-header h2 {
		display: flex; align-items: center; gap: 0.5rem; margin: 0 0 0.25rem 0;
	}
	.main-header p { color: var(--dm); margin: 0; }
	.section { margin-bottom: 2rem; }
	.section h3 {
		display: flex; align-items: center; gap: 0.5rem; margin: 0 0 1rem 0;
	}
	.btn-group {
		display: flex; gap: 0.5rem; flex-wrap: wrap; margin-bottom: 1rem;
	}
	.card {
		background: var(--bg2); border-radius: var(--r); padding: 1.5rem; margin-top: 1rem;
	}
	.card.empty { text-align: center; padding: 2rem 1.25rem; color: var(--dm); }
	.card.empty p { margin: 0.25rem 0; }
	.card.empty .hint { font-size: 0.8125rem; }
	.ts-card { max-height: 250px; overflow-y: auto; }

	/* ── Run Section ── */
	.run-section { display: flex; align-items: center; gap: 1rem; margin: 1.5rem 0; }
	.separator { flex: 1; height: 1px; background: var(--bd); }
	.run-buttons { display: flex; gap: 0.5rem; flex-wrap: wrap; justify-content: center; }
	.btn-action {
		display: inline-flex; align-items: center; gap: 0.375rem;
		padding: 0.5rem 0.875rem; font-size: 0.8125rem; font-weight: 500;
		border: 1px solid var(--bd); border-radius: var(--r);
		background: var(--bg2); color: var(--tx); cursor: pointer; white-space: nowrap;
		transition: background .15s, border-color .15s;
	}
	.btn-action:hover:not(:disabled) { background: var(--sf); border-color: var(--ac); }
	.btn-action:disabled { opacity: 0.5; cursor: default; }

	/* ── Tabs ── */
	.tabs {
		display: flex; gap: 0.25rem; border-bottom: 1px solid var(--bd); margin-bottom: 1rem;
	}
	.tab {
		display: inline-flex; align-items: center; gap: 0.375rem;
		padding: 0.5rem 0.75rem; background: none; border: none;
		border-bottom: 2px solid transparent; color: var(--dm);
		cursor: pointer; font-size: 0.875rem; font-family: inherit;
		transition: color .15s, border-color .15s;
	}
	.tab:hover { color: var(--tx); }
	.tab.active { color: var(--tx-bright); border-bottom-color: var(--ac); }
	.tab-badge {
		display: inline-block; padding: 0 0.375rem; border-radius: 0.5rem;
		background: var(--sf); color: var(--dm); font-size: 0.75rem; line-height: 1.25rem;
	}
	.tab-badge.ok { color: var(--gn-bright); }

	/* ── Requirements Table ── */
	.req-table-wrap {
		margin-top: 0.75rem; border: 0.0625rem solid var(--bd);
		border-radius: var(--r); overflow: hidden;
	}
	.req-table { width: 100%; border-collapse: collapse; font-size: 0.875rem; }
	.req-table thead { background: var(--sf); }
	.req-table th {
		padding: 0.5rem 0.75rem; text-align: left; color: var(--dm);
		font-weight: 600; font-size: 0.75rem; text-transform: uppercase;
		letter-spacing: .03em; border-bottom: 0.0625rem solid var(--bd);
	}
	.req-table td { padding: 0.625rem 0.75rem; border-bottom: 0.0625rem solid var(--bd); }
	.req-table tr:last-child td { border-bottom: none; }
	.req-row { cursor: pointer; transition: background .1s; }
	.req-row:hover { background: var(--bg2); }
	.col-id { width: 5rem; font-family: var(--font-ui); color: var(--dm); font-weight: 600; }
	.col-status { width: 7rem; }
	.col-date { width: 6.875rem; font-family: var(--font-ui); color: var(--dm); font-size: 0.8125rem; }
	.col-actions { width: 2.5rem; text-align: center; }
	.col-type { width: 6rem; }

	/* ── Type tabs ── */
	.type-tabs {
		display: flex; gap: 0.25rem; flex-wrap: wrap;
		margin: 0.75rem 0; padding-bottom: 0.5rem;
		border-bottom: 1px solid var(--bd);
	}
	.type-tab {
		display: inline-flex; align-items: center; gap: 0.25rem;
		padding: 0.25rem 0.625rem; background: none; border: 1px solid transparent;
		border-radius: var(--r); color: var(--dm); cursor: pointer;
		font-size: 0.8125rem; font-family: inherit;
		transition: color .15s, border-color .15s, background .15s;
	}
	.type-tab:hover { color: var(--tab-color); background: color-mix(in srgb, var(--tab-color) 8%, transparent); }
	.type-tab.active {
		color: var(--tab-color); border-color: var(--tab-color);
		background: color-mix(in srgb, var(--tab-color) 12%, transparent);
	}
	.type-count {
		display: inline-block; padding: 0 0.25rem; border-radius: 0.375rem;
		background: var(--sf); font-size: 0.6875rem; line-height: 1.125rem;
	}

	.type-badge {
		display: inline-block; padding: 0.0625rem 0.375rem; border-radius: 0.25rem;
		font-size: 0.6875rem; font-weight: 600; font-family: var(--font-ui);
		white-space: nowrap;
	}

	.btn-icon {
		display: inline-flex; align-items: center; justify-content: center;
		width: 1.5rem; height: 1.5rem; border: none; border-radius: var(--r);
		background: none; color: var(--dm); cursor: pointer;
		transition: color .15s, background .15s;
	}
	.btn-icon:hover { color: var(--rd); background: rgba(180, 80, 80, .1); }

	.btn-action-danger:hover:not(:disabled) { border-color: var(--rd); background: rgba(180, 80, 80, .1); color: var(--rd); }

	/* ── Status badges (like ADR) ── */
	.badge {
		display: inline-block; padding: 0.125rem 0.5rem; border-radius: 0.625rem;
		font-size: 0.75rem; font-weight: 500; line-height: 1.125rem; white-space: nowrap;
	}
	.badge-proposed { background: rgba(187, 181, 41, .12); color: var(--yl); }
	.badge-accepted { background: rgba(106, 135, 89, .15); color: var(--gn-bright); }
	.badge-deprecated { background: rgba(180, 80, 80, .12); color: var(--rd); }
	.badge-superseded { background: rgba(130, 130, 160, .12); color: var(--dm); }

	/* ── Detail view ── */
	.back-btn {
		display: inline-flex; align-items: center; gap: 0.25rem;
		background: none; border: none; color: var(--ac); cursor: pointer;
		padding: 0.25rem 0; font-size: 0.875rem; font-family: inherit; margin-bottom: 0.5rem;
	}
	.back-btn:hover { text-decoration: underline; }
	.detail-header {
		display: flex; align-items: center; gap: 0.75rem; margin-bottom: 0.5rem;
	}
	.detail-header h3 { margin: 0; font-size: 1.125rem; color: var(--tx-bright); }
	.req-id {
		display: inline-block; padding: 0.125rem 0.5rem; border-radius: 0.375rem;
		background: rgba(59, 130, 246, 0.15); color: var(--ac);
		font-size: 0.75rem; font-weight: 600; font-family: var(--font-ui); white-space: nowrap;
	}

	.status-actions {
		display: flex; gap: 0.375rem; margin-bottom: 0.75rem; flex-wrap: wrap; align-items: center;
	}
	.status-separator {
		width: 1px; height: 1.25rem; background: var(--bd); margin: 0 0.25rem;
	}
	.req-counter {
		font-size: 0.8125rem; color: var(--dm); font-family: var(--font-ui);
		white-space: nowrap; padding: 0 0.25rem;
	}
	.btn-status {
		display: inline-flex; align-items: center; gap: 0.25rem;
		padding: 0.25rem 0.625rem; border: 0.0625rem solid var(--bd);
		border-radius: var(--r); background: var(--bg2); color: var(--tx);
		cursor: pointer; font-size: 0.75rem; font-family: inherit;
		transition: background .1s, border-color .1s;
	}
	.btn-status:hover { background: var(--sf); border-color: var(--ac); }
	.btn-status:disabled { opacity: .5; cursor: default; }

	/* ── Shared ── */
	.alert-info {
		background: rgba(59, 130, 246, 0.1); border: 1px solid rgba(59, 130, 246, 0.3); color: var(--tx);
	}
	.btn-ghost { background: transparent; border: 1px solid var(--bd); }
</style>