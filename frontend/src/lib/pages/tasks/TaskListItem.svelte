<script>
	import { t } from '$lib/i18n/index.js';
	import { CheckCircle2, Circle, Clock } from 'lucide-svelte';
	import SparklesAnimated from '$lib/ui/icons/SparklesAnimated.svelte';
	import MapFoldFlipAnimated from '$lib/ui/icons/MapFoldFlipAnimated.svelte';
	import PackageOpenAnimated from '$lib/ui/icons/PackageOpenAnimated.svelte';
	import ShieldCheckAnimated from '$lib/ui/icons/ShieldCheckAnimated.svelte';

	/**
	 * @type {{
	 *   task: any,
	 *   href: string,
	 *   isFirst?: boolean,
	 *   isLast?: boolean,
	 *   prevStatus?: string,
	 *   nextStatus?: string,
	 * }}
	 */
	let {
		task,
		href,
		isFirst = false,
		isLast = false,
		prevStatus = 'pending',
		nextStatus = 'pending',
	} = $props();

	/** Whether all meaningful phases are complete. */
	let allComplete = $derived(
		task.phases &&
			Object.keys(task.phases).length > 0 &&
			['clarify', 'plan', 'implement', 'tests'].every(
				(k) => task.phases[k] === 'complete'
			)
	);

	/** Simplified status: 'done' | 'active' | 'pending'. */
	let itemStatus = $derived.by(() => {
		if (allComplete) return 'done';
		const ph = task.phases || {};
		const hasProgress = Object.values(ph).some(
			(s) => s === 'complete' || s === 'in_progress' || s === 'draft' || s === 'awaiting_review'
		);
		return hasProgress ? 'active' : 'pending';
	});

	/** Animated icon component based on current_phase. */
	let PhaseIcon = $derived.by(() => {
		if (allComplete) return null; // done uses CheckCircle2 directly
		switch (task.current_phase) {
			case 'clarify':
				return SparklesAnimated;
			case 'plan':
				return MapFoldFlipAnimated;
			case 'implement':
				return PackageOpenAnimated;
			case 'tests':
				return ShieldCheckAnimated;
			default:
				return SparklesAnimated;
		}
	});

	/** Phase label for the badge. */
	let phaseLabel = $derived(
		allComplete ? $t('phase.done') : $t('phase.' + (task.current_phase || 'clarify'))
	);

	/** Badge variant class. */
	let badgeClass = $derived.by(() => {
		if (allComplete) return 'tl-badge-done';
		if (itemStatus === 'active') return 'tl-badge-active';
		return 'tl-badge-pending';
	});

	/** Tracks hover for icon animation. */
	let hovered = $state(false);

	/** Map a status string to a CSS colour variable. */
	function statusColor(status) {
		if (status === 'done') return 'var(--ok)';
		if (status === 'active') return 'var(--warn)';
		return 'var(--bd)';
	}
</script>

<a
	class="tl-step"
	class:done={itemStatus === 'done'}
	class:active={itemStatus === 'active'}
	{href}
	draggable="false"
	onmouseenter={() => (hovered = true)}
	onmouseleave={() => (hovered = false)}
>
	<!-- Vertical connector: top -->
	{#if !isFirst}
		<div
			class="tl-line tl-line-top"
			style="background: linear-gradient(to bottom, {statusColor(prevStatus)}, {statusColor(itemStatus)})"
		></div>
	{/if}

	<!-- Vertical connector: bottom -->
	{#if !isLast}
		<div
			class="tl-line tl-line-bottom"
			style="background: linear-gradient(to bottom, {statusColor(itemStatus)}, {statusColor(nextStatus)})"
		></div>
	{/if}

	<!-- Marker circle -->
	<div class="tl-marker">
		{#if itemStatus === 'done'}
			<CheckCircle2 size={22} />
		{:else if itemStatus === 'active'}
			<Clock size={22} />
		{:else}
			<Circle size={22} />
		{/if}
	</div>

	<!-- Body -->
	<div class="tl-body">
		<div class="tl-head">
			{#if allComplete}
				<span class="tl-icon tl-icon-done">
					<CheckCircle2 size={16} />
				</span>
			{:else if PhaseIcon}
				<span class="tl-icon">
					<PhaseIcon size={16} active={hovered} />
				</span>
			{/if}
			<span class="tl-title">{task.name}</span>
			<span class="tl-badge {badgeClass}">{phaseLabel}</span>
		</div>
		{#if task.context}
			<p class="tl-desc">{task.context}</p>
		{/if}
	</div>
</a>

<style>
	/* ── Step row ── */

	.tl-step {
		display: flex;
		align-items: flex-start;
		gap: 1rem;
		padding: 1rem 1.25rem;
		border: 1px solid transparent;
		border-radius: var(--r);
		text-decoration: none;
		color: inherit;
		transition: background .15s;
		position: relative;
		cursor: pointer;
	}

	.tl-step:hover {
		background: var(--bg-deep);
		text-decoration: none;
	}

	.tl-step.active {
		background: color-mix(in srgb, var(--ac) 6%, transparent);
		border-color: color-mix(in srgb, var(--ac) 20%, transparent);
	}

	/* ── Vertical connector lines ── */

	.tl-line {
		position: absolute;
		left: calc(1.25rem + 1.625rem / 2 - 1px);
		width: 2px;
		z-index: 0;
		transition: background .2s;
	}

	.tl-line-top {
		top: 0;
		height: calc(1rem + 0.125rem);
	}

	.tl-line-bottom {
		top: calc(1rem + 0.125rem + 1.375rem);
		bottom: 0;
	}

	/* ── Marker circle ── */

	.tl-marker {
		flex-shrink: 0;
		width: 1.625rem;
		display: flex;
		align-items: center;
		justify-content: center;
		color: var(--tx-dim);
		margin-top: 0.125rem;
		position: relative;
		z-index: 1;
	}

	.tl-step.done .tl-marker {
		color: var(--ok);
	}

	.tl-step.active .tl-marker {
		color: var(--warn);
	}

	/* ── Body ── */

	.tl-body {
		flex: 1;
		min-width: 0;
	}

	.tl-head {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		margin-bottom: 0.25rem;
	}

	.tl-icon {
		display: flex;
		align-items: center;
		color: var(--tx-dim);
		flex-shrink: 0;
	}

	.tl-icon-done {
		color: var(--ok);
	}

	.tl-step.active .tl-icon {
		color: var(--ac);
	}

	.tl-title {
		font-size: 0.9375rem;
		font-weight: 600;
		color: var(--tx-bright);
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		min-width: 0;
	}

	.tl-desc {
		font-size: 0.8125rem;
		color: var(--tx-dim);
		line-height: 1.5;
		margin: 0;
		display: -webkit-box;
		-webkit-line-clamp: 2;
		-webkit-box-orient: vertical;
		overflow: hidden;
	}

	.tl-step.active .tl-desc {
		color: var(--tx);
	}

	/* ── Badge ── */

	.tl-badge {
		font-size: 0.625rem;
		font-weight: 500;
		padding: 0.0625rem 0.4375rem;
		border-radius: 0.625rem;
		text-transform: uppercase;
		letter-spacing: 0.03em;
		white-space: nowrap;
		line-height: 1.25rem;
		flex-shrink: 0;
	}

	.tl-badge-done {
		background: color-mix(in srgb, var(--ok) 15%, transparent);
		color: var(--ok);
	}

	.tl-badge-active {
		background: rgba(255, 198, 109, .12);
		color: var(--warn);
	}

	.tl-badge-pending {
		background: var(--bg-deep);
		color: var(--tx-dim);
	}
</style>
