<script>
	import { t } from '$lib/i18n/index.js';
	import { status } from '$lib/stores/statusStore.js';
	import { Bot, ChevronDown, Check } from 'lucide-svelte';

	let {
		value = '',
		onSelect = (provider, model) => {},
	} = $props();

	let open = $state(false);
	let root = $state(null);

	/** Build list of unique configured models from status config. */
	let models = $derived.by(() => {
		const s = $status;
		if (!s?.config) return [];

		const cfg = s.config;
		const seen = new Set();
		const list = [];

		function add(provider, model) {
			const key = `${provider}/${model}`;
			if (!provider || !model || seen.has(key)) return;
			seen.add(key);
			list.push({ provider, model, key });
		}

		add(cfg.llm_provider, cfg.llm_model);
		if (cfg.roles) {
			for (const [, rc] of Object.entries(cfg.roles)) {
				if (rc?.provider && rc?.model) {
					add(rc.provider, rc.model);
				}
			}
		}
		return list;
	});

	let displayText = $derived.by(() => {
		if (value) {
			const m = models.find((m) => m.key === value);
			return m ? m.model : value.split('/').pop() || value;
		}
		const s = $status;
		if (!s?.config) return '';
		return s.config.llm_model;
	});

	function handleSelect(m) {
		onSelect(m.provider, m.model);
		open = false;
	}

	function toggle(e) {
		e.stopPropagation();
		open = !open;
	}

	$effect(() => {
		if (open) {
			const handler = (e) => {
				if (root && !root.contains(e.target)) open = false;
			};
			document.addEventListener('click', handler, true);
			return () => document.removeEventListener('click', handler, true);
		}
	});
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<div class="chat-model-picker" bind:this={root}>
	<button class="model-trigger" onclick={toggle} title={displayText}>
		<Bot size={14} />
		<span class="model-name">{displayText}</span>
		<ChevronDown size={12} class={open ? 'flipped' : ''} />
	</button>

	{#if open}
		<!-- svelte-ignore a11y_click_events_have_key_events -->
		<div class="model-dropdown" onclick={(e) => e.stopPropagation()}>
			{#each models as m}
				<button
					class="model-option"
					class:selected={value === m.key || (!value && m === models[0])}
					onclick={() => handleSelect(m)}
				>
					<span class="option-model">{m.model}</span>
					{#if value === m.key || (!value && m === models[0])}
						<Check size={13} />
					{/if}
				</button>
			{/each}
		</div>
	{/if}
</div>

<style>
	.chat-model-picker {
		position: relative;
		flex: 1;
		min-width: 0;
	}

	.model-trigger {
		display: flex;
		align-items: center;
		gap: 0.375rem;
		background: none;
		border: none;
		color: var(--tx-bright);
		font-size: 0.8125rem;
		font-family: var(--font-ui);
		cursor: pointer;
		padding: 0.25rem 0.375rem;
		border-radius: var(--r2);
		transition: background 0.12s;
		max-width: 100%;
		overflow: hidden;
	}

	.model-trigger:hover {
		background: var(--sf);
	}

	.model-name {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		min-width: 0;
	}

	.model-trigger :global(.flipped) {
		transform: rotate(180deg);
	}

	.model-dropdown {
		position: absolute;
		top: calc(100% + 0.25rem);
		left: 0;
		z-index: 200;
		background: var(--bg-soft);
		border: 0.0625rem solid var(--bd2);
		border-radius: var(--r);
		box-shadow: 0 0.25rem 1rem rgba(0, 0, 0, .25);
		padding: 0.25rem;
		white-space: nowrap;
	}

	.model-option {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		width: 100%;
		padding: 0.4375rem 0.75rem;
		border: none;
		border-radius: var(--r2);
		background: none;
		color: var(--tx);
		font-size: 0.8125rem;
		font-family: var(--font-ui);
		cursor: pointer;
		text-align: left;
		transition: background 0.1s;
		white-space: nowrap;
	}

	.model-option:hover {
		background: var(--bg-deep);
	}

	.model-option.selected {
		color: var(--ac);
	}

	.option-model {
		flex: 1;
		min-width: 0;
	}
</style>
