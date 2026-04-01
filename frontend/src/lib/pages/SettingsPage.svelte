<script>
	import { onMount } from 'svelte';
	import { t, setLocale } from '$lib/i18n/index.js';
	import { api } from '$lib/api/client.js';
	import { status } from '$lib/stores/statusStore.js';
	import { addLog, addError } from '$lib/stores/logStore.js';
	import { cachedFetch, invalidate } from '$lib/api/cache.js';
	import { Settings, Compass, Code, Search, Check, Loader } from 'lucide-svelte';
	import LlmConfigForm from '$lib/pages/settings/LlmConfigForm.svelte';
	import RoleCard from '$lib/pages/settings/RoleCard.svelte';
	import LanguagePicker from '$lib/pages/settings/LanguagePicker.svelte';
	import ThemePicker from '$lib/pages/settings/ThemePicker.svelte';
	import SkillsPanel from '$lib/pages/settings/SkillsPanel.svelte';
	import EnvironmentPanel from '$lib/pages/settings/EnvironmentPanel.svelte';
	import { setTheme } from '$lib/stores/themeStore.js';
	import { setProviderLabelsFromPresets } from '$lib/ui/icons/providers.js';

	let config = $state(null);
	let presets = $state({});
	let saving = $state(false);
	let saved = $state(false);
	let error = $state('');
	let activeTab = $state('general');

	const roles = [
		{ id: 'architect', icon: Compass, labelKey: 'settings.role_architect', descKey: 'settings.role_architect_desc', color: 'var(--ac)' },
		{ id: 'coder', icon: Code, labelKey: 'settings.role_coder', descKey: 'settings.role_coder_desc', color: 'var(--ok)' },
		{ id: 'reviewer', icon: Search, labelKey: 'settings.role_reviewer', descKey: 'settings.role_reviewer_desc', color: 'var(--warn)' },
	];

	let tabs = $derived([
		{ id: 'general', label: $t('settings.tab_general') },
		{ id: 'llm', label: $t('settings.tab_llm') },
		{ id: 'roles', label: $t('settings.tab_roles') },
		{ id: 'environment', label: $t('settings.tab_environment') },
		{ id: 'skills', label: $t('settings.tab_skills') },
	]);

	let projectName = $state('');
	let projectDescription = $state('');
	let llm = $state({ provider: '', model: '', api_key: '', base_url: '', max_tokens: 16384, temperature: 0.3 });
	let roleOverrides = $state({
		architect: { enabled: false, provider: '', model: '', api_key: '', base_url: '', max_tokens: '', temperature: '' },
		coder: { enabled: false, provider: '', model: '', api_key: '', base_url: '', max_tokens: '', temperature: '' },
		reviewer: { enabled: false, provider: '', model: '', api_key: '', base_url: '', max_tokens: '', temperature: '' },
	});
	let lang = $state('en');
	let theme = $state('dark');
	let uiAutoOpen = $state(true);
	// Execution environment
	let envMode = $state('host');
	let envDockerService = $state('');
	let envDockerComposeFile = $state('');
	let envWorkdir = $state('');
	let envCommandPrefix = $state('');
	let envShell = $state('');
	// Provider names come from the backend (providers.yaml)
	let providerNames = $derived(config?._provider_keys || Object.keys(presets));

	onMount(async () => {
		try {
			config = await cachedFetch('config', () => api.getConfig());
			presets = config._provider_presets || {};
			setProviderLabelsFromPresets(presets);
			projectName = config.project_name || '';
			projectDescription = config.project_description || '';
			llm = {
				provider: config.llm?.provider || 'anthropic',
				model: config.llm?.model || '',
				api_key: config.llm?.api_key || '',
				base_url: config.llm?.base_url || '',
				max_tokens: config.llm?.max_tokens || 16384,
				temperature: config.llm?.temperature ?? 0.3,
			};
			lang = config.lang || 'en';
			theme = config.theme || 'dark';
			uiAutoOpen = config.ui?.auto_open_browser ?? true;
			const execEnv = config.execution_env || {};
			envMode = execEnv.mode || 'host';
			envDockerService = execEnv.docker_service || '';
			envDockerComposeFile = execEnv.docker_compose_file || '';
			envWorkdir = execEnv.workdir || '';
			envCommandPrefix = execEnv.command_prefix || '';
			envShell = execEnv.shell || '';
			for (const r of roles) {
				const rd = config.roles?.[r.id];
				roleOverrides[r.id] = rd?.provider && rd?.model
					? { enabled: true, provider: rd.provider, model: rd.model, api_key: rd.api_key || '', base_url: rd.base_url || '', max_tokens: rd.max_tokens ?? '', temperature: rd.temperature ?? '' }
					: { enabled: false, provider: llm.provider, model: '', api_key: '', base_url: '', max_tokens: '', temperature: '' };
			}
		} catch (e) { error = e.message; addError(e.message, 'settings'); }
	});

	function onProviderChange() {
		// Reset model to provider default when switching providers
		const preset = presets[llm.provider];
		llm.model = preset?.model || '';
	}

	function onRoleProviderChange(rid) {
		const preset = presets[roleOverrides[rid].provider];
		roleOverrides[rid].model = preset?.model || '';
	}

	async function save() {
		saving = true; saved = false; error = '';
		try {
			const payload = {
				llm: {
					provider: llm.provider,
					model: llm.model,
					api_key: llm.api_key,
					base_url: llm.base_url || null,
					max_tokens: Number(llm.max_tokens) || 16384,
					temperature: Number(llm.temperature) ?? 0.3,
				},
				ui: {
					auto_open_browser: uiAutoOpen,
				},
				lang,
				theme,
				project_name: projectName,
				project_description: projectDescription,
				roles: {},
				execution_env: {
					mode: envMode,
					docker_service: envDockerService,
					docker_compose_file: envDockerComposeFile,
					workdir: envWorkdir,
					command_prefix: envCommandPrefix,
					shell: envShell,
				},
			};
			for (const r of roles) {
				const ro = roleOverrides[r.id];
				if (ro.enabled && ro.provider && ro.model) {
					payload.roles[r.id] = {
						provider: ro.provider,
						model: ro.model,
						api_key: ro.api_key || null,
						base_url: ro.base_url || null,
						max_tokens: ro.max_tokens !== '' ? Number(ro.max_tokens) : null,
						temperature: ro.temperature !== '' ? Number(ro.temperature) : null,
					};
				} else {
					payload.roles[r.id] = null;
				}
			}
			await api.saveConfig(payload);
			setLocale(lang);
			setTheme(theme);
			invalidate('config', 'status');
			status.set(await api.getStatus());
			addLog('Settings saved');
			saved = true;
			setTimeout(() => saved = false, 3000);
		} catch (e) { error = e.message; addError(e.message, 'settings'); }
		saving = false;
	}
</script>

<div class="page-with-tabs">
	<div class="main-header">
		<h2><Settings size={24} /> {$t('settings.title')}</h2>
		<p>{$t('settings.subtitle')}</p>
	</div>

	{#if !config}
		<div class="loading-text"><Loader size={14} class="spin" /> {$t('app.loading')}</div>
	{:else}
		<div class="settings-tabs-layout">
			<nav class="settings-tabs-nav">
				{#each tabs as tab}
					<button
						class="tab-item"
						class:active={activeTab === tab.id}
						onclick={() => activeTab = tab.id}
					>
						{tab.label}
					</button>
				{/each}
			</nav>

			<div class="settings-tabs-content">
				{#if activeTab === 'general'}
					<!-- Project info -->
					<div class="card">
						<h3>{$t('settings.project_title')}</h3>
						<div class="form-grid-2">
							<div class="form-field">
								<label for="project-name">{$t('settings.project_name')}</label>
								<input id="project-name" type="text" bind:value={projectName} placeholder={$t('settings.project_name_placeholder')} />
							</div>
							<div class="form-field">
								<label for="project-desc">{$t('settings.project_description')}</label>
								<input id="project-desc" type="text" bind:value={projectDescription} placeholder={$t('settings.project_description_placeholder')} />
							</div>
						</div>
					</div>

					<!-- UI settings -->
					<div class="card">
						<h3>{$t('settings.ui_title')}</h3>
						<div class="form-field checkbox-field">
							<label class="checkbox-label">
								<input type="checkbox" bind:checked={uiAutoOpen} />
								<span>{$t('settings.auto_open_browser')}</span>
							</label>
						</div>
					</div>

					<!-- Language -->
					<LanguagePicker bind:lang />

					<!-- Theme -->
					<ThemePicker bind:theme />
				{:else if activeTab === 'llm'}
					<LlmConfigForm
						bind:provider={llm.provider}
						bind:model={llm.model}
						bind:apiKey={llm.api_key}
						bind:baseUrl={llm.base_url}
						bind:maxTokens={llm.max_tokens}
						bind:temperature={llm.temperature}
						{providerNames} {presets}
						onProviderChange={onProviderChange}
					/>
				{:else if activeTab === 'roles'}
					<div class="card">
						<h3>{$t('settings.roles_title')}</h3>
						<p class="card-desc">{$t('settings.roles_desc')}</p>
						<div class="roles-list">
							{#each roles as role}
								<RoleCard
									{role}
									bind:override={roleOverrides[role.id]}
									defaultProvider={llm.provider}
									defaultModel={llm.model}
									{providerNames}
									onProviderChange={() => onRoleProviderChange(role.id)}
								/>
							{/each}
						</div>
					</div>
				{:else if activeTab === 'skills'}
					<div class="card">
						<h3>{$t('settings.skills_title')}</h3>
						<p class="card-desc">{$t('settings.skills_desc')}</p>
						<SkillsPanel />
					</div>
				{:else if activeTab === 'environment'}
					<EnvironmentPanel
						bind:mode={envMode}
						bind:dockerService={envDockerService}
						bind:dockerComposeFile={envDockerComposeFile}
						bind:workdir={envWorkdir}
						bind:commandPrefix={envCommandPrefix}
						bind:shell={envShell}
					/>
				{/if}

				<!-- Save (visible in all tabs except skills which manages its own state) -->
				{#if activeTab !== 'skills'}
				<div class="save-row">
					<button class="btn btn-primary" onclick={save} disabled={saving}>
						{#if saving}<Loader size={14} class="spin" /> {$t('settings.saving')}
						{:else}<Check size={14} /> {$t('settings.save')}{/if}
					</button>
					{#if saved}<span class="save-ok">{$t('settings.saved')}</span>{/if}
					{#if error}<span class="save-err">{$t('settings.error')}: {error}</span>{/if}
				</div>
				{/if}
			</div>
		</div>
	{/if}
</div>

<style>
	.settings-tabs-layout {
		display: flex;
		gap: 1.5rem;
		margin-top: 1.5rem;
	}

	.settings-tabs-nav {
		position: sticky;
		top: 0;
		width: 14rem;
		flex-shrink: 0;
		align-self: flex-start;
		display: flex;
		flex-direction: column;
		gap: .2rem;
		padding: 0;
		padding-top: 1rem;
	}

	.tab-item {
		display: flex;
		align-items: center;
		width: 100%;
		padding: .75rem;
		border: none;
		border-radius: var(--r);
		background: none;
		color: var(--tx-bright);
		font-size: 1rem;
		font-family: inherit;
		text-align: left;
		cursor: pointer;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
		transition: background .1s;
	}

	.tab-item:hover {
		background: var(--bg-deep);
	}

	.tab-item.active {
		background: var(--bg-deep);
		color: var(--tx-bright);
	}

	.settings-tabs-content {
		flex: 1;
		min-width: 0;
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
	}

	.card-desc {
		font-size: 0.8125rem;
		color: var(--tx-dim);
		margin-bottom: 0.875rem;
	}

	.form-grid-2 {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 0.75rem;
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

	.checkbox-field {
		display: flex;
		align-items: center;
	}

	.checkbox-field .checkbox-label {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		cursor: pointer;
		font-size: 0.875rem;
		font-weight: 400;
		text-transform: none;
		letter-spacing: 0;
		color: var(--tx);
		margin-bottom: 0;
	}

	.checkbox-label input[type="checkbox"] {
		width: 1.125rem;
		height: 1.125rem;
		padding: 0;
		accent-color: var(--ac);
		cursor: pointer;
	}

	.roles-list {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
	}

	.save-row {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		margin-top: 0.5rem;
		margin-bottom: 1.5rem;
	}

	.save-ok {
		color: var(--ok);
		font-size: 0.8125rem;
	}

	.save-err {
		color: var(--err);
		font-size: 0.8125rem;
	}
</style>
