<script>
	import { t } from '$lib/i18n/index.js';
	import { Sun, Moon } from 'lucide-svelte';
	import BtnGroup from '$lib/ui/BtnGroup.svelte';

	let { theme = $bindable('dark') } = $props();

	let items = $derived([
		{ value: 'dark', label: $t('settings.theme_dark'), icon: Moon },
		{ value: 'light', label: $t('settings.theme_light'), icon: Sun },
	]);
</script>

<div class="card">
	<h3>{$t('settings.theme')}</h3>
	<BtnGroup {items} bind:value={theme} />
</div>
