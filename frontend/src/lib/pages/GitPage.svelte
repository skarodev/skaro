<script>
	import { onMount } from 'svelte';
	import { t } from '$lib/i18n/index.js';
	import { api } from '$lib/api/client.js';
	import { onWsEvent } from '$lib/api/client.js';
	import { addLog, addError } from '$lib/stores/logStore.js';
	import {
		GitBranch, GitCommit, Upload, RefreshCw, ChevronDown, ChevronRight,
		Plus, Minus, FileQuestion, Check, X, Loader2, AlertTriangle, Eye
	} from 'lucide-svelte';

	let data = $state(null);
	let error = $state('');
	let loading = $state(true);
	let committing = $state(false);
	let pushing = $state(false);
	let staging = $state(false);

	// Commit form
	let commitMessage = $state('');
	let pushAfterCommit = $state(false);

	// Branch
	let showBranchInput = $state(false);
	let newBranchName = $state('');
	let switchingBranch = $state(false);

	// Diff viewer
	let diffFile = $state(null);
	let diffContent = $state('');
	let loadingDiff = $state(false);

	// Selection for staging
	let selectedFiles = $state(new Set());

	onMount(() => {
		load();
		const unsub = onWsEvent((msg) => {
			if (msg.event?.startsWith('git:') || msg.event?.includes(':applied')) {
				load();
			}
		});
		return unsub;
	});

	async function load() {
		loading = true;
		try {
			data = await api.getGitStatus();
			error = '';
		} catch (e) {
			error = e.message;
			addError(e.message, 'git');
		}
		loading = false;
	}

	// ── Grouping ──
	let stagedFiles = $derived(data?.files?.filter(f => f.status === 'staged') || []);
	let unstagedFiles = $derived(data?.files?.filter(f => f.status !== 'staged') || []);
	let hasStaged = $derived(stagedFiles.length > 0);
	let hasUnstaged = $derived(unstagedFiles.length > 0);

	// ── Selection helpers ──
	function toggleSelect(path) {
		const next = new Set(selectedFiles);
		if (next.has(path)) next.delete(path);
		else next.add(path);
		selectedFiles = next;
	}

	function selectAll(files) {
		const next = new Set(selectedFiles);
		files.forEach(f => next.add(f.path));
		selectedFiles = next;
	}

	function deselectAll(files) {
		const next = new Set(selectedFiles);
		files.forEach(f => next.delete(f.path));
		selectedFiles = next;
	}

	// ── Actions ──
	async function stageSelected() {
		if (selectedFiles.size === 0) return;
		staging = true;
		try {
			const files = [...selectedFiles];
			await api.gitStage(files);
			addLog($t('git.staged_n', { n: files.length }));
			selectedFiles = new Set();
			await load();
		} catch (e) { addError(e.message, 'gitStage'); }
		staging = false;
	}

	async function unstageFiles(files) {
		staging = true;
		try {
			await api.gitUnstage(files);
			addLog($t('git.unstaged'));
			await load();
		} catch (e) { addError(e.message, 'gitUnstage'); }
		staging = false;
	}

	async function stageAll() {
		staging = true;
		try {
			const files = unstagedFiles.map(f => f.path);
			await api.gitStage(files);
			addLog($t('git.staged_all'));
			selectedFiles = new Set();
			await load();
		} catch (e) { addError(e.message, 'gitStage'); }
		staging = false;
	}

	async function unstageAll() {
		staging = true;
		try {
			await api.gitUnstage(stagedFiles.map(f => f.path));
			addLog($t('git.unstaged'));
			await load();
		} catch (e) { addError(e.message, 'gitUnstage'); }
		staging = false;
	}

	async function commit() {
		if (!commitMessage.trim()) return;
		committing = true;
		try {
			const result = await api.gitCommit(commitMessage.trim(), pushAfterCommit);
			addLog(result.message);
			if (result.push_error) {
				addError(`Push failed: ${result.push_error}`, 'gitPush');
			}
			commitMessage = '';
			await load();
		} catch (e) { addError(e.message, 'gitCommit'); }
		committing = false;
	}

	async function push() {
		pushing = true;
		try {
			const result = await api.gitPush();
			addLog(result.message);
		} catch (e) { addError(e.message, 'gitPush'); }
		pushing = false;
	}

	async function showDiff(filepath) {
		if (diffFile === filepath) { diffFile = null; return; }
		diffFile = filepath;
		loadingDiff = true;
		try {
			const result = await api.getGitDiff(filepath);
			diffContent = result.diff || '(no changes)';
		} catch (e) { diffContent = `Error: ${e.message}`; }
		loadingDiff = false;
	}

	async function switchBranch(name) {
		switchingBranch = true;
		try {
			const result = await api.gitCheckout(name, false);
			addLog(result.message);
			showBranchInput = false;
			await load();
		} catch (e) { addError(e.message, 'gitCheckout'); }
		switchingBranch = false;
	}

	async function createBranch() {
		if (!newBranchName.trim()) return;
		switchingBranch = true;
		try {
			const result = await api.gitCheckout(newBranchName.trim(), true);
			addLog(result.message);
			newBranchName = '';
			showBranchInput = false;
			await load();
		} catch (e) { addError(e.message, 'gitCheckout'); }
		switchingBranch = false;
	}

	function changeIcon(change) {
		if (change === 'A') return Plus;
		if (change === 'D') return Minus;
		if (change === 'M') return GitCommit;
		return FileQuestion;
	}

	function changeClass(change) {
		if (change === 'A') return 'change-add';
		if (change === 'D') return 'change-del';
		return 'change-mod';
	}
</script>

<div class="page-with-tabs">
	<div class="main-header">
		<h2><GitBranch size={24} /> {$t('git.title')}</h2>
		<p>{$t('git.subtitle')}</p>
	</div>

	{#if error}
		<div class="alert alert-warn"><AlertTriangle size={14} /> {error}</div>
	{:else if loading && !data}
		<div class="loading-text"><Loader2 size={14} class="spin" /> {$t('app.loading')}</div>
	{:else if data && !data.is_repo}
		<div class="alert alert-warn"><AlertTriangle size={14} /> {$t('git.not_a_repo')}</div>
	{:else if data}

		<!-- ── Branch bar ── -->
		<div class="branch-bar">
			<div class="branch-current">
				<GitBranch size={14} />
				<span class="branch-name">{data.branch}</span>
				<button class="btn btn-sm" onclick={() => showBranchInput = !showBranchInput}>
					<ChevronDown size={12} /> {$t('git.branches')}
				</button>
				<button class="btn btn-sm" onclick={load} title={$t('git.refresh')}>
					<RefreshCw size={12} />
				</button>
			</div>

			{#if showBranchInput}
				<div class="branch-panel">
					<div class="branch-list">
						{#each data.branches as br}
							<button
								class="branch-item"
								class:active={br === data.branch}
								disabled={br === data.branch || switchingBranch}
								onclick={() => switchBranch(br)}
							>
								{br}
								{#if br === data.branch}<Check size={12} />{/if}
							</button>
						{/each}
					</div>
					<div class="branch-create">
						<input
							type="text"
							class="input"
							placeholder={$t('git.new_branch_placeholder')}
							bind:value={newBranchName}
							onkeydown={(e) => e.key === 'Enter' && createBranch()}
						/>
						<button class="btn btn-primary btn-sm" onclick={createBranch} disabled={!newBranchName.trim() || switchingBranch}>
							<Plus size={12} /> {$t('git.create_branch')}
						</button>
					</div>
				</div>
			{/if}
		</div>

		<!-- ── Staged changes ── -->
		<div class="file-section">
			<div class="section-header">
				<h3>{$t('git.staged_changes')} ({stagedFiles.length})</h3>
				{#if hasStaged}
					<button class="btn btn-sm" onclick={unstageAll} disabled={staging}>
						<Minus size={12} /> {$t('git.unstage_all')}
					</button>
				{/if}
			</div>
			{#if hasStaged}
				<div class="file-list">
					{#each stagedFiles as f}
						{@const Icon = changeIcon(f.change)}
						<div class="file-row staged">
							<span class="file-change {changeClass(f.change)}"><Icon size={12} /></span>
							<span class="file-path">{f.path}</span>
							<button class="btn-icon" title={$t('git.view_diff')} onclick={() => showDiff(f.path)}>
								<Eye size={13} />
							</button>
							<button class="btn-icon" title={$t('git.unstage')} onclick={() => unstageFiles([f.path])}>
								<Minus size={13} />
							</button>
						</div>
						{#if diffFile === f.path}
							<div class="diff-inline">
								{#if loadingDiff}
									<Loader2 size={12} class="spin" /> Loading...
								{:else}
									<pre class="diff-pre">{diffContent}</pre>
								{/if}
							</div>
						{/if}
					{/each}
				</div>
			{:else}
				<p class="empty-hint">{$t('git.no_staged')}</p>
			{/if}
		</div>

		<!-- ── Unstaged / untracked ── -->
		<div class="file-section">
			<div class="section-header">
				<h3>{$t('git.changes')} ({unstagedFiles.length})</h3>
				{#if hasUnstaged}
					<button class="btn btn-sm" onclick={() => selectAll(unstagedFiles)}>
						<Check size={12} /> {$t('git.select_all')}
					</button>
					<button class="btn btn-sm" onclick={stageAll} disabled={staging}>
						<Plus size={12} /> {$t('git.stage_all')}
					</button>
				{/if}
			</div>
			{#if hasUnstaged}
				<div class="file-list">
					{#each unstagedFiles as f}
						{@const Icon = changeIcon(f.change)}
						<div class="file-row">
							<label class="file-checkbox">
								<input
									type="checkbox"
									checked={selectedFiles.has(f.path)}
									onchange={() => toggleSelect(f.path)}
								/>
							</label>
							<span class="file-change {changeClass(f.change)}"><Icon size={12} /></span>
							<span class="file-path">{f.path}</span>
							<span class="file-status-badge">{f.status}</span>
							<button class="btn-icon" title={$t('git.view_diff')} onclick={() => showDiff(f.path)}>
								<Eye size={13} />
							</button>
						</div>
						{#if diffFile === f.path}
							<div class="diff-inline">
								{#if loadingDiff}
									<Loader2 size={12} class="spin" /> Loading...
								{:else}
									<pre class="diff-pre">{diffContent}</pre>
								{/if}
							</div>
						{/if}
					{/each}
				</div>
				{#if selectedFiles.size > 0}
					<div class="selection-actions">
						<button class="btn btn-primary btn-sm" onclick={stageSelected} disabled={staging}>
							{#if staging}<Loader2 size={12} class="spin" />{/if}
							<Plus size={12} /> {$t('git.stage_selected', { n: selectedFiles.size })}
						</button>
						<button class="btn btn-sm" onclick={() => deselectAll(unstagedFiles)}>
							<X size={12} /> {$t('git.deselect')}
						</button>
					</div>
				{/if}
			{:else}
				<p class="empty-hint">{$t('git.working_tree_clean')}</p>
			{/if}
		</div>

		<!-- ── Commit box ── -->
		{#if hasStaged}
			<div class="commit-box">
				<h3><GitCommit size={16} /> {$t('git.commit')}</h3>
				<textarea
					class="input commit-input"
					placeholder={$t('git.commit_message_placeholder')}
					bind:value={commitMessage}
					rows="3"
					onkeydown={(e) => { if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') commit(); }}
				></textarea>
				<div class="commit-actions">
					<label class="push-toggle">
						<input type="checkbox" bind:checked={pushAfterCommit} disabled={!data.has_remote} />
						<Upload size={12} />
						{$t('git.push_after_commit')}
						{#if !data.has_remote}
							<span class="hint">({$t('git.no_remote')})</span>
						{/if}
					</label>
					<div class="commit-buttons">
						<button
							class="btn btn-primary"
							onclick={commit}
							disabled={committing || !commitMessage.trim()}
						>
							{#if committing}<Loader2 size={14} class="spin" />{/if}
							<GitCommit size={14} /> {$t('git.commit')}
						</button>
						{#if data.has_remote}
							<button class="btn" onclick={push} disabled={pushing}>
								{#if pushing}<Loader2 size={14} class="spin" />{/if}
								<Upload size={14} /> {$t('git.push')}
							</button>
						{/if}
					</div>
				</div>
				<p class="commit-hint">{$t('git.commit_hint')}</p>
			</div>
		{/if}

	{/if}
</div>

<style>
	/* ── Branch bar ── */
	.branch-bar {
		background: var(--bd);
		border-radius: var(--r);
		padding: 0.625rem 0.75rem;
		margin-bottom: 1rem;
	}

	.branch-current {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}

	.branch-name {
		font-family: var(--font-ui);
		font-weight: 600;
		color: var(--ac);
	}

	.branch-panel {
		margin-top: 0.75rem;
		border-top: 0.0625rem solid var(--bd);
		padding-top: 0.75rem;
	}

	.branch-list {
		display: flex;
		flex-wrap: wrap;
		gap: 0.25rem;
		margin-bottom: 0.5rem;
	}

	.branch-item {
		padding: 0.25rem 0.5rem;
		background: var(--bg-deep);
		border: 0.0625rem solid var(--bd);
		border-radius: var(--r2);
		color: var(--tx);
		font-size: 0.8125rem;
		font-family: var(--font-ui);
		cursor: pointer;
		display: inline-flex;
		align-items: center;
		gap: 0.25rem;
	}

	.branch-item:hover:not(:disabled) { background: var(--sf2); }
	.branch-item.active { border-color: var(--ac); color: var(--ac); }
	.branch-item:disabled { opacity: 0.6; cursor: default; }

	.branch-create {
		display: flex;
		gap: 0.5rem;
		align-items: center;
	}

	.branch-create .input {
		flex: 1;
		font-size: 0.8125rem;
	}

	/* ── File sections ── */
	.file-section {
		margin-bottom: 1rem;
	}

	.section-header {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		margin-bottom: 0.375rem;
	}

	.section-header h3 {
		font-size: 0.875rem;
		color: var(--tx-bright);
		flex: 1;
	}

	.file-list {
		background: var(--bd);
		border-radius: var(--r);
		overflow: hidden;
	}

	.file-row {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.375rem 0.625rem;
		border-bottom: 0.0625rem solid var(--bd);
		font-size: 0.8125rem;
	}

	.file-row:last-child { border-bottom: none; }
	.file-row:hover { background: var(--bg-deep); }
	.file-row.staged { background: color-mix(in srgb, var(--ok) 6%, transparent); }

	.file-checkbox {
		display: flex;
		align-items: center;
	}

	.file-checkbox input {
		accent-color: var(--ac);
	}

	.file-change {
		display: flex;
		align-items: center;
		width: 1rem;
		flex-shrink: 0;
	}

	.change-add { color: var(--ok); }
	.change-del { color: var(--err); }
	.change-mod { color: var(--warn); }

	.file-path {
		flex: 1;
		font-family: var(--font-ui);
		font-size: 0.8125rem;
		color: var(--tx);
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.file-status-badge {
		font-size: 0.6875rem;
		color: var(--tx-dim);
		background: var(--bg-high);
		padding: 0 0.375rem;
		border-radius: 0.25rem;
		flex-shrink: 0;
	}

	.btn-icon {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 1.5rem;
		height: 1.5rem;
		border: none;
		background: none;
		color: var(--tx-dim);
		cursor: pointer;
		border-radius: var(--r2);
		flex-shrink: 0;
	}

	.btn-icon:hover { color: var(--tx-bright); background: var(--bg-high); }

	/* ── Diff inline ── */
	.diff-inline {
		background: var(--bg-deep);
		border-bottom: 0.0625rem solid var(--bd);
		padding: 0.5rem;
		max-height: 20rem;
		overflow: auto;
	}

	.diff-pre {
		font-family: var(--font-ui);
		font-size: 0.75rem;
		line-height: 1.4;
		white-space: pre;
		color: var(--tx);
		margin: 0;
	}

	/* ── Selection actions ── */
	.selection-actions {
		display: flex;
		gap: 0.5rem;
		margin-top: 0.5rem;
		padding: 0.5rem;
	}

	/* ── Commit box ── */
	.commit-box {
		background: var(--sf);
		border: 0.0625rem solid var(--bd);
		border-radius: var(--r);
		padding: 0.75rem;
		margin-top: 1rem;
	}

	.commit-box h3 {
		font-size: 0.875rem;
		color: var(--tx-bright);
		margin-bottom: 0.5rem;
		display: flex;
		align-items: center;
		gap: 0.375rem;
	}

	.commit-input {
		width: 100%;
		resize: vertical;
		font-family: var(--font-ui);
		font-size: 0.8125rem;
		margin-bottom: 0.5rem;
	}

	.commit-actions {
		display: flex;
		justify-content: space-between;
		align-items: center;
		flex-wrap: wrap;
		gap: 0.5rem;
	}

	.push-toggle {
		display: flex;
		align-items: center;
		gap: 0.375rem;
		font-size: 0.8125rem;
		color: var(--tx);
		cursor: pointer;
	}

	.push-toggle input { accent-color: var(--ac); }
	.push-toggle .hint { color: var(--tx-dim); font-size: 0.75rem; }

	.commit-buttons {
		display: flex;
		gap: 0.5rem;
	}

	.commit-hint {
		margin-top: 0.375rem;
		font-size: 0.75rem;
		color: var(--tx-dim);
	}

	/* ── Misc ── */
	.empty-hint {
		padding: 0.75rem;
		color: var(--tx-dim);
		font-size: 0.8125rem;
		text-align: center;
	}

	.btn-sm {
		font-size: 0.75rem;
		padding: 0.1875rem 0.5rem;
	}

	.input {
		background: var(--bg-deep);
		border: 0.0625rem solid var(--bd);
		border-radius: var(--r2);
		color: var(--tx);
		padding: 0.375rem 0.5rem;
		font-family: inherit;
		font-size: 0.8125rem;
	}

	.input:focus {
		border-color: var(--ac);
		outline: none;
	}
</style>
