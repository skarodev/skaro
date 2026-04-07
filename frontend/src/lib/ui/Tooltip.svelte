<script>
	/**
	 * Reusable animated tooltip component.
	 *
	 * Uses position:fixed to escape overflow containers (e.g. sidebar).
	 * Automatically clamps position to stay within the viewport.
	 *
	 * Props:
	 *   text      — tooltip text
	 *   placement — "right" | "top" | "bottom" (default: "right")
	 *   disabled  — suppress tooltip when true
	 */
	let {
		text = '',
		placement = 'right',
		disabled = false,
		children,
	} = $props();

	let visible = $state(false);
	let timeout = $state(null);
	let anchor = $state(null);
	let tooltipEl = $state(null);
	let pos = $state({ top: 0, left: 0 });

	const MARGIN = 8;

	function calcPosition() {
		if (!anchor) return;
		const rect = anchor.getBoundingClientRect();
		if (placement === 'right') {
			pos = {
				top: rect.top + rect.height / 2,
				left: rect.right + 8,
			};
		} else if (placement === 'top') {
			pos = {
				top: rect.top - 8,
				left: rect.left + rect.width / 2,
			};
		} else {
			pos = {
				top: rect.bottom + 8,
				left: rect.left + rect.width / 2,
			};
		}
	}

	function clampToViewport() {
		if (!tooltipEl) return;
		const tr = tooltipEl.getBoundingClientRect();
		const vw = window.innerWidth;
		const vh = window.innerHeight;
		let dx = 0, dy = 0;

		if (tr.right > vw - MARGIN) dx = vw - MARGIN - tr.right;
		if (tr.left < MARGIN) dx = MARGIN - tr.left;
		if (tr.bottom > vh - MARGIN) dy = vh - MARGIN - tr.bottom;
		if (tr.top < MARGIN) dy = MARGIN - tr.top;

		if (dx || dy) {
			pos = { top: pos.top + dy, left: pos.left + dx };
		}
	}

	function show() {
		if (disabled || !text) return;
		timeout = setTimeout(() => {
			calcPosition();
			visible = true;
			requestAnimationFrame(clampToViewport);
		}, 80);
	}

	function hide() {
		clearTimeout(timeout);
		visible = false;
	}
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<span
	class="tooltip-anchor"
	bind:this={anchor}
	onmouseenter={show}
	onmouseleave={hide}
	onfocusin={show}
	onfocusout={hide}
>
	{@render children()}
	{#if visible && text}
		<span
			class="tooltip tooltip-{placement}"
			role="tooltip"
			style="top: {pos.top}px; left: {pos.left}px;"
			bind:this={tooltipEl}
		>{text}</span>
	{/if}
</span>

<style>
	.tooltip-anchor {
		position: relative;
		display: inline-flex;
	}

	.tooltip {
		position: fixed;
		white-space: nowrap;
		padding: 0.375rem 0.625rem;
		border-radius: 0.375rem;
		background: var(--bg-deep);
		color: var(--tx);
		font-size: 0.8125rem;
		line-height: 1.25;
		pointer-events: none;
		z-index: 1000;
		animation: tooltip-in 0.15s ease-out;
		box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
	}

	.tooltip-right {
		transform: translateY(-50%);
	}

	.tooltip-top {
		transform: translate(-50%, -100%);
		animation-name: tooltip-in-top;
	}

	.tooltip-bottom {
		transform: translateX(-50%);
		animation-name: tooltip-in-bottom;
	}

	@keyframes tooltip-in {
		from {
			opacity: 0;
			transform: translateY(-50%) translateX(-4px);
		}
		to {
			opacity: 1;
			transform: translateY(-50%) translateX(0);
		}
	}

	@keyframes tooltip-in-top {
		from {
			opacity: 0;
			transform: translate(-50%, -100%) translateY(4px);
		}
		to {
			opacity: 1;
			transform: translate(-50%, -100%) translateY(0);
		}
	}

	@keyframes tooltip-in-bottom {
		from {
			opacity: 0;
			transform: translateX(-50%) translateY(-4px);
		}
		to {
			opacity: 1;
			transform: translateX(-50%) translateY(0);
		}
	}
</style>
