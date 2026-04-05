<script>
	import { t } from '$lib/i18n/index.js';
	import { Search, FolderOpen, File, ChevronRight, ChevronDown, Trash2 } from 'lucide-svelte';
	import Modal from '$lib/ui/Modal.svelte';

	/**
	 * @type {{
	 *   tree: any[],
	 *   selected: string[],
	 *   onConfirm: (paths: string[]) => void,
	 *   onClose: () => void,
	 * }}
	 */
	let { tree = [], selected = [], onConfirm, onClose } = $props();

	let localSelected = $state(new Set());
	let expanded = $state(new Set());
	let filter = $state('');

	// Sync from prop when modal opens
	$effect(() => {
		localSelected = new Set(selected);
	});

	// Auto-expand first level on mount
	$effect(() => {
		const firstLevel = new Set();
		for (const node of tree) {
			if (node.type === 'dir') firstLevel.add(node.path);
		}
		expanded = firstLevel;
	});

	let filterLower = $derived(filter.toLowerCase());

	function nodeVisible(node) {
		if (!filterLower) return true;
		if (node.name.toLowerCase().includes(filterLower)) return true;
		if (node.type === 'dir' && node.children) {
			return node.children.some((c) => nodeVisible(c));
		}
		return false;
	}

	function getAllFiles(node) {
		if (node.type === 'file') return [node.path];
		if (!node.children) return [];
		return node.children.flatMap(getAllFiles);
	}

	function getCheckState(node) {
		if (node.type === 'file') return localSelected.has(node.path) ? 'all' : 'none';
		const files = getAllFiles(node);
		if (files.length === 0) return 'none';
		const count = files.filter((f) => localSelected.has(f)).length;
		if (count === 0) return 'none';
		if (count === files.length) return 'all';
		return 'partial';
	}

	function toggleNode(node) {
		const files = getAllFiles(node);
		const state = getCheckState(node);
		const next = new Set(localSelected);
		if (state === 'all') {
			files.forEach((f) => next.delete(f));
		} else {
			files.forEach((f) => next.add(f));
		}
		localSelected = next;
	}

	function toggleExpand(path) {
		const next = new Set(expanded);
		if (next.has(path)) next.delete(path);
		else next.add(path);
		expanded = next;
	}

	function clearAll() {
		localSelected = new Set();
	}

	function confirm() {
		onConfirm([...localSelected]);
	}

	let selectedCount = $derived(localSelected.size);
	let estimatedTokens = $derived.by(() => {
		// Rough estimate: find matching nodes in tree, sum sizes
		let bytes = 0;
		function walk(nodes) {
			for (const n of nodes) {
				if (n.type === 'file' && localSelected.has(n.path)) {
					bytes += n.size || 0;
				}
				if (n.children) walk(n.children);
			}
		}
		walk(tree);
		return Math.round(bytes / 4);
	});
	let tokenDisplay = $derived.by(() => {
		const k = estimatedTokens / 1000;
		return k >= 1 ? `~${k.toFixed(0)}k ${$t('fix.tokens')}` : `~${estimatedTokens} ${$t('fix.tokens')}`;
	});

	function formatSize(bytes) {
		if (bytes < 1024) return `${bytes} B`;
		return `${(bytes / 1024).toFixed(1)} KB`;
	}
</script>

<Modal title={$t('scope.title')} {onClose} width="62.5rem" maxHeight="85vh">
	<div class="search-bar">
		<Search size={14} />
		<input
			type="text"
			bind:value={filter}
			placeholder={$t('scope.search_placeholder')}
			class="search-input"
		/>
	</div>

	<div class="tree-scroll">
		{#each tree as node}
			{#if nodeVisible(node)}
				{@render treeNode(node, 0)}
			{/if}
		{/each}
		{#if tree.length === 0}
			<div class="empty">{$t('scope.empty')}</div>
		{/if}
	</div>

	{#snippet footer()}
		<div class="scope-footer">
			<div class="footer-info">
				<span class="count">{$t('scope.selected_count', { n: selectedCount })}</span>
				{#if selectedCount > 0}
					<span class="tokens">{tokenDisplay}</span>
				{/if}
			</div>
			<div class="footer-actions">
				{#if selectedCount > 0}
					<button class="btn btn-sm" onclick={clearAll}>
						<Trash2 size={12} /> {$t('scope.clear')}
					</button>
				{/if}
				<button class="btn" onclick={onClose}>{$t('scope.cancel')}</button>
				<button class="btn btn-primary" onclick={confirm}>{$t('scope.confirm')}</button>
			</div>
		</div>
	{/snippet}
</Modal>

{#snippet treeNode(node, depth)}
	{@const state = getCheckState(node)}
	{@const isDir = node.type === 'dir'}
	{@const isExpanded = expanded.has(node.path)}
	{@const visible = nodeVisible(node)}
	{#if visible}
		<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
		<div
			class="tree-item"
			class:tree-dir={isDir}
			style="padding-left: {0.75 + depth * 1.25}rem"
		>
			{#if isDir}
				<button class="expand-btn" onclick={() => toggleExpand(node.path)}>
					{#if isExpanded}<ChevronDown size={13} />{:else}<ChevronRight size={13} />{/if}
				</button>
			{:else}
				<span class="expand-spacer"></span>
			{/if}
			<input
				type="checkbox"
				checked={state === 'all'}
				indeterminate={state === 'partial'}
				onchange={() => toggleNode(node)}
				class="tree-check"
			/>
			<span class="tree-icon">
				{#if isDir}<FolderOpen size={14} />{:else}<File size={14} />{/if}
			</span>
			<span
				class="tree-name"
				class:tree-name-dir={isDir}
				onclick={() => { if (isDir) toggleExpand(node.path); else toggleNode(node); }}
			>
				{node.name}
			</span>
			{#if !isDir && node.size}
				<span class="tree-size">{formatSize(node.size)}</span>
			{/if}
		</div>
		{#if isDir && isExpanded && node.children}
			{#each node.children as child}
				{#if nodeVisible(child)}
					{@render treeNode(child, depth + 1)}
				{/if}
			{/each}
		{/if}
	{/if}
{/snippet}

<style>
	.search-bar {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.5rem 1rem;
		border-bottom: 0.0625rem solid var(--bd);
		color: var(--tx-dim);
		flex-shrink: 0;
	}

	.search-input {
		flex: 1;
		background: none;
		border: none;
		outline: none;
		color: var(--tx-bright);
		font-size: 0.8125rem;
		font-family: var(--font-ui);
	}
	.search-input::placeholder { color: var(--tx-dim); }

	.tree-scroll {
		overflow-y: auto;
		flex: 1;
		min-height: 0;
		padding: 0.375rem 0;
	}

	.tree-item {
		display: flex;
		align-items: center;
		gap: 0.25rem;
		padding-top: 0.1875rem;
		padding-bottom: 0.1875rem;
		padding-right: 0.75rem;
		font-size: 0.8125rem;
		cursor: default;
		transition: background 0.08s;
	}
	.tree-item:hover { background: var(--sf-hover); }

	.expand-btn {
		background: none;
		border: none;
		color: var(--tx-dim);
		cursor: pointer;
		padding: 0;
		display: flex;
		align-items: center;
		width: 1rem;
		flex-shrink: 0;
	}
	.expand-btn:hover { color: var(--tx-bright); }

	.expand-spacer { width: 1rem; flex-shrink: 0; }

	.tree-check {
		accent-color: var(--ac);
		cursor: pointer;
		flex-shrink: 0;
	}

	.tree-icon {
		color: var(--tx-dim);
		display: flex;
		align-items: center;
		flex-shrink: 0;
	}
	.tree-dir .tree-icon { color: var(--warn); }

	.tree-name {
		flex: 1;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		color: var(--tx);
		cursor: pointer;
		font-family: var(--font-ui);
	}
	.tree-name-dir { color: var(--tx-bright); font-weight: 500; }

	.tree-size {
		font-size: 0.6875rem;
		color: var(--tx-dim);
		font-family: var(--font-ui);
		flex-shrink: 0;
		margin-left: auto;
	}

	.empty {
		padding: 2rem;
		text-align: center;
		color: var(--tx-dim);
		font-size: 0.8125rem;
	}

	.scope-footer {
		display: flex;
		align-items: center;
		justify-content: space-between;
		width: 100%;
	}

	.footer-info {
		display: flex;
		align-items: center;
		gap: 0.75rem;
	}

	.count {
		font-size: 0.75rem;
		color: var(--tx);
		font-family: var(--font-ui);
	}

	.tokens {
		font-size: 0.6875rem;
		color: var(--tx-dim);
		font-family: var(--font-ui);
	}

	.footer-actions {
		display: flex;
		gap: 0.5rem;
		align-items: center;
	}

	.btn-sm {
		font-size: 0.75rem;
		padding: 0.1875rem 0.5rem;
		display: flex;
		align-items: center;
		gap: 0.25rem;
	}

	.btn-primary {
		background: var(--ac);
		color: #fff;
		border-color: var(--ac);
	}
	.btn-primary:hover { background: color-mix(in srgb, var(--ac) 85%, black); }
</style>
