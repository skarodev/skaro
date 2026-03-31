<script>
	import { t } from '$lib/i18n/index.js';
	import { api } from '$lib/api/client.js';
	import { RefreshCw, Search, ChevronDown, Star, Check, Keyboard } from 'lucide-svelte';

	let {
		value = $bindable(''),
		provider = '',
		id = '',
	} = $props();

	// ── State ──
	let open = $state(false);
	let search = $state('');
	let loading = $state(false);
	let curated = $state([]);
	let extra = $state([]);
	let source = $state('static');
	let fetchError = $state('');
	let root = $state(null);
	let inputEl = $state(null);

	// ── Derived ──
	let lowerSearch = $derived(search.toLowerCase());

	let filteredCurated = $derived(
		lowerSearch
			? curated.filter(m => m.id.toLowerCase().includes(lowerSearch) || m.name.toLowerCase().includes(lowerSearch))
			: curated
	);

	let filteredExtra = $derived(
		lowerSearch
			? extra.filter(m => m.id.toLowerCase().includes(lowerSearch) || m.name.toLowerCase().includes(lowerSearch))
			: extra
	);

	let hasResults = $derived(filteredCurated.length > 0 || filteredExtra.length > 0);

	let showCustomOption = $derived(
		search.length > 0 && !curated.some(m => m.id === search) && !extra.some(m => m.id === search)
	);

	let displayName = $derived(() => {
		const found = curated.find(m => m.id === value) || extra.find(m => m.id === value);
		return found ? found.name : value;
	});

	// ── Fetch models when provider changes ──
	let prevProvider = $state('');

	$effect(() => {
		if (provider && provider !== prevProvider) {
			prevProvider = provider;
			fetchModels(false);
		}
	});

	async function fetchModels(refresh = false) {
		if (!provider) return;
		loading = true;
		fetchError = '';
		try {
			const data = await api.getModels(provider, refresh);
			curated = data.curated || [];
			extra = data.extra || [];
			source = data.source || 'static';
			if (data.error) fetchError = data.error;
		} catch (e) {
			fetchError = e.message || 'Failed to fetch models';
		}
		loading = false;
	}

	async function onRefresh(e) {
		e.stopPropagation();
		await fetchModels(true);
	}

	function selectModel(modelId) {
		value = modelId;
		search = '';
		open = false;
	}

	function useCustom() {
		value = search;
		search = '';
		open = false;
	}

	function onTriggerClick() {
		open = !open;
		if (open) {
			search = '';
			// Focus search input after dropdown opens
			requestAnimationFrame(() => inputEl?.focus());
		}
	}

	function onKeydown(e) {
		if (e.key === 'Escape') {
			open = false;
		} else if (e.key === 'Enter' && open) {
			e.preventDefault();
			// Select first match or use custom
			if (filteredCurated.length > 0) {
				selectModel(filteredCurated[0].id);
			} else if (filteredExtra.length > 0) {
				selectModel(filteredExtra[0].id);
			} else if (showCustomOption) {
				useCustom();
			}
		}
	}

	function onClickOutside(e) {
		if (open && root && !root.contains(e.target)) {
			open = false;
			search = '';
		}
	}

	$effect(() => {
		if (open) {
			document.addEventListener('click', onClickOutside, true);
			return () => document.removeEventListener('click', onClickOutside, true);
		}
	});
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<div class="model-picker" bind:this={root} onkeydown={onKeydown}>
	<div class="trigger-row">
		<button type="button" {id} class="trigger" class:focused={open} onclick={onTriggerClick}>
			<span class="trigger-value" class:placeholder={!value}>
				{value ? displayName() : $t('settings.model_select_placeholder')}
			</span>
			<span class="chevron" class:flipped={open}>
				<ChevronDown size={14} />
			</span>
		</button>
		{#if loading}
			<span class="refresh-btn"><RefreshCw size={14} class="spin" /></span>
		{:else}
			<button
				type="button"
				class="refresh-btn"
				title={$t('settings.model_refresh')}
				onclick={onRefresh}
			>
				<RefreshCw size={14} />
			</button>
		{/if}
	</div>

	{#if open}
		<div class="dropdown">
			<div class="search-row">
				<Search size={14} />
				<input
					bind:this={inputEl}
					type="text"
					bind:value={search}
					placeholder={$t('settings.model_search_placeholder')}
					class="search-input"
				/>
			</div>

			<div class="options-list">
				{#if filteredCurated.length > 0}
					<div class="group-header">
						<Star size={12} />
						<span>{$t('settings.model_group_curated')}</span>
					</div>
					{#each filteredCurated as m}
						<button
							type="button"
							class="option"
							class:selected={m.id === value}
							onclick={() => selectModel(m.id)}
							title="{m.id} — ctx: {(m.context_window / 1000).toFixed(0)}k, out: {(m.max_output / 1000).toFixed(0)}k"
						>
							<span class="option-name">{m.name}</span>
							<span class="option-meta">{(m.context_window / 1000).toFixed(0)}k</span>
							{#if m.id === value}<Check size={14} />{/if}
						</button>
					{/each}
				{/if}

				{#if filteredExtra.length > 0}
					<div class="group-header">
						<span>{$t('settings.model_group_all')}</span>
						{#if source !== 'static'}
							<span class="source-badge">{source}</span>
						{/if}
					</div>
					{#each filteredExtra as m}
						<button
							type="button"
							class="option"
							class:selected={m.id === value}
							onclick={() => selectModel(m.id)}
							title="{m.id} — ctx: {(m.context_window / 1000).toFixed(0)}k, out: {(m.max_output / 1000).toFixed(0)}k"
						>
							<span class="option-name">{m.id}</span>
							<span class="option-meta">{(m.context_window / 1000).toFixed(0)}k</span>
							{#if m.id === value}<Check size={14} />{/if}
						</button>
					{/each}
				{/if}

				{#if !hasResults && !showCustomOption}
					<div class="empty">{$t('settings.model_no_results')}</div>
				{/if}

				{#if showCustomOption}
					<div class="group-header">
						<Keyboard size={12} />
						<span>{$t('settings.model_custom')}</span>
					</div>
					<button type="button" class="option custom-option" onclick={useCustom}>
						<span class="option-name">{$t('settings.model_use_custom', { model: search })}</span>
					</button>
				{/if}
			</div>

			{#if fetchError}
				<div class="fetch-error">{fetchError}</div>
			{/if}
		</div>
	{/if}
</div>

<style>
	.model-picker {
		position: relative;
	}

	.trigger-row {
		display: flex;
		align-items: center;
		gap: 0;
		background-color: var(--bg2);
		border: 0.0625rem solid var(--bg);
		border-radius: var(--r2);
		transition: border-color .15s;
	}

	.trigger-row:focus-within {
		border-color: var(--ac);
	}

	.trigger-row:has(.focused) {
		border-color: var(--ac);
	}

	.trigger {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		flex: 1;
		min-width: 0;
		padding: .7rem;
		background: none;
		border: none;
		color: var(--tx);
		font-size: 1rem;
		font-family: var(--font-ui);
		cursor: pointer;
		text-align: left;
		outline: none;
	}

	.trigger-value {
		flex: 1;
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.trigger-value.placeholder {
		color: var(--dm);
	}

	.chevron {
		display: flex;
		color: var(--dm);
		transition: transform .15s;
		flex-shrink: 0;
	}

	.chevron.flipped {
		transform: rotate(180deg);
	}

	.refresh-btn {
		display: flex;
		align-items: center;
		justify-content: center;
		background: none;
		border: none;
		color: var(--dm);
		cursor: pointer;
		padding: 0.5rem;
		border-radius: var(--r2);
		transition: color .15s;
		flex-shrink: 0;
	}

	.refresh-btn:hover {
		color: var(--ac);
	}

	.refresh-btn :global(.spin) {
		animation: spin 1s linear infinite;
	}

	@keyframes spin {
		from { transform: rotate(0deg); }
		to { transform: rotate(360deg); }
	}

	.dropdown {
		position: absolute;
		top: calc(100% + 0.25rem);
		left: 0;
		right: 0;
		z-index: 200;
		background: var(--bg2);
		border: 0.0625rem solid var(--bd);
		border-radius: var(--r2);
		box-shadow: 0 0.5rem 1.5rem rgba(0, 0, 0, .35);
		overflow: hidden;
	}

	.search-row {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.5rem 0.625rem;
		border-bottom: 0.0625rem solid var(--bd);
		color: var(--dm);
	}

	.search-input {
		flex: 1;
		background: none;
		border: none;
		color: var(--tx);
		font-size: 0.875rem;
		font-family: var(--font-ui);
		outline: none;
		padding: 0;
	}

	.search-input::placeholder {
		color: var(--dm);
		opacity: 0.6;
	}

	.options-list {
		max-height: 18rem;
		overflow-y: auto;
		padding: 0.25rem;
	}

	.group-header {
		display: flex;
		align-items: center;
		gap: 0.375rem;
		padding: 0.375rem 0.625rem 0.25rem;
		font-size: 0.6875rem;
		font-weight: 600;
		color: var(--dm);
		text-transform: uppercase;
		letter-spacing: 0.03rem;
	}

	.source-badge {
		font-size: 0.5625rem;
		background: var(--bg);
		padding: 0.0625rem 0.3125rem;
		border-radius: 0.25rem;
		font-weight: 500;
		text-transform: lowercase;
		letter-spacing: 0;
	}

	.option {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		width: 100%;
		padding: 0.4375rem 0.625rem;
		border: none;
		border-radius: var(--r2);
		background: none;
		color: var(--tx);
		font-size: 0.875rem;
		font-family: var(--font-ui);
		cursor: pointer;
		text-align: left;
		transition: background .1s;
	}

	.option:hover {
		background: var(--sf);
	}

	.option.selected {
		color: var(--ac);
	}

	.option-name {
		flex: 1;
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.option-meta {
		font-size: 0.6875rem;
		color: var(--dm);
		flex-shrink: 0;
	}

	.custom-option .option-name {
		font-style: italic;
		color: var(--dm);
	}

	.empty {
		padding: 0.75rem 0.625rem;
		font-size: 0.8125rem;
		color: var(--dm);
		text-align: center;
	}

	.fetch-error {
		padding: 0.375rem 0.625rem;
		font-size: 0.6875rem;
		color: var(--yl);
		border-top: 0.0625rem solid var(--bd);
	}
</style>
