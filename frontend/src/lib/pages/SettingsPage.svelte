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
	import { setTheme } from '$lib/stores/themeStore.js';

	let config = $state(null);
	let presets = $state({});
	let saving = $state(false);
	let saved = $state(false);
	let error = $state('');
	let activeTab = $state('general');

	const PROVIDER_MODELS = {
		anthropic: ['claude-sonnet-4-6', 'claude-opus-4-6', 'claude-sonnet-4-5-20250929', 'claude-opus-4-5-20251120', 'claude-haiku-4-5-20251001'],
		openai: ['gpt-5.2', 'gpt-5', 'gpt-5-mini', 'gpt-5-nano', 'gpt-4.1', 'gpt-4.1-mini', 'gpt-4.1-nano', 'o3', 'o4-mini', 'gpt-4o'],
		groq: ['openai/gpt-oss-120b', 'openai/gpt-oss-20b', 'llama-3.3-70b-versatile', 'llama-3.1-8b-instant', 'meta-llama/llama-4-scout-17b-16e-instruct', 'meta-llama/llama-4-maverick-17b-128e-instruct', 'qwen/qwen3-32b', 'moonshotai/kimi-k2-instruct-0905', 'deepseek-r1-distill-llama-70b'],
		ollama: ['llama3.3', 'llama4:scout', 'qwen3', 'qwen3-coder', 'deepseek-v3', 'deepseek-r1', 'mistral', 'codellama', 'phi4', 'gemma3'],
	};

	const roles = [
		{ id: 'architect', icon: Compass, labelKey: 'settings.role_architect', descKey: 'settings.role_architect_desc', color: 'var(--ac)' },
		{ id: 'coder', icon: Code, labelKey: 'settings.role_coder', descKey: 'settings.role_coder_desc', color: 'var(--gn-bright)' },
		{ id: 'reviewer', icon: Search, labelKey: 'settings.role_reviewer', descKey: 'settings.role_reviewer_desc', color: 'var(--yl)' },
	];

	let tabs = $derived([
		{ id: 'general', label: $t('settings.tab_general') },
		{ id: 'llm', label: $t('settings.tab_llm') },
		{ id: 'roles', label: $t('settings.tab_roles') },
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
	const providerNames = Object.keys(PROVIDER_MODELS);

	onMount(async () => {
		try {
			config = await cachedFetch('config', () => api.getConfig());
			presets = config._provider_presets || {};
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
			for (const r of roles) {
				const rd = config.roles?.[r.id];
				roleOverrides[r.id] = rd?.provider && rd?.model
					? { enabled: true, provider: rd.provider, model: rd.model, api_key: rd.api_key || '', base_url: rd.base_url || '', max_tokens: rd.max_tokens ?? '', temperature: rd.temperature ?? '' }
					: { enabled: false, provider: llm.provider, model: '', api_key: '', base_url: '', max_tokens: '', temperature: '' };
			}
		} catch (e) { error = e.message; addError(e.message, 'settings'); }
	});

	function modelsFor(provider) { return PROVIDER_MODELS[provider] || []; }

	function onProviderChange() {
		llm.model = modelsFor(llm.provider)[0] || '';
	}

	function onRoleProviderChange(rid) {
		roleOverrides[rid].model = modelsFor(roleOverrides[rid].provider)[0] || '';
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
						{providerNames} {modelsFor} {presets}
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
									{providerNames} {modelsFor}
									onProviderChange={() => onRoleProviderChange(role.id)}
								/>
							{/each}
						</div>
					</div>
				{/if}

				<!-- Save (visible in all tabs) -->
				<div class="save-row">
					<button class="btn btn-primary" onclick={save} disabled={saving}>
						{#if saving}<Loader size={14} class="spin" /> {$t('settings.saving')}
						{:else}<Check size={14} /> {$t('settings.save')}{/if}
					</button>
					{#if saved}<span class="save-ok">{$t('settings.saved')}</span>{/if}
					{#if error}<span class="save-err">{$t('settings.error')}: {error}</span>{/if}
				</div>
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
		background: var(--bg2);
	}

	.tab-item.active {
		background: var(--bg2);
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
		color: var(--dm);
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
		color: var(--dm);
		text-transform: uppercase;
		letter-spacing: 0.03rem;
		margin-bottom: 0.25rem;
		font-weight: 600;
	}

	.form-field input {
		width: 100%;
		padding: .7rem;
		background-color: var(--bg2);
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
		color: var(--gn-bright);
		font-size: 0.8125rem;
	}

	.save-err {
		color: var(--rd);
		font-size: 0.8125rem;
	}
</style>
