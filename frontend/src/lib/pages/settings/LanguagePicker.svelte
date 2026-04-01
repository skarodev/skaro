<script>
	import { t } from '$lib/i18n/index.js';

	let { lang = $bindable('en') } = $props();
</script>

<div class="card">
	<h3>{$t('settings.language')}</h3>
	<div class="lang-tabs">
		<button class="tab" class:active={lang === 'en'} onclick={() => lang = 'en'}>
			<svg class="flag" viewBox="0 0 60 30" width="24" height="12">
				<clipPath id="gb"><rect width="60" height="30" rx="2"/></clipPath>
				<g clip-path="url(#gb)">
					<rect width="60" height="30" fill="#012169"/>
					<path d="M0,0 L60,30 M60,0 L0,30" stroke="#fff" stroke-width="6"/>
					<path d="M0,0 L60,30 M60,0 L0,30" stroke="#C8102E" stroke-width="4" clip-path="url(#gb)"/>
					<path d="M30,0V30M0,15H60" stroke="#fff" stroke-width="10"/>
					<path d="M30,0V30M0,15H60" stroke="#C8102E" stroke-width="6"/>
				</g>
			</svg>
			English
		</button>
		<button class="tab" class:active={lang === 'ru'} onclick={() => lang = 'ru'}>
			<svg class="flag" viewBox="0 0 60 30" width="24" height="12">
				<clipPath id="ru"><rect width="60" height="30" rx="2"/></clipPath>
				<g clip-path="url(#ru)">
					<rect width="60" height="10" fill="#fff"/>
					<rect y="10" width="60" height="10" fill="#0039A6"/>
					<rect y="20" width="60" height="10" fill="#D52B1E"/>
				</g>
			</svg>
			Русский
		</button>
	</div>
</div>

<style>
	.lang-tabs {
		display: flex;
		gap: .5rem;
	}

	.tab {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.375rem 0.875rem;
		border: solid 0.0625rem var(--bg-high);
		border-radius: var(--r);
		background: transparent;
		color: var(--dm);
		cursor: pointer;
		font-size: 0.8125rem;
		font-family: inherit;
		transition: .12s;
	}

	.tab:hover {
		color: var(--tx);
	}

	.tab.active {
		color: var(--ac);
		border: solid 0.0625rem var(--ac);
		font-weight: 600;
	}

	.flag {
		flex-shrink: 0;
	}
</style>
