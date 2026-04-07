<script>
	import { onMount, onDestroy } from 'svelte';
	import { t } from '$lib/i18n/index.js';
	import { api } from '$lib/api/client.js';
	import { status, devplanMilestones } from '$lib/stores/statusStore.js';
	import { addLog, addError } from '$lib/stores/logStore.js';
	import { cachedFetch, invalidate } from '$lib/api/cache.js';
	import { Map, ClipboardList, Check, AlertTriangle, Loader2, Pencil } from 'lucide-svelte';
	import MarkdownContent from '$lib/ui/MarkdownContent.svelte';
	import DevPlanProposal from '$lib/pages/devplan/DevPlanProposal.svelte';
	import MdEditor from '$lib/ui/md-editor/MdEditor.svelte';

	let devplanContent = $state('');
	let devplanConfirmed = $state(false);
	let draftMilestones = $state(null);
	let loading = $state(false);
	let approving = $state(false);
	let confirmingPlan = $state(false);
	let error = $state('');
	let formatError = $state('');
	let showEditor = $state(false);

	onMount(() => {
		load();
		window.addEventListener('skaro:devplan-updated', handleDevplanUpdated);
	});

	onDestroy(() => {
		window.removeEventListener('skaro:devplan-updated', handleDevplanUpdated);
	});

	function handleDevplanUpdated() {
		invalidate('devplan', 'status');
		load();
	}

	async function load() {
		loading = true;
		formatError = '';
		try {
			const data = await cachedFetch('devplan', () => api.getDevPlan());
			devplanContent = data.content || '';
			devplanConfirmed = data.devplan_confirmed ?? false;
			error = '';
			// If devplan exists but not confirmed — parse milestones
			if (devplanContent.trim().length > 100 && !devplanConfirmed && !$devplanMilestones) {
				const ms = await api.getDevPlanMilestones();
				if (ms.milestones?.length > 0) draftMilestones = ms.milestones;
			}
		}
		catch (e) { error = e.message; addError(e.message, 'devplan'); }
		loading = false;
	}

	async function confirmPlan() {
		const milestones = $devplanMilestones || draftMilestones;
		if (!milestones) return;
		confirmingPlan = true;
		try {
			const result = await api.confirmDevPlan({ milestones });
			if (result.success) {
				addLog($t('log.tasks_created', { n: result.tasks_created.length }));
				devplanMilestones.set(null);
				draftMilestones = null;
				devplanConfirmed = true;
				invalidate('devplan', 'status');
				status.set(await api.getStatus());
				await load();
			} else { addError(result.message, 'confirmDevPlan'); }
		} catch (e) { addError(e.message, 'confirmDevPlan'); }
		confirmingPlan = false;
	}

	async function approve() {
		approving = true;
		formatError = '';
		try {
			// Parse milestones to check format
			const ms = await api.getDevPlanMilestones();
			const milestones = ms.milestones || [];
			const totalTasks = milestones.reduce((sum, m) => sum + (m.tasks?.length || 0), 0);

			if (milestones.length === 0 || totalTasks === 0) {
				formatError = $t('devplan.format_error');
				approving = false;
				return;
			}

			// Confirm with parsed milestones
			const result = await api.confirmDevPlan({ milestones });
			if (result.success) {
				addLog($t('log.tasks_created', { n: result.tasks_created.length }));
				devplanMilestones.set(null);
				draftMilestones = null;
				devplanConfirmed = true;
				invalidate('devplan', 'status');
				status.set(await api.getStatus());
				await load();
			} else { addError(result.message, 'approvePlan'); }
		} catch (e) { addError(e.message, 'approvePlan'); }
		approving = false;
	}

	async function saveContent(content) {
		try {
			await api.saveDevPlan(content);
			addLog($t('editor.doc_saved'));
			invalidate('devplan', 'status');
			status.set(await api.getStatus());
			await load();
		} catch (e) { addError(e.message, 'devplanSave'); }
	}

	let hasDevplan = $derived(devplanContent.trim().length > 100);
</script>

<div class="main-header">
	<h2>
		{$t('devplan.title')}
		{#if hasDevplan}
			{#if devplanConfirmed}
				<span class="status-badge status-badge-ok">{$t('status.approved')}</span>
			{:else}
				<span class="status-badge status-badge-pending">{$t('status.not_approved')}</span>
			{/if}
		{/if}
	</h2>
	<p>{$t('devplan.subtitle')}</p>
</div>

{#if error}
	<div class="alert alert-warn"><AlertTriangle size={14} /> {error}</div>
{:else if loading}
	<div class="loading-text"><Loader2 size={14} class="spin" /> {$t('app.loading')}</div>
{:else if !hasDevplan && !$devplanMilestones}
	<div class="card empty">
		<p>{$t('devplan.empty')}</p>
		<p class="hint">{$t('devplan.empty_hint')}</p>
	</div>
{:else}
	{#if ($devplanMilestones || draftMilestones) && !devplanConfirmed}
		<DevPlanProposal
			mode="initial"
			items={$devplanMilestones || draftMilestones}
			confirming={confirmingPlan}
			onConfirm={confirmPlan}
			onDiscard={() => { devplanMilestones.set(null); draftMilestones = null; }}
		/>
	{:else if !devplanConfirmed}
		<div class="btn-group">
			<button class="btn btn-success" disabled={approving} onclick={approve}>
				{#if approving}<Loader2 size={14} class="spin" />{:else}<Check size={14} />{/if}
				{$t('devplan.approve')}
			</button>
			<button class="btn" onclick={() => showEditor = true}>
				<Pencil size={14} /> {$t('editor.edit')}
			</button>
		</div>
		{#if formatError}
			<div class="alert alert-warn" style="margin-top: 0.5rem;">
				<AlertTriangle size={14} /> {formatError}
			</div>
		{/if}
	{:else}
		<div class="btn-group">
			<button class="btn" onclick={() => showEditor = true}>
				<Pencil size={14} /> {$t('editor.edit')}
			</button>
		</div>
	{/if}

	{#if hasDevplan}
		<MarkdownContent content={devplanContent} />
	{/if}
{/if}

{#if showEditor}
	<MdEditor
		content={devplanContent}
		onSave={(c) => { saveContent(c); showEditor = false; }}
		onClose={() => showEditor = false}
	/>
{/if}

<style>
	.card.empty {
		text-align: center;
		padding: 2rem 1.25rem;
		color: var(--tx-dim);
	}
	.card.empty p { margin: 0.25rem 0; }
	.card.empty .hint { font-size: 0.8125rem; }
	.btn-success {
		background: var(--ok);
		color: #fff;
		border-color: var(--ok);
	}
	.btn-success:hover:not(:disabled) { filter: brightness(1.1); }
</style>
