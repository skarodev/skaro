<script>
	import { onMount } from 'svelte';
	import { t } from '$lib/i18n/index.js';
	import { status } from '$lib/stores/statusStore.js';
	import { theme } from '$lib/stores/themeStore.js';
	import { BarChart3, AlertTriangle } from 'lucide-svelte';

	let container = $state(null);
	let mermaidLib = $state(null);
	let renderError = $state('');
	let loading = $state(true);
	let renderCounter = 0;

	/* ── Group tasks by milestone ────────────── */

	let tasksByMilestone = $derived.by(() => {
		const tasks = $status?.tasks || [];
		if (!tasks.length) return {};

		const grouped = {};
		for (const task of tasks) {
			const ms = task.milestone || 'unassigned';
			if (!grouped[ms]) grouped[ms] = [];
			grouped[ms].push(task);
		}
		return grouped;
	});

	let hasTasks = $derived(Object.keys(tasksByMilestone).length > 0);

	/* ── Legend counters ──────────────────────── */

	let legend = $derived.by(() => {
		const tasks = $status?.tasks || [];
		let done = 0, active = 0, pending = 0;
		for (const t of tasks) {
			if (t.progress_percent >= 100) done++;
			else if (t.progress_percent > 0) active++;
			else pending++;
		}
		return { done, active, pending, total: tasks.length };
	});

	/* ── Load mermaid dynamically ────────────── */

	onMount(async () => {
		try {
			const mod = await import('mermaid');
			mermaidLib = mod.default;
		} catch (e) {
			renderError = 'Failed to load mermaid: ' + e.message;
		}
		loading = false;
	});

	/* ── Helpers ──────────────────────────────── */

	function sanitizeId(name) {
		return 'tk_' + name.replace(/[^a-zA-Z0-9]/g, '_');
	}

	function sanitizeLabel(name) {
		// Mermaid Gantt label: avoid colons, semicolons, hash
		return name.replace(/[:;#]/g, '-');
	}

	function formatMilestoneName(slug) {
		const parts = slug.split('-');
		const num = parts[0];
		const name = parts
			.slice(1)
			.map((w) => w.charAt(0).toUpperCase() + w.slice(1))
			.join(' ');
		return name ? `${num} — ${name}` : slug;
	}

	function statusTag(task) {
		if (task.progress_percent >= 100) return 'done, ';
		if (task.progress_percent > 0) return 'active, ';
		return '';
	}

	function offsetToDate(offset) {
		const d = new Date(2025, 0, 1 + offset);
		const y = d.getFullYear();
		const m = String(d.getMonth() + 1).padStart(2, '0');
		const day = String(d.getDate()).padStart(2, '0');
		return `${y}-${m}-${day}`;
	}

	function buildDefinition() {
		const lines = [
			'gantt',
			'    dateFormat YYYY-MM-DD',
			'    todayMarker off',
			'    axisFormat  ',
		];

		let dayOffset = 0;
		const milestones = Object.keys(tasksByMilestone).sort();

		for (const ms of milestones) {
			const tasks = tasksByMilestone[ms];
			lines.push(`    section ${formatMilestoneName(ms)}`);

			for (const task of tasks) {
				const id = sanitizeId(task.name);
				const tag = statusTag(task);
				const start = offsetToDate(dayOffset);
				const label = sanitizeLabel(task.name);
				lines.push(`    ${label} :${tag}${id}, ${start}, 2d`);
				dayOffset += 2;
			}
			dayOffset += 1; // gap between milestones
		}

		return lines.join('\n');
	}

	/* ── Dark / Light palettes matching Skaro ── */

	const DARK_VARS = {
		primaryColor: '#589df6',
		primaryTextColor: '#d4d4d4',
		primaryBorderColor: '#4b6eaf',
		lineColor: '#515151',
		sectionBkgColor: '#313131',
		altSectionBkgColor: '#2a2d2f',
		gridColor: '#3c3f41',
		doneTaskBkgColor: '#6a8759',
		doneTaskBorderColor: '#4a6b3f',
		activeTaskBkgColor: '#589df6',
		activeTaskBorderColor: '#4b6eaf',
		taskBkgColor: '#45494a',
		taskBorderColor: '#515151',
		taskTextColor: '#d4d4d4',
		taskTextDarkColor: '#d4d4d4',
		sectionBkgColor2: '#262626',
	};

	const LIGHT_VARS = {
		primaryColor: '#4a78c2',
		primaryTextColor: '#2b2b2b',
		primaryBorderColor: '#3d6098',
		lineColor: '#d0d0d0',
		sectionBkgColor: '#f0f0f2',
		altSectionBkgColor: '#e4e4e8',
		gridColor: '#d0d0d0',
		doneTaskBkgColor: '#4a8c3f',
		doneTaskBorderColor: '#3b7a2c',
		activeTaskBkgColor: '#4a78c2',
		activeTaskBorderColor: '#3d6098',
		taskBkgColor: '#dcdcdc',
		taskBorderColor: '#b8b8b8',
		taskTextColor: '#2b2b2b',
		taskTextDarkColor: '#ffffff',
		sectionBkgColor2: '#f8f8f8',
	};

	/* ── Render mermaid chart ────────────────── */

	$effect(() => {
		if (!mermaidLib || !container || !hasTasks) return;

		const isDark = $theme === 'dark';

		mermaidLib.initialize({
			startOnLoad: false,
			theme: 'base',
			themeVariables: isDark ? DARK_VARS : LIGHT_VARS,
			gantt: {
				barHeight: 26,
				barGap: 6,
				topPadding: 50,
				sidePadding: 100,
				sectionFontSize: 13,
				numberSectionStyles: 4,
				useWidth: undefined,
			},
		});

		const def = buildDefinition();
		const renderId = `skaro-gantt-${++renderCounter}`;

		mermaidLib
			.render(renderId, def)
			.then(({ svg }) => {
				if (container) {
					container.innerHTML = svg;
					const svgEl = container.querySelector('svg');
					if (svgEl) {
						svgEl.style.maxWidth = '100%';
						svgEl.style.height = 'auto';
					}
				}
				renderError = '';
			})
			.catch((err) => {
				renderError = err.message || 'Render failed';
			});
	});
</script>

{#if loading}
	<div class="gantt-loading">{$t('app.loading')}</div>
{:else if renderError}
	<div class="gantt-error">
		<AlertTriangle size={14} />
		{renderError}
	</div>
{:else if !hasTasks}
	<div class="gantt-empty">{$t('devplan.gantt_no_tasks')}</div>
{:else}
	<div class="gantt-wrapper">
		<div class="gantt-header">
			<h3><BarChart3 size={16} /> {$t('devplan.gantt_title')}</h3>
			<div class="gantt-legend">
				<span class="legend-item done">{$t('devplan.gantt_done')} ({legend.done})</span>
				<span class="legend-item active">{$t('devplan.gantt_active')} ({legend.active})</span>
				<span class="legend-item pending">{$t('devplan.gantt_pending')} ({legend.pending})</span>
			</div>
		</div>
		<div class="gantt-container" bind:this={container}></div>
	</div>
{/if}

<style>
	.gantt-wrapper {
		border: 0.0625rem solid var(--bd);
		border-radius: var(--r);
		background: var(--bg-deep);
		padding: 1rem;
		margin-bottom: 1.25rem;
	}

	.gantt-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		margin-bottom: 0.75rem;
		flex-wrap: wrap;
		gap: 0.5rem;
	}

	.gantt-header h3 {
		font-size: 0.875rem;
		font-weight: 600;
		color: var(--tx-bright);
		display: flex;
		align-items: center;
		gap: 0.375rem;
		margin: 0;
	}

	.gantt-legend {
		display: flex;
		gap: 0.75rem;
		font-size: 0.75rem;
		font-family: var(--font-ui);
	}

	.legend-item {
		display: flex;
		align-items: center;
		gap: 0.25rem;
	}

	.legend-item::before {
		content: '';
		display: inline-block;
		width: 0.625rem;
		height: 0.625rem;
		border-radius: 0.125rem;
	}

	.legend-item.done::before {
		background: var(--gn);
	}

	.legend-item.active::before {
		background: var(--ac);
	}

	.legend-item.pending::before {
		background: var(--sf2);
	}

	.gantt-container {
		overflow-x: auto;
		overflow-y: hidden;
	}

	/* Override mermaid SVG to fit container */
	.gantt-container :global(svg) {
		display: block;
		max-width: 100%;
		height: auto;
	}

	.gantt-loading,
	.gantt-empty {
		font-size: 0.8125rem;
		color: var(--dm);
		padding: 1rem;
		text-align: center;
	}

	.gantt-error {
		font-size: 0.8125rem;
		color: var(--rd);
		padding: 0.75rem;
		display: flex;
		align-items: center;
		gap: 0.375rem;
	}
</style>
