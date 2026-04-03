<script>
	/**
	 * Segmented button group (toggle control).
	 *
	 * @prop {Array<{value: string, label: string, icon?: Component}>} items
	 * @prop {string} value — bindable, current selection
	 * @prop {Snippet?} item — optional render snippet `{#snippet item(it, active)}`
	 */
	let { items = [], value = $bindable(''), item } = $props();
</script>

<div class="btn-group-seg" role="radiogroup">
	{#each items as it (it.value)}
		{@const active = value === it.value}
		<button
			class="btn-group-seg-item"
			class:active
			role="radio"
			aria-checked={active}
			onclick={() => value = it.value}
		>
			{#if item}
				{@render item(it, active)}
			{:else}
				{#if it.icon}
					<svelte:component this={it.icon} size={14} />
				{/if}
				{it.label}
			{/if}
		</button>
	{/each}
</div>

<style>
	.btn-group-seg {
		display: inline-flex;
		align-items: center;
		gap: 1px;
		padding: 2px;
		background: var(--bg-deep);
		border-radius: var(--r);
	}

	.btn-group-seg-item {
		display: inline-flex;
		align-items: center;
		gap: 0.375rem;
		padding: 0.25rem 0.75rem;
		border: none;
		border-radius: var(--r);
		background: transparent;
		color: var(--tx);
		font-size: 0.8125rem;
		font-family: inherit;
		line-height: 1.25rem;
		white-space: nowrap;
		cursor: pointer;
		transition: background 0.12s, color 0.12s;
	}

	.btn-group-seg-item:hover {
		color: var(--tx-bright);
	}

	.btn-group-seg-item.active {
		background: var(--bg);
		color: var(--tx-bright);
	}
</style>
