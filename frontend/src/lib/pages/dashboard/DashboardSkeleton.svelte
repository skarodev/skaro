<!--
	Skeleton placeholder that mimics the dashboard grid layout.
	Shown while data is loading to reduce layout shift.
-->
<div class="dash-grid">
	<!-- Row 1: pipeline + 4× summary -->
	<div class="widget lg skel-card skel-pipeline">
		<div class="skel-line skel-h3"></div>
		<div class="skel-steps">
			{#each Array(5) as _}
				<div class="skel-step"></div>
			{/each}
		</div>
	</div>

	{#each Array(4) as _}
		<div class="widget sm skel-card skel-summary">
			<div class="skel-line skel-big"></div>
			<div class="skel-line skel-label"></div>
		</div>
	{/each}

	<!-- Row 2: tasks overview + files by type -->
	<div class="widget lg skel-card">
		<div class="skel-line skel-h3"></div>
		<div class="skel-feat-grid">
			{#each Array(4) as _}
				<div class="skel-feat"></div>
			{/each}
		</div>
	</div>

	<div class="widget lg skel-card skel-chart">
		<div class="skel-line skel-h3"></div>
		<div class="skel-chart-row">
			<div class="skel-donut"></div>
			<div class="skel-legend">
				{#each Array(5) as _}
					<div class="skel-line skel-leg-row"></div>
				{/each}
			</div>
		</div>
	</div>

	<!-- Row 3: LLM config + by model + by role -->
	<div class="widget lg skel-card">
		<div class="skel-line skel-h3"></div>
		<div class="skel-flex-row">
			{#each Array(3) as _}
				<div class="skel-tag"></div>
			{/each}
		</div>
	</div>

	<div class="widget md skel-card">
		<div class="skel-line skel-h3"></div>
		{#each Array(3) as _}
			<div class="skel-line skel-table-row"></div>
		{/each}
	</div>

	<div class="widget md skel-card">
		<div class="skel-line skel-h3"></div>
		{#each Array(3) as _}
			<div class="skel-line skel-table-row"></div>
		{/each}
	</div>
</div>

<style>
	.dash-grid {
		display: grid;
		grid-template-columns: repeat(8, 1fr);
		gap: 1rem;
	}

	.dash-grid > :global(.widget.lg) { grid-column: span 4; }
	.dash-grid > :global(.widget.md) { grid-column: span 2; }
	.dash-grid > :global(.widget.sm) { grid-column: span 1; }

	.skel-card {
		background: var(--sf);
		border-radius: var(--r);
		padding: 1rem 0.875rem;
	}

	/* ── Skeleton primitives ─────────── */

	.skel-line {
		background: var(--bg2);
		border-radius: 0.25rem;
		animation: skel-pulse 1.5s ease-in-out infinite;
	}

	.skel-h3 {
		width: 40%;
		height: 0.875rem;
		margin-bottom: 0.875rem;
	}

	/* ── Pipeline skeleton ─────────── */

	.skel-pipeline { display: flex; flex-direction: column; justify-content: center; }

	.skel-steps {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		margin-top: 0.375rem;
	}

	.skel-step {
		flex: 1;
		height: 2.25rem;
		background: var(--bg2);
		border-radius: var(--r);
		animation: skel-pulse 1.5s ease-in-out infinite;
	}

	/* ── Summary card skeleton ─────── */

	.skel-summary {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 0.5rem;
	}

	.skel-big {
		width: 3.5rem;
		height: 1.5rem;
	}

	.skel-label {
		width: 5rem;
		height: 0.625rem;
	}

	/* ── Tasks grid skeleton ────────── */

	.skel-feat-grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(12.5rem, 1fr));
		gap: 0.625rem;
	}

	.skel-feat {
		height: 4.5rem;
		background: var(--bg2);
		border-radius: var(--r2);
		animation: skel-pulse 1.5s ease-in-out infinite;
	}

	/* ── Chart skeleton ───────────── */

	.skel-chart-row {
		display: flex;
		align-items: flex-start;
		gap: 1.75rem;
	}

	.skel-donut {
		width: 10rem;
		height: 10rem;
		border-radius: 50%;
		background: var(--bg2);
		flex-shrink: 0;
		animation: skel-pulse 1.5s ease-in-out infinite;
	}

	.skel-legend {
		flex: 1;
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		padding-top: 0.5rem;
	}

	.skel-leg-row {
		width: 100%;
		height: 1.25rem;
	}

	/* ── Misc skeleton rows ────────── */

	.skel-flex-row {
		display: flex;
		gap: 0.5rem;
		flex-wrap: wrap;
	}

	.skel-tag {
		width: 8rem;
		height: 2.5rem;
		background: var(--bg2);
		border-radius: var(--r2);
		animation: skel-pulse 1.5s ease-in-out infinite;
	}

	.skel-table-row {
		width: 100%;
		height: 1.125rem;
		margin-bottom: 0.375rem;
	}

	/* ── Pulse animation ──────────── */

	@keyframes skel-pulse {
		0%, 100% { opacity: 0.45; }
		50% { opacity: 0.2; }
	}
</style>
