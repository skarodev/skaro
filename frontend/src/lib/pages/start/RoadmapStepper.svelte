<script>
	import { t } from '$lib/i18n/index.js';
	import { CheckCircle2, Circle, Clock, ArrowRight } from 'lucide-svelte';
	import FileTextAnimated from '$lib/ui/icons/FileTextAnimated.svelte';
	import LayersAnimated from '$lib/ui/icons/LayersAnimated.svelte';
	import FolderOpenCrossfade from '$lib/ui/icons/FolderOpenCrossfade.svelte';
	import MapFoldFlipAnimated from '$lib/ui/icons/MapFoldFlipAnimated.svelte';
	import PackageOpenAnimated from '$lib/ui/icons/PackageOpenAnimated.svelte';
	import ShieldCheckAnimated from '$lib/ui/icons/ShieldCheckAnimated.svelte';

	let { status } = $props();

	let allTasksDone = $derived.by(() => {
		const tasks = status?.tasks;
		if (!tasks || tasks.length === 0) return false;
		return tasks.every(f => f.phases?.tests === 'complete');
	});

	let steps = $derived.by(() => {
		if (!status?.initialized) return [];
		return [
			{
				id: 'constitution',
				icon: FileTextAnimated,
				done: status.constitution_validated,
				active: status.has_constitution && !status.constitution_validated,
				href: '/constitution',
			},
			{
				id: 'architecture',
				icon: LayersAnimated,
				done: status.architecture_reviewed,
				active: status.has_architecture && !status.architecture_reviewed,
				href: '/architecture',
			},
			{
				id: 'adr',
				icon: FolderOpenCrossfade,
				done: status.architecture_reviewed && (status.adr_count || 0) > 0,
				active: status.architecture_reviewed && (status.adr_count || 0) === 0,
				href: '/adr',
			},
			{
				id: 'devplan',
				icon: MapFoldFlipAnimated,
				done: status.devplan_confirmed,
				active: status.has_devplan && !status.devplan_confirmed,
				href: '/devplan',
			},
			{
				id: 'tasks',
				icon: PackageOpenAnimated,
				done: allTasksDone,
				active: (status.tasks?.length || 0) > 0 && !allTasksDone,
				href: '/tasks',
			},
			{
				id: 'review',
				icon: ShieldCheckAnimated,
				done: status.review_passed === true,
				active: allTasksDone && status.review_passed !== true,
				href: '/review',
			},
		];
	});

	/** Index of first incomplete step — used for "current" highlight */
	let currentIdx = $derived(steps.findIndex(s => !s.done));
</script>

<div class="roadmap">
	{#each steps as step, i}
		{@const Icon = step.icon}
		{@const isCurrent = i === currentIdx}
		<a
			class="rm-step"
			class:done={step.done}
			class:active={step.active}
			class:current={isCurrent}
			href={step.href}
		>
			<!-- Connector line (above, except first) -->
			{#if i > 0}
				<div class="rm-line" class:rm-line-done={steps[i - 1].done}></div>
			{/if}

			<div class="rm-marker">
				{#if step.done}
					<CheckCircle2 size={22} />
				{:else if step.active}
					<Clock size={22} />
				{:else}
					<Circle size={22} />
				{/if}
			</div>

			<div class="rm-body">
				<div class="rm-head">
					<span class="rm-icon"><Icon size={16} active={isCurrent} /></span>
					<span class="rm-title">{$t('start.step_' + step.id)}</span>
					{#if step.done}
						<span class="rm-badge rm-badge-done">{$t('start.done')}</span>
					{:else if step.active}
						<span class="rm-badge rm-badge-active">{$t('start.in_progress')}</span>
					{:else}
						<span class="rm-badge rm-badge-pending">{$t('start.pending')}</span>
					{/if}
				</div>
				<p class="rm-desc">{$t('start.desc_' + step.id)}</p>
				{#if isCurrent}
					<span class="rm-go">
						{$t('start.go_to')}
						<ArrowRight size={13} />
					</span>
				{/if}
			</div>
		</a>
	{/each}
</div>

<style>
	.roadmap {
		display: flex;
		flex-direction: column;
		gap: 0;
		position: relative;
	}

	/* ── Step row ── */

	.rm-step {
		display: flex;
		align-items: flex-start;
		gap: 1rem;
		padding: 1rem 1.25rem;
		border-radius: var(--r);
		text-decoration: none;
		transition: background .15s;
		position: relative;
		cursor: pointer;
	}

	.rm-step:hover {
		background: var(--bg-deep);
	}

	.rm-step.current {
		background: color-mix(in srgb, var(--ac) 6%, transparent);
		border: 1px solid color-mix(in srgb, var(--ac) 20%, transparent);
	}

	/* ── Vertical connector line ── */

	.rm-line {
		position: absolute;
		left: 2.1rem;
		top: -0.5rem;
		bottom: calc(100% - 1rem);
		width: 2px;
		height: 1rem;
		background: var(--bd);
		z-index: 0;
		top: 0;
		height: 1rem;
	}

	.rm-line.rm-line-done {
		background: var(--ok);
	}

	/* ── Marker circle ── */

	.rm-marker {
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

	.rm-step.done .rm-marker {
		color: var(--ok);
	}

	.rm-step.active .rm-marker {
		color: var(--warn);
	}

	.rm-step.current .rm-marker {
		color: var(--ac);
	}

	/* ── Body ── */

	.rm-body {
		flex: 1;
		min-width: 0;
	}

	.rm-head {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		margin-bottom: 0.25rem;
	}

	.rm-icon {
		display: flex;
		align-items: center;
		color: var(--tx-dim);
	}

	.rm-step.current .rm-icon {
		color: var(--ac);
	}

	.rm-title {
		font-size: 0.9375rem;
		font-weight: 600;
		color: var(--tx-bright);
	}

	.rm-desc {
		font-size: 0.8125rem;
		color: var(--tx-dim);
		line-height: 1.5;
		margin: 0;
	}

	.rm-step.current .rm-desc {
		color: var(--tx);
	}

	/* ── Badge ── */

	.rm-badge {
		font-size: 0.625rem;
		font-weight: 500;
		padding: 0.0625rem 0.4375rem;
		border-radius: 0.625rem;
		text-transform: uppercase;
		letter-spacing: 0.03em;
		white-space: nowrap;
		line-height: 1.25rem;
	}

	.rm-badge-done {
		background: color-mix(in srgb, var(--ok) 15%, transparent);
		color: var(--ok);
	}

	.rm-badge-active {
		background: rgba(255, 198, 109, .12);
		color: var(--warn);
	}

	.rm-badge-pending {
		background: var(--bg-deep);
		color: var(--tx-dim);
	}

	/* ── Go-to link ── */

	.rm-go {
		display: inline-flex;
		align-items: center;
		gap: 0.25rem;
		font-size: 0.75rem;
		font-weight: 600;
		color: var(--ac);
		margin-top: 0.5rem;
	}

	.rm-step:hover .rm-go {
		text-decoration: underline;
	}
</style>
