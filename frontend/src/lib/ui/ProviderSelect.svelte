<script>
	import { providerLabels } from '$lib/ui/icons/providers.js';
	import { ChevronDown } from 'lucide-svelte';

	let {
		value = $bindable(''),
		providers = [],
		id = '',
		onchange = () => {},
	} = $props();

	let open = $state(false);
	let root = $state(null);

	function select(p) {
		if (p !== value) {
			value = p;
			onchange();
		}
		open = false;
	}

	function onKeydown(e) {
		if (e.key === 'Escape') { open = false; }
	}

	function onClickOutside(e) {
		if (open && root && !root.contains(e.target)) {
			open = false;
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
<div class="provider-select" bind:this={root} onkeydown={onKeydown}>
	<button type="button" class="trigger" {id} onclick={() => open = !open}>
		<img class="icon" src="/icons/providers/{value}.svg" alt="" />
		<span class="label">{$providerLabels[value] || value}</span>
		<ChevronDown size={14} />
	</button>

	{#if open}
		<div class="dropdown">
			{#each providers as p}
				<button
					type="button"
					class="option"
					class:selected={p === value}
					onclick={() => select(p)}
				>
					<img class="icon" src="/icons/providers/{p}.svg" alt="" />
					<span>{$providerLabels[p] || p}</span>
				</button>
			{/each}
		</div>
	{/if}
</div>

<style>
	.provider-select {
		position: relative;
	}

	.trigger {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		width: 100%;
		padding: .7rem;
		background-color: var(--bg-deep);
		border: 0.0625rem solid var(--bg);
		border-radius: var(--r2);
		color: var(--tx);
		font-size: 1rem;
		font-family: var(--font-ui);
		cursor: pointer;
		text-align: left;
		transition: border-color .15s;
	}

	.trigger:focus {
		outline: none;
		border-color: var(--ac);
	}

	.trigger .label {
		flex: 1;
		min-width: 0;
	}

	.trigger :global(svg:last-child) {
		color: var(--dm);
		flex-shrink: 0;
		transition: transform .15s;
	}

	.icon {
		width: 1.25rem;
		height: 1.25rem;
		flex-shrink: 0;
		border-radius: 50%;
	}

	.dropdown {
		position: absolute;
		top: calc(100% + 0.25rem);
		left: 0;
		right: 0;
		z-index: 100;
		background: var(--bg-deep);
		border: 0.0625rem solid var(--bd);
		border-radius: var(--r2);
		padding: 0.25rem;
		box-shadow: 0 0.5rem 1.5rem rgba(0, 0, 0, .35);
	}

	.option {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		width: 100%;
		padding: 0.5rem 0.625rem;
		border: none;
		border-radius: var(--r2);
		background: none;
		color: var(--tx);
		font-size: 1rem;
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
</style>
