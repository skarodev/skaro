<script>
	import { onMount } from 'svelte';
	import { t } from '$lib/i18n/index.js';
	import { api } from '$lib/api/client.js';
	import { addLog, addError } from '$lib/stores/logStore.js';
	import { Loader2, CheckCircle, XCircle, Circle, ChevronDown, ChevronUp, Zap } from 'lucide-svelte';
	import Tooltip from '$lib/ui/Tooltip.svelte';

	let skills = $state(/** @type {any[]} */ ([]));
	let preset = $state('');
	let loading = $state(true);
	let saving = $state(false);
	let expanded = $state(/** @type {string|null} */ (null));
	let expandedDetail = $state(/** @type {any|null} */ (null));
	let loadingDetail = $state(false);

	onMount(() => { load(); });

	async function load() {
		loading = true;
		try {
			const res = await api.getSkills();
			skills = res.skills ?? [];
			preset = res.preset || '';
		} catch (e) { addError(e.message, 'skills'); }
		loading = false;
	}

	async function toggleSkill(name, currentStatus, source) {
		saving = true;
		try {
			const active = [];
			const disabled = [];
			for (const s of skills) {
				if (s.name === name) {
					if (currentStatus === 'active') {
						// Deactivate: preset skills go to disabled, others just removed from active
						if (s.source === 'preset') disabled.push(name);
					} else {
						// Activate: preset skills remove from disabled, others add to active
						if (s.source === 'preset') {
							// Don't add to disabled — that's enough to re-enable
						} else {
							active.push(name);
						}
					}
				} else {
					// Preserve existing state for other skills
					if (s.status === 'active' && s.source !== 'preset') active.push(s.name);
					if (s.status === 'disabled') disabled.push(s.name);
				}
			}
			await api.updateActiveSkills(active, disabled);
			await load();
			addLog(`Skill '${name}' ${currentStatus === 'active' ? 'disabled' : 'enabled'}`);
		} catch (e) { addError(e.message, 'skillToggle'); }
		saving = false;
	}

	async function toggleExpand(name) {
		if (expanded === name) {
			expanded = null;
			expandedDetail = null;
			return;
		}
		expanded = name;
		expandedDetail = null;
		loadingDetail = true;
		try {
			expandedDetail = await api.getSkill(name);
		} catch (e) { addError(e.message, 'skillDetail'); }
		loadingDetail = false;
	}
</script>

{#if loading}
	<div class="loading-text"><Loader2 size={14} class="spin" /> {$t('app.loading')}</div>
{:else}
	{#if preset}
		<div class="skills-preset-badge">
			<Zap size={14} />
			<span>{$t('settings.skills_preset')}: <strong>{preset}</strong></span>
		</div>
	{/if}

	{#if skills.length === 0}
		<p class="skills-empty">{$t('settings.skills_empty')}</p>
	{:else}
		<div class="skills-list">
			{#each skills as skill}
				<div class="skill-item" class:expanded={expanded === skill.name}>
					<div class="skill-header">
					<Tooltip text={skill.status === 'active' ? $t('settings.skills_disable') : $t('settings.skills_enable')} placement="top">
							<button
								class="skill-toggle"
								disabled={saving || skill.status === 'missing'}
								onclick={() => toggleSkill(skill.name, skill.status, skill.source)}
							>
							{#if skill.status === 'active'}
								<CheckCircle size={16} color="var(--ok)" />
							{:else if skill.status === 'disabled'}
								<XCircle size={16} color="var(--tx-dim)" />
							{:else}
								<Circle size={16} color="var(--tx-dim)" />
							{/if}
							</button>
						</Tooltip>

						<button class="skill-name-btn" onclick={() => toggleExpand(skill.name)}>
							<span class="skill-name" class:dimmed={skill.status !== 'active'}>{skill.name}</span>
							<span class="skill-meta">
								{#if skill.source === 'preset'}
									<span class="skill-badge badge-preset">preset</span>
								{:else if skill.source === 'global'}
									<span class="skill-badge badge-global">global</span>
								{:else if skill.source === 'user'}
									<span class="skill-badge badge-user">project</span>
								{/if}
								{#if skill.presets?.length && skill.source !== 'preset'}
									{#each skill.presets as p}
										<span class="skill-badge badge-ref">{p}</span>
									{/each}
								{/if}
								{#if skill.phases?.length}
									<span class="skill-phases">{skill.phases.join(', ')}</span>
								{/if}
							</span>
							{#if expanded === skill.name}
								<ChevronUp size={14} color="var(--tx-dim)" />
							{:else}
								<ChevronDown size={14} color="var(--tx-dim)" />
							{/if}
						</button>
					</div>

					{#if expanded === skill.name}
						<div class="skill-detail">
							{#if loadingDetail}
								<div class="loading-text"><Loader2 size={12} class="spin" /> Loading...</div>
							{:else if expandedDetail}
								{#if expandedDetail.description}
									<p class="skill-desc">{expandedDetail.description}</p>
								{/if}
								<pre class="skill-instructions">{expandedDetail.instructions}</pre>
								{#if Object.keys(expandedDetail.phase_instructions || {}).length > 0}
									{#each Object.entries(expandedDetail.phase_instructions) as [phase, text]}
										<div class="skill-phase-override">
											<span class="skill-phase-label">{phase}:</span>
											<pre class="skill-instructions">{text}</pre>
										</div>
									{/each}
								{/if}
							{/if}
						</div>
					{/if}
				</div>
			{/each}
		</div>
	{/if}
{/if}

<style>
	.skills-preset-badge {
		display: inline-flex;
		align-items: center;
		gap: .4rem;
		padding: .4rem .75rem;
		background: color-mix(in srgb, var(--ac) 12%, transparent);
		border: 1px solid color-mix(in srgb, var(--ac) 25%, transparent);
		border-radius: var(--r);
		font-size: .8125rem;
		color: var(--tx);
		margin-bottom: .75rem;
	}

	.skills-empty {
		font-size: .8125rem;
		color: var(--tx-dim);
		margin-bottom: .75rem;
	}

	.skills-list {
		display: flex;
		flex-direction: column;
		gap: 1px;
	}

	.skill-item {
		background: var(--bg-deep);
		border-radius: var(--r2);
		overflow: hidden;
	}

	.skill-item.expanded {
		background: var(--sf);
	}

	.skill-header {
		display: flex;
		align-items: center;
		gap: .5rem;
		padding: .1rem;
	}

	.skill-toggle {
		flex-shrink: 0;
		display: flex;
		align-items: center;
		justify-content: center;
		width: 2rem;
		height: 2rem;
		border: none;
		background: none;
		cursor: pointer;
		border-radius: var(--r2);
		transition: background .1s;
	}

	.skill-toggle:hover:not(:disabled) {
		background: var(--sf-hover);
	}

	.skill-toggle:disabled {
		opacity: .35;
		cursor: not-allowed;
	}

	.skill-name-btn {
		flex: 1;
		display: flex;
		align-items: center;
		gap: .5rem;
		padding: .55rem .5rem;
		border: none;
		background: none;
		color: var(--tx);
		font-family: inherit;
		font-size: .875rem;
		cursor: pointer;
		text-align: left;
		border-radius: var(--r2);
		transition: background .1s;
	}

	.skill-name-btn:hover {
		background: var(--sf-hover);
	}

	.skill-name {
		font-weight: 500;
		color: var(--tx-bright);
	}

	.skill-name.dimmed {
		color: var(--tx-dim);
	}

	.skill-meta {
		display: flex;
		align-items: center;
		gap: .4rem;
		margin-left: auto;
		flex-wrap: wrap;
		justify-content: flex-end;
	}

	.skill-badge {
		font-size: .65rem;
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: .03rem;
		padding: .15rem .4rem;
		border-radius: .2rem;
		white-space: nowrap;
	}

	.badge-preset {
		background: color-mix(in srgb, var(--ac) 15%, transparent);
		color: var(--ac);
	}

	.badge-global {
		background: color-mix(in srgb, var(--warn) 15%, transparent);
		color: var(--warn);
	}

	.badge-user {
		background: color-mix(in srgb, var(--ok) 15%, transparent);
		color: var(--ok);
	}

	.badge-ref {
		background: color-mix(in srgb, var(--tx-dim) 15%, transparent);
		color: var(--tx-dim);
		font-weight: 500;
	}

	.skill-phases {
		font-size: .7rem;
		color: var(--tx-dim);
	}

	.skill-detail {
		padding: 0 .75rem .75rem 2.5rem;
	}

	.skill-desc {
		font-size: .8125rem;
		color: var(--tx-dim);
		margin-bottom: .5rem;
	}

	.skill-instructions {
		font-family: var(--font-mono, monospace);
		font-size: .75rem;
		line-height: 1.5;
		color: var(--tx);
		background: var(--bg);
		padding: .75rem;
		border-radius: var(--r2);
		white-space: pre-wrap;
		word-break: break-word;
		overflow-x: auto;
		margin: 0;
	}

	.skill-phase-override {
		margin-top: .5rem;
	}

	.skill-phase-label {
		display: block;
		font-size: .7rem;
		font-weight: 600;
		text-transform: uppercase;
		color: var(--tx-dim);
		margin-bottom: .25rem;
	}
</style>
