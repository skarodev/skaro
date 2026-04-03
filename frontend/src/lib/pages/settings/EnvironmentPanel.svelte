<script>
	import { t } from '$lib/i18n/index.js';
	import { api } from '$lib/api/client.js';
	import { addError } from '$lib/stores/logStore.js';
	import { Container, Monitor, Terminal, Loader, Info, RefreshCw } from 'lucide-svelte';
	import BtnGroup from '$lib/ui/BtnGroup.svelte';

	let {
		mode = $bindable('host'),
		dockerService = $bindable(''),
		dockerComposeFile = $bindable(''),
		workdir = $bindable(''),
		commandPrefix = $bindable(''),
		shell = $bindable(''),
	} = $props();

	let detecting = $state(false);
	let detected = $state(null);

	let modeItems = $derived([
		{ value: 'host', label: $t('settings.env_mode_host'), icon: Monitor },
		{ value: 'docker', label: $t('settings.env_mode_docker'), icon: Container },
		{ value: 'custom', label: $t('settings.env_mode_custom'), icon: Terminal },
	]);

	async function detect() {
		detecting = true;
		try {
			detected = await api.detectEnv();
			if (detected.docker && detected.services?.length > 0) {
				mode = 'docker';
				dockerService = detected.services[0];
				dockerComposeFile = detected.compose_file || '';
			}
		} catch (e) {
			addError(e.message, 'env-detect');
		}
		detecting = false;
	}
</script>

<div class="card">
	<div class="card-header">
		<h3>{$t('settings.env_title')}</h3>
		<button class="btn btn-sm btn-ghost" onclick={detect} disabled={detecting} title={$t('settings.env_detect')}>
			{#if detecting}<Loader size={14} class="spin" />{:else}<RefreshCw size={14} />{/if}
			{$t('settings.env_detect')}
		</button>
	</div>
	<p class="card-desc">{$t('settings.env_desc')}</p>

	{#if detected?.docker}
		<div class="hint">
			<Info size={14} />
			<span>
				{$t('settings.env_docker_detected')}
				{#if detected.services?.length > 0}
					— services: <strong>{detected.services.join(', ')}</strong>
				{/if}
			</span>
		</div>
	{/if}

	<div class="form-field">
		<span class="field-label">{$t('settings.env_mode')}</span>
		<BtnGroup items={modeItems} bind:value={mode} />
	</div>

	{#if mode === 'docker'}
		<div class="form-grid-2">
			<div class="form-field">
				<label for="docker-service">{$t('settings.env_docker_service')}</label>
				{#if detected?.services?.length > 0}
					<select id="docker-service" bind:value={dockerService}>
						{#each detected.services as svc}
							<option value={svc}>{svc}</option>
						{/each}
					</select>
				{:else}
					<input id="docker-service" type="text" bind:value={dockerService} placeholder="app" />
				{/if}
			</div>
			<div class="form-field">
				<label for="compose-file">{$t('settings.env_compose_file')}</label>
				<input id="compose-file" type="text" bind:value={dockerComposeFile} placeholder="docker-compose.yml" />
			</div>
		</div>
		<div class="form-grid-2">
			<div class="form-field">
				<label for="workdir">{$t('settings.env_workdir')}</label>
				<input id="workdir" type="text" bind:value={workdir} placeholder="/app" />
			</div>
			<div class="form-field">
				<label for="shell">{$t('settings.env_shell')}</label>
				<input id="shell" type="text" bind:value={shell} placeholder="sh" />
				<span class="field-hint">{$t('settings.env_shell_hint')}</span>
			</div>
		</div>
	{:else if mode === 'custom'}
		<div class="form-field">
			<label for="command-prefix">{$t('settings.env_command_prefix')}</label>
			<input id="command-prefix" type="text" bind:value={commandPrefix} placeholder="ssh user@host" />
			<span class="field-hint">{$t('settings.env_command_prefix_hint')}</span>
		</div>
	{:else}
		<p class="mode-desc">{$t('settings.env_host_desc')}</p>
	{/if}
</div>

<style>
	.card-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		margin-bottom: 0.25rem;
	}

	.card-header h3 {
		margin: 0;
	}

	.card-desc {
		font-size: 0.8125rem;
		color: var(--tx-dim);
		margin-bottom: 0.875rem;
	}

	.hint {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.625rem 0.75rem;
		background: color-mix(in srgb, var(--ac) 8%, transparent);
		border: 0.0625rem solid color-mix(in srgb, var(--ac) 25%, transparent);
		border-radius: var(--r2);
		font-size: 0.8125rem;
		color: var(--tx);
		margin-bottom: 0.875rem;
	}

	.hint :global(svg) {
		color: var(--ac);
		flex-shrink: 0;
	}

	.form-grid-2 {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 0.75rem;
		margin-top: 0.75rem;
	}

	.form-field {
		margin-top: 0.75rem;
	}

	.form-grid-2 .form-field {
		margin-top: 0;
	}

	.form-field label,
	.form-field .field-label {
		display: block;
		font-size: 0.6875rem;
		color: var(--tx-dim);
		text-transform: uppercase;
		letter-spacing: 0.03rem;
		margin-bottom: 0.25rem;
		font-weight: 600;
	}

	.form-field input,
	.form-field select {
		width: 100%;
		padding: .7rem;
		background-color: var(--bg-deep);
		border: 0.0625rem solid var(--bg);
		border-radius: var(--r2);
		color: var(--tx);
		font-size: 1rem;
		font-family: var(--font-ui);
	}

	.form-field input:focus,
	.form-field select:focus {
		outline: none;
		border-color: var(--ac);
	}

	.field-hint {
		display: block;
		font-size: 0.75rem;
		color: var(--tx-dim);
		margin-top: 0.25rem;
	}

	.mode-desc {
		font-size: 0.8125rem;
		color: var(--tx-dim);
		margin-top: 0.5rem;
	}

	.btn-sm {
		padding: 0.3rem 0.625rem;
		font-size: 0.75rem;
	}

	.btn-ghost {
		display: flex;
		align-items: center;
		gap: 0.375rem;
		background: transparent;
		border: 0.0625rem solid var(--bg-high);
		border-radius: var(--r);
		color: var(--tx-dim);
		cursor: pointer;
		font-family: inherit;
		transition: .12s;
	}

	.btn-ghost:hover {
		color: var(--tx);
		border-color: var(--tx);
	}
</style>
