<script>
	import { t } from '$lib/i18n/index.js';
	import { Eye, EyeOff } from 'lucide-svelte';
	import ProviderSelect from '$lib/ui/ProviderSelect.svelte';

	let {
		role = {},
		override = $bindable({ enabled: false, provider: '', model: '', api_key: '', base_url: '', max_tokens: '', temperature: '' }),
		defaultProvider = '',
		defaultModel = '',
		providerNames = [],
		modelsFor = (p) => [],
		onProviderChange = () => {},
	} = $props();

	function toggle() {
		override.enabled = !override.enabled;
		if (override.enabled && !override.provider) {
			override.provider = defaultProvider;
			override.model = defaultModel;
		}
	}

	let Icon = $derived(role.icon);
	let needsKey = $derived(override.enabled && override.provider !== defaultProvider);
	let masked = $state(true);
	let keyId = $derived(`role-${role.id}-key`);
	let baseUrlId = $derived(`role-${role.id}-base-url`);
	let maxTokensId = $derived(`role-${role.id}-max-tokens`);
	let tempId = $derived(`role-${role.id}-temperature`);

	const OTHER = '__other__';
	let models = $derived(modelsFor(override.provider));
	let customMode = $state(false);
	let showCustom = $derived(customMode || (override.model && !models.includes(override.model)));
	let selectValue = $derived(showCustom ? OTHER : override.model);

	function onSelectModel(e) {
		const v = e.target.value;
		if (v === OTHER) {
			customMode = true;
			override.model = '';
		} else {
			customMode = false;
			override.model = v;
		}
	}
</script>

<div class="role-card">
	<button type="button" class="role-header" onclick={toggle}>
		<div class="role-icon" style="color: {role.color}">
			<Icon size={22} />
		</div>
		<div class="role-info">
			<div class="role-name">{$t(role.labelKey)}</div>
			<div class="role-desc">{$t(role.descKey)}</div>
		</div>
		<div class="role-toggle" class:on={override.enabled}>
			<div class="toggle-thumb"></div>
		</div>
	</button>
	{#if override.enabled}
		<div class="role-body">
			<div class="form-row">
				<div class="form-field">
					<label for={`role-${role.id}-provider`}>{$t('settings.provider')}</label>
					<ProviderSelect id={`role-${role.id}-provider`} bind:value={override.provider} providers={providerNames} onchange={onProviderChange} />
				</div>
				<div class="form-field">
					<label for={`role-${role.id}-model`}>{$t('settings.model')}</label>
					<select id={`role-${role.id}-model`} value={selectValue} onchange={onSelectModel}>
						{#each models as m}<option value={m}>{m}</option>{/each}
						<option value={OTHER}>Other…</option>
					</select>
					{#if showCustom}
						<input
							type="text"
							bind:value={override.model}
							placeholder="model-name"
							class="custom-model-input"
						/>
					{/if}
				</div>
			</div>
			<div class="form-row">
				<div class="form-field">
					<label for={keyId}>{$t('settings.api_key')}</label>
					<div class="input-with-icon">
						<input
							id={keyId}
							type={masked ? 'password' : 'text'}
							bind:value={override.api_key}
							placeholder={needsKey ? $t('settings.api_key_placeholder') : $t('settings.use_default')}
						/>
						{#if override.api_key}
							<button type="button" class="icon-toggle" onclick={() => masked = !masked}>
								{#if masked}<Eye size={14} />{:else}<EyeOff size={14} />{/if}
							</button>
						{/if}
					</div>
				</div>
				<div class="form-field">
					<label for={baseUrlId}>{$t('settings.base_url')}</label>
					<input
						id={baseUrlId}
						type="text"
						bind:value={override.base_url}
						placeholder={$t('settings.use_default')}
					/>
				</div>
			</div>
			<div class="form-row">
				<div class="form-field">
					<label for={maxTokensId}>{$t('settings.max_tokens')}</label>
					<input
						id={maxTokensId}
						type="number"
						bind:value={override.max_tokens}
						min="256"
						max="2097152"
						step="256"
						placeholder={$t('settings.use_default')}
					/>
				</div>
				<div class="form-field">
					<label for={tempId}>{$t('settings.temperature')}</label>
					<input
						id={tempId}
						type="number"
						bind:value={override.temperature}
						min="0"
						max="2"
						step="0.05"
						placeholder={$t('settings.use_default')}
					/>
				</div>
			</div>
		</div>
	{:else}
		<div class="role-default">{$t('settings.use_default')}: {defaultProvider} / {defaultModel}</div>
	{/if}
</div>

<style>
	.role-card {
		border: 0.0625rem solid var(--bd);
		border-radius: var(--r);
		overflow: visible;
	}

	.role-header {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		padding: 0.75rem;
		cursor: pointer;
		width: 100%;
		background: none;
		border: none;
		border-radius: var(--r);
		color: inherit;
		font: inherit;
		text-align: left;
	}

	.role-icon {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 2.5rem;
		height: 2.5rem;
		background: rgba(255, 255, 255, .05);
		border-radius: 0.5rem;
		flex-shrink: 0;
	}

	.role-info {
		flex: 1;
		min-width: 0;
	}

	.role-name {
		font-size: 0.875rem;
		font-weight: 600;
		color: var(--tx-bright);
	}

	.role-desc {
		font-size: 0.75rem;
		color: var(--dm);
		margin-top: 0.0625rem;
	}

	.role-toggle {
		width: 2.25rem;
		height: 1.25rem;
		border-radius: 0.625rem;
		background: var(--bd2);
		position: relative;
		flex-shrink: 0;
		transition: background .15s;
	}

	.role-toggle.on {
		background: var(--ac2);
	}

	.toggle-thumb {
		width: 1rem;
		height: 1rem;
		border-radius: 50%;
		background: #fff;
		position: absolute;
		top: 0.125rem;
		left: 0.125rem;
		transition: transform .15s;
	}

	.role-toggle.on .toggle-thumb {
		transform: translateX(1rem);
	}

	.role-body {
		padding: 0 0.75rem 0.75rem;
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}

	.form-row {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 0.5rem;
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

	.form-field select,
	.form-field input {
		width: 100%;
		padding: .7rem;
		background-color: var(--bg2);
		border: 0.0625rem solid var(--bg);
		border-radius: var(--r2);
		color: var(--tx);
		font-size: 1rem;
		font-family: var(--font-ui);
		cursor: pointer;
	}

	.form-field input {
		cursor: text;
	}

	.form-field select:focus,
	.form-field input:focus {
		outline: none;
		border-color: var(--ac);
	}

	.custom-model-input {
		margin-top: 0.375rem;
	}

	.input-with-icon {
		position: relative;
	}

	.input-with-icon input {
		padding-right: 2.25rem;
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

	.role-default {
		padding: 0 0.75rem 0.625rem;
		font-size: 0.75rem;
		color: var(--dm);
		font-family: var(--font-ui);
	}
</style>
