<script>
	import { t } from '$lib/i18n/index.js';
	import { Eye, EyeOff } from 'lucide-svelte';
	import ProviderSelect from '$lib/ui/ProviderSelect.svelte';

	let {
		provider = $bindable(''),
		model = $bindable(''),
		apiKey = $bindable(''),
		baseUrl = $bindable(''),
		maxTokens = $bindable(16384),
		temperature = $bindable(0.3),
		providerNames = [],
		modelsFor = (p) => [],
		presets = {},
		onProviderChange = () => {},
	} = $props();

	let needsKey = $derived(presets[provider]?.needs_key !== false);
	let masked = $state(true);

	const OTHER = '__other__';
	let models = $derived(modelsFor(provider));
	let customMode = $state(false);
	let showCustom = $derived(customMode || (model && !models.includes(model)));
	let selectValue = $derived(showCustom ? OTHER : model);

	function onSelectModel(e) {
		const v = e.target.value;
		if (v === OTHER) {
			customMode = true;
			model = '';
		} else {
			customMode = false;
			model = v;
		}
	}

	// Reset custom mode when provider changes
	$effect(() => {
		provider;
		customMode = false;
	});
</script>

<div class="card">
	<h3>{$t('settings.default_llm')}</h3>
	<p class="card-desc">{$t('settings.default_llm_desc')}</p>

	<div class="form-grid-2">
		<div class="form-field">
			<label for="llm-provider">{$t('settings.provider')}</label>
			<ProviderSelect id="llm-provider" bind:value={provider} providers={providerNames} onchange={onProviderChange} />
		</div>
		<div class="form-field">
			<label for="llm-model">{$t('settings.model')}</label>
			<select id="llm-model" value={selectValue} onchange={onSelectModel}>
				{#each models as m}<option value={m}>{m}</option>{/each}
				<option value={OTHER}>Other…</option>
			</select>
			{#if showCustom}
				<input
					id="llm-model-custom"
					type="text"
					bind:value={model}
					placeholder="model-name"
					class="custom-model-input"
				/>
			{/if}
		</div>
	</div>

	<div class="form-grid-2">
		<div class="form-field">
			<label for="llm-api-key">{$t('settings.api_key')}</label>
			<div class="input-with-icon">
				<input
					id="llm-api-key"
					type={masked ? 'password' : 'text'}
					bind:value={apiKey}
					placeholder={$t('settings.api_key_placeholder')}
					disabled={!needsKey}
				/>
				{#if needsKey}
					<button type="button" class="icon-toggle" onclick={() => masked = !masked}>
						{#if masked}<Eye size={16} />{:else}<EyeOff size={16} />{/if}
					</button>
				{/if}
			</div>
			<span class="field-hint">{$t('settings.api_key_hint')}</span>
		</div>
		<div class="form-field">
			<label for="llm-base-url">{$t('settings.base_url')}</label>
			<input
				id="llm-base-url"
				type="text"
				bind:value={baseUrl}
				placeholder={$t('settings.base_url_placeholder')}
			/>
			<span class="field-hint">{$t('settings.base_url_hint')}</span>
		</div>
	</div>

	<div class="form-grid-2">
		<div class="form-field">
			<label for="llm-max-tokens">{$t('settings.max_tokens')}</label>
			<input
				id="llm-max-tokens"
				type="number"
				bind:value={maxTokens}
				min="256"
				max="2097152"
				step="256"
			/>
		</div>
		<div class="form-field">
			<label for="llm-temperature">{$t('settings.temperature')}</label>
			<input
				id="llm-temperature"
				type="number"
				bind:value={temperature}
				min="0"
				max="2"
				step="0.05"
			/>
		</div>
	</div>
</div>

<style>
	.card-desc {
		font-size: 0.8125rem;
		color: var(--dm);
		margin-bottom: 0.875rem;
	}

	.form-grid-2 {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 0.75rem;
		margin-bottom: 0.75rem;
	}

	.form-grid-2:last-child {
		margin-bottom: 0;
	}

	.form-field label {
		display: block;
		font-size: 0.6875rem;
		color: var(--dm);
		text-transform: uppercase;
		letter-spacing: 0.03rem;
		margin-bottom: 0.25rem;
		font-weight: 600;
	}

	.form-field input,
	.form-field select {
		width: 100%;
		padding: .7rem;
		background-color: var(--bg2);
		border: 0.0625rem solid var(--bg);
		border-radius: var(--r2);
		color: var(--tx);
		font-size: 1rem;
		font-family: var(--font-ui);
	}

	.form-field select {
		cursor: pointer;
	}

	.form-field input:focus,
	.form-field select:focus {
		outline: none;
		border-color: var(--ac);
	}

	.custom-model-input {
		margin-top: 0.375rem;
	}

	.form-field input:disabled {
		opacity: .4;
	}

	.input-with-icon {
		position: relative;
	}

	.input-with-icon input {
		padding-right: 2.5rem;
	}

	.icon-toggle {
		position: absolute;
		right: 0.5rem;
		top: 50%;
		transform: translateY(-50%);
		background: none;
		border: none;
		cursor: pointer;
		color: var(--dm);
		display: flex;
		align-items: center;
		padding: 0.25rem;
		border-radius: var(--r2);
		transition: color .15s;
	}

	.icon-toggle:hover {
		color: var(--tx-bright);
	}

	.field-hint {
		display: block;
		font-size: 0.625rem;
		color: var(--dm);
		margin-top: 0.1875rem;
		opacity: .7;
	}
</style>
