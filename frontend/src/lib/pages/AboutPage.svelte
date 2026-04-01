<script>
	import { t } from '$lib/i18n/index.js';
	import { updateInfo } from '$lib/stores/statusStore.js';
	import { ExternalLink } from 'lucide-svelte';

	let currentVersion = $derived($updateInfo?.current_version ?? '…');
</script>

<div class="about-page">
	<div class="about-card">
		<div class="about-header">
			<img src="/mark.svg" alt="Skaro" class="about-logo" />
			<div>
				<h1 class="about-title">Skaro</h1>
				<p class="about-tagline">{$t('about.tagline')}</p>
			</div>
		</div>

		<div class="about-section">
			<h2 class="section-heading">{$t('about.description_title')}</h2>
			<p class="about-text">{$t('about.description')}</p>
		</div>

		<div class="about-meta">
			<div class="meta-row">
				<span class="meta-label">{$t('about.version')}</span>
				<span class="meta-value"><span class="version-badge">v{currentVersion}</span></span>
			</div>
			<div class="meta-row">
				<span class="meta-label">{$t('about.license')}</span>
				<span class="meta-value">AGPL-3.0-or-later</span>
			</div>
			<div class="meta-row">
				<span class="meta-label">{$t('about.author')}</span>
				<span class="meta-value">
					<a
						href="https://ermolaev.tech"
						target="_blank"
						rel="noopener noreferrer"
						class="about-link"
					>
						Andrey Ermolaev
						<ExternalLink size={13} strokeWidth={1.75} />
					</a>
				</span>
			</div>
		</div>
	</div>
</div>

<style>
	.about-page {
		flex: 1;
		display: flex;
		justify-content: center;
		align-items: flex-start;
		padding: 3rem 2rem;
		overflow-y: auto;
	}

	.about-card {
		width: 100%;
		max-width: 36rem;
		display: flex;
		flex-direction: column;
		gap: 2rem;
	}

	.about-header {
		display: flex;
		align-items: center;
		gap: 1.25rem;
	}

	.about-logo {
		width: 3.5rem;
		height: 3.5rem;
		flex-shrink: 0;
	}

	.about-title {
		margin: 0;
		font-size: 1.75rem;
		font-weight: 600;
		color: var(--tx-bright);
		line-height: 1.2;
	}

	.about-tagline {
		margin: 0.25rem 0 0;
		font-size: 0.9375rem;
		color: var(--tx-dim);
	}

	.about-section {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}

	.section-heading {
		margin: 0;
		font-size: 0.75rem;
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.06em;
		color: var(--tx-dim);
	}

	.about-text {
		margin: 0;
		font-size: 0.9375rem;
		color: var(--tx-bright);
		line-height: 1.6;
	}

	.about-meta {
		display: flex;
		flex-direction: column;
		gap: 0;
		border: 0.0625rem solid var(--bd);
		border-radius: var(--r2);
		overflow: hidden;
	}

	.meta-row {
		display: flex;
		align-items: center;
		gap: 1rem;
		padding: 0.75rem 1rem;
		border-bottom: 0.0625rem solid var(--bd);
	}

	.meta-row:last-child {
		border-bottom: none;
	}

	.meta-label {
		font-size: 0.875rem;
		color: var(--tx-dim);
		min-width: 5rem;
		flex-shrink: 0;
	}

	.meta-value {
		font-size: 0.9375rem;
		color: var(--tx-bright);
		display: flex;
		align-items: center;
		gap: 0.375rem;
	}

	.version-badge {
		background: var(--sf);
		padding: 0.125rem 0.5rem;
		border-radius: 0.5rem;
		font-size: 0.8125rem;
		font-family: var(--font-ui);
		color: var(--tx-dim);
	}

	.about-link {
		display: inline-flex;
		align-items: center;
		gap: 0.3rem;
		color: var(--tx-bright);
		text-decoration: none;
		transition: color 0.15s;
	}

	.about-link:hover {
		text-decoration: underline;
		opacity: 0.8;
	}
</style>
