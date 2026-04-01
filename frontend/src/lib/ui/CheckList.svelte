<script>
	import { CheckCircle, XCircle } from 'lucide-svelte';

	let { checks = [] } = $props();
</script>

<div class="check-list">
	{#each checks as check}
		<div class="check-item" class:pass={check.passed} class:fail={!check.passed}>
			{#if check.passed}
				<CheckCircle size={15} class="icon-pass" />
			{:else}
				<XCircle size={15} class="icon-fail" />
			{/if}
			<span class="check-label">{check.label}</span>
			<span class="check-detail">{check.detail}</span>
		</div>
	{/each}
</div>

<style>
	.check-list { display: flex; flex-direction: column; gap: 0.25rem; }

	.check-item {
		display: flex; align-items: center; gap: 0.5rem;
		padding: 0.375rem 0.625rem; background: var(--bg-deep);
		border-radius: var(--r2); font-size: 0.8125rem;
	}

	.check-label { font-weight: 500; color: var(--tx); }

	.check-detail {
		margin-left: auto; font-size: 0.75rem;
		color: var(--dm); font-family: var(--font-ui);
	}

	:global(.icon-pass) { color: var(--gn-bright); flex-shrink: 0; }
	:global(.icon-fail) { color: var(--rd); flex-shrink: 0; }
</style>
