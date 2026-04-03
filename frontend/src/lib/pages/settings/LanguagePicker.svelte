<script>
	import { t } from '$lib/i18n/index.js';
	import BtnGroup from '$lib/ui/BtnGroup.svelte';

	let { lang = $bindable('en') } = $props();

	const items = [
		{ value: 'en', label: 'English' },
		{ value: 'ru', label: 'Русский' },
	];
</script>

<div class="card">
	<h3>{$t('settings.language')}</h3>
	<BtnGroup {items} bind:value={lang}>
		{#snippet item(it)}
			{#if it.value === 'en'}
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
			{:else}
				<svg class="flag" viewBox="0 0 60 30" width="24" height="12">
					<clipPath id="ru"><rect width="60" height="30" rx="2"/></clipPath>
					<g clip-path="url(#ru)">
						<rect width="60" height="10" fill="#fff"/>
						<rect y="10" width="60" height="10" fill="#0039A6"/>
						<rect y="20" width="60" height="10" fill="#D52B1E"/>
					</g>
				</svg>
			{/if}
			{it.label}
		{/snippet}
	</BtnGroup>
</div>

<style>
	.flag {
		flex-shrink: 0;
	}
</style>
