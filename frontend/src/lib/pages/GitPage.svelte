<script>
	import { onMount } from 'svelte';
	import { t } from '$lib/i18n/index.js';
	import { api } from '$lib/api/client.js';
	import { onWsEvent } from '$lib/api/client.js';
	import { addLog, addError } from '$lib/stores/logStore.js';
	import {
		GitBranch, GitCommit, Upload, RefreshCw, ChevronDown,
		Plus, Minus, FileQuestion, FilePen, Check, X, Loader2,
		AlertTriangle, Eye, CircleCheckBig
	} from 'lucide-svelte';
	import Tooltip from '$lib/ui/Tooltip.svelte';
	import GitDiffModal from './git/GitDiffModal.svelte';

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
	let isClean = $derived(!hasStaged && !hasUnstaged);

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
		diffFile = filepath;
		loadingDiff = true;
		try {
			const result = await api.getGitDiff(filepath);
			diffContent = result.diff || '(no changes)';
		} catch (e) { diffContent = `Error: ${e.message}`; }
		loadingDiff = false;
	}

	function closeDiff() {
		diffFile = null;
		diffContent = '';
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
		if (change === 'M') return FilePen;
		return FileQuestion;
	}

	function changeClass(change) {
		if (change === 'A') return 'change-add';
		if (change === 'D') return 'change-del';
		return 'change-mod';
	}
</script>

<div class="git-page">
	<div class="main-header">
		<h2><GitBranch size={20} /> {$t('git.title')}</h2>
		<p>{$t('git.subtitle')}</p>
	</div>

	{#if error}
		<div class="alert alert-warn"><AlertTriangle size={14} /> {error}</div>
	{:else if loading && !data}
		<div class="loading-text"><Loader2 size={14} class="spin" /> {$t('app.loading')}</div>
	{:else if data && !data.is_repo}
		<div class="alert alert-warn"><AlertTriangle size={14} /> {$t('git.not_a_repo')}</div>
	{:else if data}

		<!-- ── Branch toolbar ── -->
		<div class="git-toolbar">
			<div class="git-toolbar-row">
				<div class="git-branch-info">
					<GitBranch size={14} />
					<span class="git-branch-name">{data.branch}</span>
					{#if hasStaged}
						<span class="status-badge status-badge-ok">{stagedFiles.length} staged</span>
					{/if}
					{#if hasUnstaged}
						<span class="status-badge git-badge-warn">{unstagedFiles.length} changed</span>
					{/if}
					{#if isClean}
						<span class="status-badge status-badge-ok"><Check size={10} /> clean</span>
					{/if}
				</div>
				<div class="git-toolbar-actions">
					<button class="btn btn-sm" onclick={() => showBranchInput = !showBranchInput}>
						<ChevronDown size={12} /> {$t('git.branches')}
					</button>
					<Tooltip text={$t('git.refresh')} placement="bottom">
						<button class="btn btn-sm" onclick={load}>
							<RefreshCw size={12} />
						</button>
					</Tooltip>
				</div>
			</div>

			{#if showBranchInput}
				<div class="git-branch-panel">
					<div class="git-branch-list">
						{#each data.branches as br}
							<button
								class="git-branch-item"
								class:active={br === data.branch}
								disabled={br === data.branch || switchingBranch}
								onclick={() => switchBranch(br)}
							>
								{br}
								{#if br === data.branch}<Check size={12} />{/if}
							</button>
						{/each}
					</div>
					<div class="git-branch-create">
						<input
							type="text"
							class="git-input"
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

		<!-- ── Clean state ── -->
		{#if isClean}
			<div class="card git-clean-state">
				<CircleCheckBig size={28} />
				<p>{$t('git.working_tree_clean')}</p>
			</div>
		{:else}
			<!-- ── File sections grid ── -->
			<div class="git-files-grid">

				<!-- Staged changes -->
				<div class="card git-file-section">
					<div class="section-head">
						<h3>{$t('git.staged_changes')} ({stagedFiles.length})</h3>
						{#if hasStaged}
							<button class="sec-btn" onclick={unstageAll} disabled={staging}>
								<Minus size={10} /> {$t('git.unstage_all')}
							</button>
						{/if}
					</div>
					{#if hasStaged}
						<div class="git-file-list">
							{#each stagedFiles as f}
								{@const Icon = changeIcon(f.change)}
								<div class="git-file-row git-file-staged">
									<span class="git-file-change {changeClass(f.change)}"><Icon size={12} /></span>
									<span class="git-file-path">{f.path}</span>
									<Tooltip text={$t('git.view_diff')} placement="top">
										<button class="git-btn-icon" onclick={() => showDiff(f.path)}>
											<Eye size={13} />
										</button>
									</Tooltip>
									<Tooltip text={$t('git.unstage')} placement="top">
										<button class="git-btn-icon" onclick={() => unstageFiles([f.path])}>
											<Minus size={13} />
										</button>
									</Tooltip>
								</div>
							{/each}
						</div>
					{:else}
						<p class="empty-hint">{$t('git.no_staged')}</p>
					{/if}
				</div>

				<!-- Unstaged / untracked -->
				<div class="card git-file-section">
					<div class="section-head">
						<h3>{$t('git.changes')} ({unstagedFiles.length})</h3>
						{#if hasUnstaged}
							<div class="git-section-actions">
								<button class="sec-btn" onclick={() => selectAll(unstagedFiles)}>
									<Check size={10} /> {$t('git.select_all')}
								</button>
								<button class="sec-btn" onclick={stageAll} disabled={staging}>
									<Plus size={10} /> {$t('git.stage_all')}
								</button>
							</div>
						{/if}
					</div>
					{#if hasUnstaged}
						<div class="git-file-list">
							{#each unstagedFiles as f}
								{@const Icon = changeIcon(f.change)}
								<div class="git-file-row">
									<label class="git-file-checkbox">
										<input
											type="checkbox"
											checked={selectedFiles.has(f.path)}
											onchange={() => toggleSelect(f.path)}
										/>
									</label>
									<span class="git-file-change {changeClass(f.change)}"><Icon size={12} /></span>
									<span class="git-file-path">{f.path}</span>
									<span class="git-file-status">{f.status}</span>
									<Tooltip text={$t('git.view_diff')} placement="top">
										<button class="git-btn-icon" onclick={() => showDiff(f.path)}>
											<Eye size={13} />
										</button>
									</Tooltip>
								</div>
							{/each}
						</div>
						{#if selectedFiles.size > 0}
							<div class="git-selection-bar">
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
			</div>
		{/if}

		<!-- ── Commit box ── -->
		{#if hasStaged}
			<div class="card git-commit-box">
				<h3><GitCommit size={16} /> {$t('git.commit')}</h3>
				<textarea
					class="git-input git-commit-input"
					placeholder={$t('git.commit_message_placeholder')}
					bind:value={commitMessage}
					rows="3"
					onkeydown={(e) => { if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') commit(); }}
				></textarea>
				<div class="git-commit-actions">
					<label class="git-push-toggle">
						<input type="checkbox" bind:checked={pushAfterCommit} disabled={!data.has_remote} />
						<Upload size={12} />
						<span>
							{$t('git.push_after_commit')}
							{#if !data.has_remote}
								<span class="hint">({$t('git.no_remote')})</span>
							{/if}
						</span>
					</label>
					<div class="git-commit-buttons">
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
			</div>
		{/if}

	{/if}
</div>

<!-- ── Diff modal ── -->
{#if diffFile && !loadingDiff}
	<GitDiffModal filepath={diffFile} diffText={diffContent} onClose={closeDiff} />
{/if}

<style>
	/* ── Page width ── */

	:global(.main > .git-page) {
		max-width: 63.5rem !important;
	}

	/* ── Branch toolbar (transparent) ── */

	.git-toolbar {
		margin-bottom: 1rem;
	}

	.git-toolbar-row {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.75rem;
	}

	.git-branch-info {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		color: var(--tx-dim);
		min-width: 0;
	}

	.git-branch-name {
		font-family: var(--font-ui);
		font-weight: 600;
		font-size: 0.9375rem;
		color: var(--ac);
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.git-badge-warn {
		background: color-mix(in srgb, var(--warn) 12%, transparent);
		color: var(--warn);
	}

	.git-toolbar-actions {
		display: flex;
		align-items: center;
		gap: 0.375rem;
		flex-shrink: 0;
	}

	/* ── Branch panel ── */

	.git-branch-panel {
		margin-top: 0.75rem;
		border-top: 1px solid var(--bd);
		padding-top: 0.75rem;
	}

	.git-branch-list {
		display: flex;
		flex-wrap: wrap;
		gap: 0.25rem;
		margin-bottom: 0.5rem;
	}

	.git-branch-item {
		padding: 0.25rem 0.5rem;
		background: var(--bg-deep);
		border: 1px solid var(--bd);
		border-radius: var(--r2);
		color: var(--tx);
		font-size: 0.8125rem;
		font-family: var(--font-ui);
		cursor: pointer;
		display: inline-flex;
		align-items: center;
		gap: 0.25rem;
		transition: all .1s;
	}

	.git-branch-item:hover:not(:disabled) { background: var(--sf2); }
	.git-branch-item.active { border-color: var(--ac); color: var(--ac); }
	.git-branch-item:disabled { opacity: 0.6; cursor: default; }

	.git-branch-create {
		display: flex;
		gap: 0.5rem;
		align-items: center;
	}

	.git-branch-create .git-input { flex: 1; }

	/* ── Clean state ── */

	.git-clean-state {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.5rem;
		padding: 2.5rem 1rem;
		color: var(--ok);
		text-align: center;
	}

	.git-clean-state p {
		color: var(--tx-dim);
		font-size: 0.875rem;
		margin: 0;
	}

	/* ── Files grid ── */

	.git-files-grid {
		display: grid;
		grid-template-columns: 1fr;
		gap: 0.5rem;
	}

	@media (min-width: 768px) {
		.git-files-grid {
			grid-template-columns: 1fr 1fr;
		}
	}

	.git-file-section {
		min-width: 0;
	}

	.git-file-section .section-head {
		margin-bottom: 0.5rem;
	}

	.git-section-actions {
		display: flex;
		gap: 0.25rem;
	}

	/* ── File list ── */

	.git-file-list {
		background: var(--bg-deep);
		border-radius: var(--r);
		overflow: hidden;
	}

	.git-file-row {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.375rem 0.625rem;
		border-bottom: 1px solid var(--bg);
		font-size: 0.8125rem;
		transition: background .1s;
	}

	.git-file-row:last-child { border-bottom: none; }
	.git-file-row:hover { background: var(--bg-high); }

	.git-file-staged {
		background: color-mix(in srgb, var(--ok) 4%, transparent);
	}

	.git-file-checkbox {
		display: flex;
		align-items: center;
	}

	.git-file-checkbox input { accent-color: var(--ac); }

	.git-file-change {
		display: flex;
		align-items: center;
		width: 1rem;
		flex-shrink: 0;
	}

	.change-add { color: var(--ok); }
	.change-del { color: var(--err); }
	.change-mod { color: var(--warn); }

	.git-file-path {
		flex: 1;
		font-family: var(--font-ui);
		font-size: 0.8125rem;
		color: var(--tx);
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		min-width: 0;
	}

	.git-file-status {
		font-size: 0.6875rem;
		color: var(--tx-dim);
		background: var(--sf);
		padding: 0 0.375rem;
		border-radius: 0.25rem;
		flex-shrink: 0;
	}

	.git-btn-icon {
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
		transition: all .1s;
	}

	.git-btn-icon:hover { color: var(--tx-bright); background: var(--sf); }

	/* ── Selection bar ── */

	.git-selection-bar {
		display: flex;
		gap: 0.5rem;
		padding: 0.625rem;
		border-top: 1px solid var(--bd);
	}

	/* ── Commit box ── */

	.git-commit-box {
		border-color: color-mix(in srgb, var(--ac) 35%, var(--bd));
	}

	.git-commit-box h3 {
		font-size: 0.9375rem;
		display: flex;
		align-items: center;
		gap: 0.375rem;
	}

	.git-commit-input {
		width: 100%;
		resize: vertical;
		font-family: var(--font-ui);
		font-size: 0.8125rem;
		margin-bottom: 0.5rem;
	}

	.git-commit-actions {
		display: flex;
		justify-content: space-between;
		align-items: center;
		flex-wrap: wrap;
		gap: 0.5rem;
	}

	.git-push-toggle {
		display: inline-flex;
		align-items: center;
		gap: 0.375rem;
		font-size: 0.8125rem;
		color: var(--tx);
		cursor: pointer;
		white-space: nowrap;
	}

	.git-push-toggle input { accent-color: var(--ac); }
	.git-push-toggle .hint { color: var(--tx-dim); font-size: 0.75rem; }

	.git-commit-buttons {
		display: flex;
		gap: 0.5rem;
	}

	/* ── Shared input ── */

	.git-input {
		background: var(--bg-deep);
		border: 1px solid var(--bd);
		border-radius: var(--r);
		color: var(--tx);
		padding: 0.375rem 0.5rem;
		font-family: inherit;
		font-size: 0.8125rem;
	}

	.git-input:focus {
		border-color: var(--ac);
		outline: none;
	}
</style>
