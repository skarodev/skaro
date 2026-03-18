<script>
	import { t } from '$lib/i18n/index.js';
	import { status } from '$lib/stores/statusStore.js';
</script>

<div class="page">
	<h1>{$t('nav.analytics')}</h1>
	<p>Analytics phase: pre-clarification analysis of task specifications.</p>
	
	{#if $status?.analytics_done}
		<p>✅ Analytics reports have been generated for tasks.</p>
	{:else}
		<p>📊 No analytics reports yet. Run analytics phase on tasks.</p>
	{/if}
	
	<div class="card">
		<h3>What Analytics Does:</h3>
		<ul>
			<li>Complexity assessment (LOW/MEDIUM/HIGH/CRITICAL)</li>
			<li>Risk identification with probability/impact ratings</li>
			<li>Dependency analysis (external APIs, internal modules)</li>
			<li>Technology fit evaluation (1-5 rating)</li>
			<li>Effort breakdown by stage (research, design, implementation, testing)</li>
			<li>Recommendations for approach and simplifications</li>
		</ul>
	</div>
</div>

<style>
	.page {
		padding: 2rem;
		max-width: 800px;
	}
	
	.card {
		background: var(--bg2);
		border-radius: var(--r);
		padding: 1.5rem;
		margin-top: 1.5rem;
	}
	
	.card h3 {
		margin-top: 0;
	}
	
	.card ul {
		margin: 0.5rem 0 0 0;
		padding-left: 1.5rem;
	}
	
	.card li {
		margin-bottom: 0.5rem;
	}
</style>