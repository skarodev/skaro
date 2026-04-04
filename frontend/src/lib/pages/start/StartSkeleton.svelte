<!--
	Skeleton placeholder for the Start page.
	Shown while data is loading to reduce layout shift.
-->
<div class="start-skel">
	<!-- Roadmap skeleton (early stage fallback) -->
	{#each Array(6) as _, i}
		<div class="skel-step">
			<div class="skel-marker"></div>
			<div class="skel-body">
				<div class="skel-line skel-title"></div>
				<div class="skel-line skel-desc"></div>
				<div class="skel-line skel-desc-short"></div>
			</div>
		</div>
	{/each}
</div>

<style>
	.start-skel {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		max-width: 40rem;
	}

	.skel-step {
		display: flex;
		gap: 1rem;
		padding: 1rem 1.25rem;
	}

	.skel-marker {
		width: 1.5rem;
		height: 1.5rem;
		border-radius: 50%;
		background: var(--bg-deep);
		flex-shrink: 0;
		animation: skel-pulse 1.5s ease-in-out infinite;
	}

	.skel-body {
		flex: 1;
		display: flex;
		flex-direction: column;
		gap: 0.375rem;
	}

	.skel-line {
		background: var(--bg-deep);
		border-radius: 0.25rem;
		animation: skel-pulse 1.5s ease-in-out infinite;
	}

	.skel-title {
		width: 35%;
		height: 0.875rem;
	}

	.skel-desc {
		width: 80%;
		height: 0.625rem;
	}

	.skel-desc-short {
		width: 55%;
		height: 0.625rem;
	}

	@keyframes skel-pulse {
		0%, 100% { opacity: 0.45; }
		50% { opacity: 0.2; }
	}
</style>
