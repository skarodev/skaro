<script>
	/** @type {{ onResize: (ratio: number) => void }} */
	let { onResize } = $props();

	let dragging = $state(false);

	function onMouseDown(e) {
		e.preventDefault();
		dragging = true;
		const parent = e.currentTarget.parentElement;
		if (!parent) return;

		function onMouseMove(e) {
			const rect = parent.getBoundingClientRect();
			const x = e.clientX - rect.left;
			const ratio = Math.min(Math.max(x / rect.width, 0.15), 0.85);
			onResize(ratio);
		}

		function onMouseUp() {
			dragging = false;
			window.removeEventListener('mousemove', onMouseMove);
			window.removeEventListener('mouseup', onMouseUp);
		}

		window.addEventListener('mousemove', onMouseMove);
		window.addEventListener('mouseup', onMouseUp);
	}
</script>

<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
<div
	class="divider"
	class:dragging
	onmousedown={onMouseDown}
	role="separator"
	aria-orientation="vertical"
>
	<div class="handle"></div>
</div>

<style>
	.divider {
		width: 0.1875rem;
		flex-shrink: 0;
		display: flex;
		align-items: center;
		justify-content: center;
		cursor: col-resize;
		background: var(--bd);
		transition: background 0.1s;
		position: relative;
		z-index: 2;
	}

	.divider:hover,
	.divider.dragging {
		background: var(--bd2);
	}

	.handle {
		position: absolute;
		width: 0.5rem;
		height: 2.5rem;
		border-radius: var(--r2);
		background: var(--tx-dim);
		transition: background 0.1s;
	}

	.divider:hover .handle,
	.divider.dragging .handle {
		background: var(--ac);
	}
</style>
