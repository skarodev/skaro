<script>
	import { t } from '$lib/i18n/index.js';
	import { Sun, Moon } from 'lucide-svelte';
	import BtnGroup from '$lib/ui/BtnGroup.svelte';
	import { ACCENT_PRESETS, accentColor, setAccentColor } from '$lib/stores/themeStore.js';

	let { theme = $bindable('dark') } = $props();

	let items = $derived([
		{ value: 'dark', label: $t('settings.theme_dark'), icon: Moon },
		{ value: 'light', label: $t('settings.theme_light'), icon: Sun },
	]);

	let currentAccent = $state('');
	let customHex = $state('');
	let isCustom = $state(false);

	// Sync from store
	accentColor.subscribe(v => {
		currentAccent = v;
		const preset = ACCENT_PRESETS.find(p => p.hex === v);
		isCustom = !preset;
		if (isCustom) customHex = v;
	});

	function selectPreset(hex) {
		isCustom = false;
		customHex = '';
		setAccentColor(hex);
	}

	function enableCustom() {
		isCustom = true;
		customHex = currentAccent;
	}

	function applyCustom() {
		const hex = customHex.trim();
		if (/^#[0-9a-fA-F]{6}$/.test(hex)) {
			setAccentColor(hex);
		}
	}

	function handleCustomInput(e) {
		customHex = e.target.value;
		if (/^#[0-9a-fA-F]{6}$/.test(customHex)) {
			setAccentColor(customHex);
		}
	}
</script>

<div class="card">
	<h3>{$t('settings.theme')}</h3>
	<BtnGroup {items} bind:value={theme} />

	<div class="accent-section">
		<h4>{$t('settings.accent_color')}</h4>
		<div class="accent-grid">
			{#each ACCENT_PRESETS as preset}
				<button
					class="accent-swatch"
					class:active={!isCustom && currentAccent === preset.hex}
					style="--swatch: {preset.hex}"
					onclick={() => selectPreset(preset.hex)}
				>
					<span class="swatch-dot"></span>
					<span class="swatch-label">{$t(preset.label)}</span>
				</button>
			{/each}
			<button
				class="accent-swatch"
				class:active={isCustom}
				style="--swatch: {isCustom ? customHex || '#888' : '#888'}"
				onclick={enableCustom}
			>
				<span class="swatch-dot swatch-custom-dot">?</span>
				<span class="swatch-label">{$t('accent.custom')}</span>
			</button>
		</div>

		{#if isCustom}
			<div class="custom-hex-row">
				<input
					type="text"
					class="hex-input"
					value={customHex}
					oninput={handleCustomInput}
					placeholder="#000000"
					maxlength="7"
				/>
				<div class="hex-preview" style="background: {customHex}"></div>
			</div>
		{/if}
	</div>
</div>

<style>
	.accent-section {
		margin-top: 1rem;
	}

	.accent-section h4 {
		font-size: 0.6875rem;
		color: var(--tx-dim);
		text-transform: uppercase;
		letter-spacing: 0.03rem;
		margin-bottom: 0.5rem;
		font-weight: 600;
	}

	.accent-grid {
		display: flex;
		flex-wrap: wrap;
		gap: 0.375rem;
	}

	.accent-swatch {
		display: flex;
		align-items: center;
		gap: 0.375rem;
		padding: 0.375rem 0.625rem;
		border: 1px solid var(--bd);
		border-radius: var(--r);
		background: var(--bg-deep);
		cursor: pointer;
		font-family: inherit;
		font-size: 0.8125rem;
		color: var(--tx);
		transition: border-color 0.12s, background 0.12s;
	}

	.accent-swatch:hover {
		border-color: var(--swatch);
		background: var(--bg-high);
	}

	.accent-swatch.active {
		border-color: var(--swatch);
		box-shadow: 0 0 0 1px var(--swatch);
	}

	.swatch-dot {
		width: 0.875rem;
		height: 0.875rem;
		border-radius: 50%;
		background: var(--swatch);
		flex-shrink: 0;
	}

	.swatch-custom-dot {
		display: flex;
		align-items: center;
		justify-content: center;
		font-size: 0.625rem;
		font-weight: 700;
		color: #fff;
		background: var(--swatch);
	}

	.swatch-label {
		white-space: nowrap;
	}

	.custom-hex-row {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		margin-top: 0.5rem;
	}

	.hex-input {
		width: 7rem;
		padding: 0.4rem 0.625rem;
		background: var(--bg-deep);
		border: 1px solid var(--bd);
		border-radius: var(--r2);
		color: var(--tx);
		font-family: var(--font-ui);
		font-size: 0.875rem;
	}

	.hex-input:focus {
		outline: none;
		border-color: var(--ac);
	}

	.hex-preview {
		width: 1.5rem;
		height: 1.5rem;
		border-radius: var(--r2);
		border: 1px solid var(--bd);
		flex-shrink: 0;
	}
</style>
