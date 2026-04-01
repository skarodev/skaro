<script>
	import MarkdownContent from './MarkdownContent.svelte';

	let {
		tabs = [],
		activeTab = '',
		content = '',
		onSelectTab = (id) => {},
		chatSlot = null,
		testsSlot = null,
		infoSlot = null,
		contentActionsSlot = null,
	} = $props();

	let effectiveTab = $derived(activeTab || tabs[0]?.id || '');

	function handleTabClick(id) {
		onSelectTab(id);
		// Scroll to bottom only for chat tab
		if (id === 'chat') {
			requestAnimationFrame(() => {
				const main = document.querySelector('.main');
				if (main) main.scrollTo({ top: main.scrollHeight, behavior: 'smooth' });
			});
		}
	}
</script>

{#if tabs.length > 0}
	<div class="file-tabs-layout">
		<nav class="file-tabs-nav">
			{#each tabs as tab}
				<button
					class="tab-item"
					class:active={effectiveTab === tab.id}
					onclick={() => handleTabClick(tab.id)}
				>
					{tab.label}
				</button>
			{/each}
		</nav>
		<div class="file-tabs-content">
			{#if contentActionsSlot}
				{@render contentActionsSlot()}
			{/if}
			{#if effectiveTab === 'chat' && chatSlot}
				{@render chatSlot()}
			{:else if effectiveTab === 'tests' && testsSlot}
				{@render testsSlot()}
			{:else if effectiveTab === 'info' && infoSlot}
				{@render infoSlot()}
			{:else}
				<MarkdownContent {content} />
			{/if}
		</div>
	</div>
{/if}

<style>
	.file-tabs-layout {
		display: flex;
		gap: 1.5rem;
		margin-top: 1.5rem;
	}

	.file-tabs-nav {
		position: sticky;
		top: 0;
		width: 14rem;
		flex-shrink: 0;
		align-self: flex-start;
		display: flex;
		flex-direction: column;
		gap: .2rem;
		padding: 0;
		padding-top: 1rem;
	}

	.tab-item {
		display: flex;
		align-items: center;
		width: 100%;
		padding: .75rem;
		border: none;
		border-radius: var(--r);
		background: none;
		color: var(--tx-bright);
		font-size: 1rem;
		font-family: inherit;
		text-align: left;
		cursor: pointer;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
		transition: background .1s;
	}

	.tab-item:hover {
		background: var(--bg-deep);
	}

	.tab-item.active {
		background: var(--bg-deep);
		color: var(--tx-bright);
	}

	.file-tabs-content {
		flex: 1;
		min-width: 0;
	}
</style>
