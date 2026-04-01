<script>
	import { t } from '$lib/i18n/index.js';
	import { api } from '$lib/api/client.js';
	import { addError } from '$lib/stores/logStore.js';
	import { Loader2 } from 'lucide-svelte';

	/** @type {{ onSelect: (content: string, presetId: string) => void }} */
	let { onSelect } = $props();

	let presets = $state(/** @type {any[]} */ ([]));
	let loading = $state(true);
	let loadingId = $state(/** @type {string|null} */ (null));

	$effect(() => { loadPresets(); });

	async function loadPresets() {
		try {
			const res = await api.getConstitutionPresets();
			presets = res.presets ?? [];
		} catch (e) { addError(e.message, 'presets'); }
		loading = false;
	}

	async function pick(id) {
		loadingId = id;
		try {
			const res = await api.getConstitutionPreset(id);
			onSelect(res.content, id);
		} catch (e) { addError(e.message, 'presetLoad'); }
		loadingId = null;
	}
</script>

{#if loading}
	<div class="loading-text"><Loader2 size={14} class="spin" /> {$t('app.loading')}</div>
{:else}
	<div class="preset-picker">
		<p class="preset-hint">{$t('const.preset_hint')}</p>
		<div class="preset-grid">
			{#each presets as preset}
				<button
					class="preset-card"
					disabled={loadingId !== null}
					onclick={() => pick(preset.id)}
				>
					{#if loadingId === preset.id}
						<Loader2 size={18} class="spin" />
					{:else}
						<img
							src="/icons/presets/{preset.id}.svg"
							alt=""
							class="preset-icon"
							width="24"
							height="24"
						/>
					{/if}
					<span class="preset-name">{preset.name}</span>
				</button>
			{/each}
		</div>
	</div>
{/if}

<style>
	.preset-picker {
		margin-top: .5rem;
	}
	.preset-hint {
		color: var(--tx-dim);
		font-size: .85rem;
		margin-bottom: 1rem;
	}
	.preset-grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
		gap: .5rem;
	}
	.preset-card {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: .5rem;
		padding: .7rem .5rem;
		background: var(--sf);
		border: 1px solid var(--sf);
		border-radius: var(--r);
		color: var(--tx-bright);
		font-family: inherit;
		font-size: .9rem;
		font-weight: 500;
		cursor: pointer;
		transition: border-color .15s, background .15s;
	}
	.preset-card:hover:not(:disabled) {
		border-color: var(--ac);
		background: var(--sf-hover);
	}
	.preset-card:disabled {
		opacity: .45;
		cursor: wait;
	}
	.preset-icon {
		flex-shrink: 0;
	}
	.preset-name {
		white-space: nowrap;
	}
</style>
