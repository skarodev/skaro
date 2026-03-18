<script>
	import { t } from '$lib/i18n/index.js';
	import { status } from '$lib/stores/statusStore.js';
</script>

<div class="page">
	<h1>{$t('nav.cicd')}</h1>
	<p>CI/CD phase: generate deployment pipelines after tests pass.</p>
	
	{#if $status?.cicd_done}
		<p>✅ CI/CD pipeline configuration has been generated.</p>
	{:else}
		<p>🚀 No CI/CD pipeline generated yet. Run the CI/CD phase.</p>
	{/if}
	
	<div class="card">
		<h3>What CI/CD Generates:</h3>
		<ul>
			<li>GitHub Actions workflows (.github/workflows/)</li>
			<li>GitLab CI pipelines (.gitlab-ci.yml)</li>
			<li>Docker configuration</li>
			<li>Environment setup scripts</li>
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