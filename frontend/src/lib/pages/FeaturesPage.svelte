<script>
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { t } from '$lib/i18n/index.js';
	import { api } from '$lib/api/client.js';
	import { status } from '$lib/stores/statusStore.js';
	import { addLog, addError } from '$lib/stores/logStore.js';
	import { cachedFetch, invalidate } from '$lib/api/cache.js';
	import { Sparkles, Plus, Loader2, AlertTriangle, Trash2 } from 'lucide-svelte';

	let features = $state([]);
	let loading = $state(true);
	let creating = $state(false);
	let error = $state('');

	onMount(() => { load(); });

	async function load() {
		loading = true;
		try {
			const data = await cachedFetch('features', () => api.listFeatures());
			features = data.features || [];
			error = '';
		} catch (e) { error = e.message; addError(e.message, 'features'); }
		loading = false;
	}

	async function createFeature() {
		creating = true;
		try {
			const result = await api.createFeature();
			if (result.success) {
				addLog($t('feature.created', { slug: result.slug }));
				invalidate('features', 'status');
				goto(`/features/${result.slug}`);
			} else { addError(result.message, 'featureCreate'); }
		} catch (e) { addError(e.message, 'featureCreate'); }
		creating = false;
	}

	async function deleteFeature(slug, st) {
		try {
			const result = await api.deleteFeature(slug);
			if (result.success) {
				addLog(result.action === 'deleted'
					? $t('feature.deleted', { slug })
					: $t('feature.cancelled_log', { slug }));
				invalidate('features', 'status');
				await load();
			} else { addError(result.message, 'featureDelete'); }
		} catch (e) { addError(e.message, 'featureDelete'); }
	}

	function statusClass(s) {
		if (s === 'draft') return 'badge-draft';
		if (s === 'planned') return 'badge-planned';
		if (s === 'in-progress') return 'badge-progress';
		if (s === 'done') return 'badge-done';
		if (s === 'cancelled') return 'badge-cancelled';
		return '';
	}
</script>

<div class="main-header">
	<h2><Sparkles size={24} /> {$t('feature.page_title')}</h2>
	<p>{$t('feature.page_subtitle')}</p>
</div>

{#if error}
	<div class="alert alert-warn"><AlertTriangle size={14} /> {error}</div>
{:else if loading}
	<div class="loading-text"><Loader2 size={14} class="spin" /> {$t('app.loading')}</div>
{:else}
	<div class="btn-group">
		<button class="btn btn-primary" disabled={creating} onclick={createFeature}>
			{#if creating}<Loader2 size={14} class="spin" />{:else}<Plus size={14} />{/if}
			{$t('feature.new')}
		</button>
	</div>

	{#if features.length === 0}
		<div class="card empty">
			<p>{$t('feature.empty')}</p>
			<p class="hint">{$t('feature.empty_hint')}</p>
		</div>
	{:else}
		<div class="feature-table-wrap">
			<table class="feature-table">
				<thead>
					<tr>
						<th class="col-slug">{$t('feature.col_id')}</th>
						<th class="col-title">{$t('feature.col_title')}</th>
						<th class="col-status">{$t('feature.col_status')}</th>
						<th class="col-tasks">{$t('feature.col_tasks')}</th>
						<th class="col-date">{$t('feature.col_date')}</th>
						<th class="col-actions"></th>
					</tr>
				</thead>
				<tbody>
					{#each features as feat}
						<tr class="feature-row" onclick={() => goto(`/features/${feat.slug}`)}>
							<td class="col-slug">{feat.slug}</td>
							<td class="col-title">{feat.title || $t('feature.untitled')}</td>
							<td class="col-status">
								<span class="badge {statusClass(feat.status)}">
									{$t('feature.status_' + feat.status)}
								</span>
							</td>
							<td class="col-tasks">{feat.tasks?.length || 0}</td>
							<td class="col-date">{feat.created_at || '—'}</td>
							<td class="col-actions">
								{#if feat.status === 'draft' || feat.status !== 'done'}
									<button
										class="btn-icon"
										title={feat.status === 'draft' ? $t('feature.delete') : $t('feature.cancel')}
										onclick={(e) => { e.stopPropagation(); deleteFeature(feat.slug, feat.status); }}
									>
										<Trash2 size={14} />
									</button>
								{/if}
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{/if}
{/if}

<style>
	.card.empty {
		text-align: center;
		padding: 2rem 1.25rem;
		color: var(--tx-dim);
	}
	.card.empty p { margin: 0.25rem 0; }
	.card.empty .hint { font-size: 0.8125rem; }

	.feature-table-wrap {
		margin-top: 0.75rem;
		border: 0.0625rem solid var(--bd);
		border-radius: var(--r);
		overflow: hidden;
	}

	.feature-table {
		width: 100%;
		border-collapse: collapse;
		font-size: 0.875rem;
	}

	.feature-table thead { background: var(--sf); }

	.feature-table th {
		padding: 0.5rem 0.75rem;
		text-align: left;
		color: var(--tx-dim);
		font-weight: 600;
		font-size: 0.75rem;
		text-transform: uppercase;
		letter-spacing: .03em;
		border-bottom: 0.0625rem solid var(--bd);
	}

	.feature-table td {
		padding: 0.625rem 0.75rem;
		border-bottom: 0.0625rem solid var(--bd);
	}

	.feature-table tr:last-child td { border-bottom: none; }

	.feature-row { cursor: pointer; transition: background .1s; }
	.feature-row:hover { background: var(--bg-deep); }

	.col-slug { width: 5.5rem; font-family: var(--font-ui); color: var(--tx-dim); }
	.col-status { width: 7rem; }
	.col-tasks { width: 4rem; text-align: center; font-family: var(--font-ui); color: var(--tx-dim); }
	.col-date { width: 6.875rem; font-family: var(--font-ui); color: var(--tx-dim); font-size: 0.8125rem; }
	.col-actions { width: 2.5rem; text-align: center; }

	.badge {
		display: inline-block;
		padding: 0.125rem 0.5rem;
		border-radius: 0.625rem;
		font-size: 0.75rem;
		font-weight: 500;
		line-height: 1.125rem;
		white-space: nowrap;
	}

	.badge-draft { background: rgba(130, 130, 160, .12); color: var(--tx-dim); }
	.badge-planned { background: rgba(187, 181, 41, .12); color: var(--warn); }
	.badge-progress { background: rgba(26, 165, 194, .15); color: var(--ac); }
	.badge-done { background: color-mix(in srgb, var(--ok) 15%, transparent); color: var(--ok); }
	.badge-cancelled { background: rgba(180, 80, 80, .12); color: var(--err); }

	.btn-icon {
		background: none;
		border: none;
		color: var(--tx-dim);
		cursor: pointer;
		padding: 0.25rem;
		border-radius: var(--r2);
		transition: color .1s, background .1s;
	}
	.btn-icon:hover { color: var(--err); background: var(--bg-deep); }
</style>
