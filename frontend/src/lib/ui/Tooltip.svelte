<script>
	/**
	 * Reusable animated tooltip component.
	 *
	 * Usage:
	 *   <Tooltip text="Label" placement="right">
	 *     <button>Hover me</button>
	 *   </Tooltip>
	 *
	 * Props:
	 *   text     — tooltip text
	 *   placement — "right" | "top" | "bottom" (default: "right")
	 *   disabled — suppress tooltip when true
	 */
	let {
		text = '',
		placement = 'right',
		disabled = false,
		children,
	} = $props();

	let visible = $state(false);
	let timeout = $state(null);

	function show() {
		if (disabled || !text) return;
		timeout = setTimeout(() => { visible = true; }, 80);
	}

	function hide() {
		clearTimeout(timeout);
		visible = false;
	}
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<span
	class="tooltip-anchor"
	onmouseenter={show}
	onmouseleave={hide}
	onfocusin={show}
	onfocusout={hide}
>
	{@render children()}
	{#if visible && text}
		<span class="tooltip tooltip-{placement}" role="tooltip">{text}</span>
	{/if}
</span>

<style>
	.tooltip-anchor {
		position: relative;
		display: inline-flex;
	}

	.tooltip {
		position: absolute;
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
		left: calc(100% + 0.5rem);
		top: 50%;
		transform: translateY(-50%);
	}

	.tooltip-top {
		bottom: calc(100% + 0.5rem);
		left: 50%;
		transform: translateX(-50%);
	}

	.tooltip-bottom {
		top: calc(100% + 0.5rem);
		left: 50%;
		transform: translateX(-50%);
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

	.tooltip-top {
		animation-name: tooltip-in-top;
	}

	@keyframes tooltip-in-top {
		from {
			opacity: 0;
			transform: translateX(-50%) translateY(4px);
		}
		to {
			opacity: 1;
			transform: translateX(-50%) translateY(0);
		}
	}

	.tooltip-bottom {
		animation-name: tooltip-in-bottom;
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
