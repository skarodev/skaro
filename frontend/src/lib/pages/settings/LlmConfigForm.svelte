<script>
	import { t } from '$lib/i18n/index.js';
	import { Eye, EyeOff } from 'lucide-svelte';
	import ProviderSelect from '$lib/ui/ProviderSelect.svelte';
	import ModelPicker from '$lib/ui/ModelPicker.svelte';

	let {
		provider = $bindable(''),
		model = $bindable(''),
		apiKey = $bindable(''),
		baseUrl = $bindable(''),
		maxTokens = $bindable(16384),
		temperature = $bindable(0.3),
		providerNames = [],
		presets = {},
		onProviderChange = () => {},
	} = $props();

	let needsKey = $derived(presets[provider]?.needs_key !== false);
	let masked = $state(true);
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
			<ModelPicker id="llm-model" bind:value={model} {provider} />
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
				max="200000"
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
		color: var(--tx-dim);
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
		color: var(--tx-dim);
		text-transform: uppercase;
		letter-spacing: 0.03rem;
		margin-bottom: 0.25rem;
		font-weight: 600;
	}

	.form-field input {
		width: 100%;
		padding: .7rem;
		background-color: var(--bg-deep);
		border: 0.0625rem solid var(--bg);
		border-radius: var(--r2);
		color: var(--tx);
		font-size: 1rem;
		font-family: var(--font-ui);
	}

	.form-field input:focus {
		outline: none;
		border-color: var(--ac);
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
		color: var(--tx-dim);
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
		color: var(--tx-dim);
		margin-top: 0.1875rem;
		opacity: .7;
	}
</style>
