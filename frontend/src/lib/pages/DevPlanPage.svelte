<script>
	import { onMount } from 'svelte';
	import { t } from '$lib/i18n/index.js';
	import { api } from '$lib/api/client.js';
	import { status, devplanMilestones } from '$lib/stores/statusStore.js';
	import { addLog, addError } from '$lib/stores/logStore.js';
	import { cachedFetch, invalidate } from '$lib/api/cache.js';
	import { Map, ClipboardList, RefreshCw, AlertTriangle, Loader2 } from 'lucide-svelte';
	import MarkdownContent from '$lib/ui/MarkdownContent.svelte';
	import GuidanceInput from '$lib/pages/devplan/GuidanceInput.svelte';
	import DevPlanProposal from '$lib/pages/devplan/DevPlanProposal.svelte';
	import Tooltip from '$lib/ui/Tooltip.svelte';

	let architectureReady = $derived(!!$status?.architecture_reviewed);

	let devplanContent = $state('');
	let devplanConfirmed = $state(false);
	let draftMilestones = $state(null); // milestones parsed from imported devplan
	let loading = $state(false);
	let generating = $state(false);
	let updating = $state(false);
	let confirmingUpdate = $state(false);
	let confirmingPlan = $state(false);
	let error = $state('');
	let updateGuidance = $state('');
	let showGuidanceInput = $state(false);
	let proposedDevplan = $state('');
	let proposedNewMilestones = $state([]);
	let updateRawResponse = $state('');

	onMount(() => { load(); });

	async function load() {
		loading = true;
		try {
			const data = await cachedFetch('devplan', () => api.getDevPlan());
			devplanContent = data.content || '';
			devplanConfirmed = data.devplan_confirmed ?? false;
			error = '';
			// If imported but not yet confirmed — load milestones for the Confirm UI
			if (devplanContent.trim().length > 100 && !devplanConfirmed && !$devplanMilestones) {
				const ms = await api.getDevPlanMilestones();
				if (ms.milestones?.length > 0) draftMilestones = ms.milestones;
			}
		}
		catch (e) { error = e.message; addError(e.message, 'devplan'); }
		loading = false;
	}

	async function generate() {
		generating = true;
		addLog($t('log.devplan_gen'));
		try {
			const result = await api.generateDevPlan();
			if (result.success && result.milestones?.length > 0) {
				devplanMilestones.set(result.milestones);
				devplanContent = result.devplan || '';
				addLog($t('log.devplan_milestones', { n: result.milestones.length }));
			} else { addError(result.message, 'devplan'); }
		} catch (e) { addError(e.message, 'devplan'); }
		generating = false;
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

	async function runUpdate() {
		updating = true; proposedDevplan = ''; proposedNewMilestones = []; updateRawResponse = '';
		addLog($t('log.devplan_update'));
		try {
			const result = await api.updateDevPlan(updateGuidance);
			if (result.success) {
				proposedDevplan = result.updated_devplan || '';
				proposedNewMilestones = result.new_milestones || [];
				updateRawResponse = result.message || '';
				addLog($t('log.devplan_update_proposed'));
				showGuidanceInput = false; updateGuidance = '';
			} else { addError(result.message, 'devplanUpdate'); }
		} catch (e) { addError(e.message, 'devplanUpdate'); }
		updating = false;
	}

	async function confirmUpdate() {
		confirmingUpdate = true;
		try {
			const result = await api.confirmDevPlanUpdate({ updated_devplan: proposedDevplan, new_milestones: proposedNewMilestones });
			if (result.success) {
				addLog($t('log.devplan_updated', { n: result.tasks_created?.length || 0 }));
				proposedDevplan = ''; proposedNewMilestones = []; updateRawResponse = '';
				invalidate('devplan', 'status');
				status.set(await api.getStatus());
				await load();
			} else { addError(result.message, 'confirmUpdate'); }
		} catch (e) { addError(e.message, 'confirmUpdate'); }
		confirmingUpdate = false;
	}

	function discardUpdate() { proposedDevplan = ''; proposedNewMilestones = []; updateRawResponse = ''; }
	function cancelGuidance() { showGuidanceInput = false; updateGuidance = ''; }

	let hasDevplan = $derived(devplanContent.trim().length > 100);
	let hasProposal = $derived(proposedDevplan.trim().length > 0 || updateRawResponse.trim().length > 0);
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
	<div class="btn-group">
		<Tooltip text={!architectureReady ? $t('gate.need_architecture') : ''} placement="bottom">
		<button class="btn btn-primary" disabled={generating || !architectureReady} onclick={generate}>
			{#if generating}<Loader2 size={14} class="spin" />{:else}<ClipboardList size={14} />{/if}
			{$t('devplan.generate')}
		</button>
		</Tooltip>
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
	{:else if !$devplanMilestones && !hasProposal}
		<div class="btn-group">
			{#if !showGuidanceInput}
				<Tooltip text={!architectureReady ? $t('gate.need_architecture') : ''} placement="bottom">
				<button class="btn btn-primary" disabled={updating || !architectureReady} onclick={() => showGuidanceInput = true}>
					<RefreshCw size={14} /> {$t('devplan.update_btn')}
				</button>
				</Tooltip>
			{/if}
			<Tooltip text={!architectureReady ? $t('gate.need_architecture') : ''} placement="bottom">
			<button class="btn" disabled={generating || !architectureReady} onclick={generate}>
				{#if generating}<Loader2 size={14} class="spin" />{:else}<ClipboardList size={14} />{/if}
				{$t('devplan.regenerate')}
			</button>
			</Tooltip>
		</div>

		{#if showGuidanceInput}
			<GuidanceInput bind:guidance={updateGuidance} {updating} onRun={runUpdate} onCancel={cancelGuidance} />
		{/if}
	{/if}

	{#if $devplanMilestones && devplanConfirmed}
		<DevPlanProposal
			mode="initial"
			items={$devplanMilestones}
			confirming={confirmingPlan}
			onConfirm={confirmPlan}
			onDiscard={() => devplanMilestones.set(null)}
		/>
	{/if}

	{#if hasProposal}
		<DevPlanProposal
			mode="update"
			items={proposedNewMilestones}
			{proposedDevplan}
			rawResponse={updateRawResponse}
			confirming={confirmingUpdate}
			onConfirm={confirmUpdate}
			onDiscard={discardUpdate}
		/>
	{/if}

	{#if hasDevplan && !($devplanMilestones || draftMilestones) && !hasProposal}
		<MarkdownContent content={devplanContent} />
	{/if}
{/if}


