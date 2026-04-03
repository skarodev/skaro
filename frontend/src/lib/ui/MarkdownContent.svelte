<script>
	import { renderMarkdown } from '$lib/utils/markdown.js';
	import { Copy, Check } from 'lucide-svelte';

	/** @type {{ content: string }} */
	let { content = '' } = $props();

	let container = $state(null);

	// After each render, inject copy buttons into <pre> blocks
	$effect(() => {
		// Subscribe to content so effect re-runs on change
		void content;
		if (!container) return;

		// Tick: wait for {@html} to be applied
		requestAnimationFrame(() => {
			const pres = container.querySelectorAll('pre');
			for (const pre of pres) {
				// Skip if already has a button
				if (pre.querySelector('.copy-btn')) continue;

				// Wrap pre in a relative container for absolute positioning
				pre.style.position = 'relative';

				const btn = document.createElement('button');
				btn.className = 'copy-btn';
				btn.type = 'button';
				btn.title = 'Скопировать';
				btn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/></svg>`;

				btn.addEventListener('click', async () => {
					const code = pre.querySelector('code');
					const text = (code || pre).textContent || '';
					try {
						await navigator.clipboard.writeText(text);
						btn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>`;
						btn.classList.add('copied');
						setTimeout(() => {
							btn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/></svg>`;
							btn.classList.remove('copied');
						}, 2000);
					} catch { /* clipboard not available */ }
				});

				pre.appendChild(btn);
			}
		});
	});
</script>

<div class="md-content" bind:this={container}>
	{@html renderMarkdown(content)}
</div>

<style>
	.md-content {
		line-height: 1.65;
		color: var(--tx);
		margin-bottom: 2rem;
	}

	.md-content :global(h1) {
		font-size: 1.3rem;
		margin: 1rem 0 0.5rem;
		padding-bottom: 0.25rem;
		color: var(--tx-bright);
	}

	.md-content :global(h2) {
		font-size: 1.2rem;
		margin: 1rem 0 .5rem;
		color: var(--ac);
	}

	.md-content :global(h3) {
		font-size: 1.1rem;
		margin: 1rem 0 .5rem;
		color: var(--tx-bright);
	}

	.md-content :global(p) {
		margin: 1rem 0;
	}

	.md-content :global(ul),
	.md-content :global(ol) {
		margin: 0.25rem 0 0.25rem 1.25rem;
	}

	.md-content :global(li) {
		margin: 0.125rem 0;
	}

	.md-content :global(pre) {
		position: relative;
		background: var(--bg-deep);
		border-radius: var(--r);
		padding: 1.2rem 1.5rem;
		overflow-x: auto;
		font-size: 0.8125rem;
		margin: 0.375rem 0;
		font-family: var(--font-ui);
	}

	.md-content :global(code) {
        background: rgb(from var(--ac) r g b / 0.05);
        border-radius: var(--r2);
        padding: .08rem .2rem .1rem .2rem;
        color: var(--ac);
        font-size: 1rem;
        border: solid 1px rgb(from var(--ac) r g b / 0.25);
	}

    .md-content :global(pre > code) {
        background: none;
        border-radius: 0;
        padding: inherit;
        color: inherit;
        font-size: inherit;
        border: none;
    }

	.md-content :global(.copy-btn) {
		position: absolute;
		top: 0.5rem;
		right: 0.5rem;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 1.75rem;
		height: 1.75rem;
		background: transparent;
		border: 0.0625rem solid var(--bd);
		border-radius: var(--r);
		color: var(--tx-dim);
		cursor: pointer;
		opacity: 0;
		transition: opacity 0.15s, color 0.15s, border-color 0.15s;
	}

	.md-content :global(pre:hover .copy-btn) {
		opacity: 1;
	}

	.md-content :global(.copy-btn:hover) {
		color: var(--tx-bright);
		border-color: var(--tx2);
	}

	.md-content :global(.copy-btn.copied) {
		color: var(--ok);
		border-color: var(--ok);
		opacity: 1;
	}

	.md-content :global(blockquote) {
		border-left: 0.1875rem solid var(--ac);
		padding-left: 0.625rem;
		color: var(--tx-dim);
		margin: 0.375rem 0;
	}

	.md-content :global(table) {
		border-collapse: separate;
		border-spacing: 0;
		width: 100%;
		margin: 0.375rem 0;
		background: var(--bg-deep);
		border-radius: var(--r);
		overflow: hidden;
		border: 1px solid var(--bd);
	}

	.md-content :global(thead) {
		background: var(--bd);
	}

	.md-content :global(th),
	.md-content :global(td) {
		border-bottom: 0.0625rem solid var(--bd);
		border-right: 0.0625rem solid var(--bd);
		padding: 0.5rem 0.75rem;
		text-align: left;
		font-size: 0.85rem;
		word-wrap: break-word;
		overflow-wrap: break-word;
	}

	/* Remove right border on last column */
	.md-content :global(th:last-child),
	.md-content :global(td:last-child) {
		border-right: none;
	}

	/* Remove bottom border on last row */
	.md-content :global(tr:last-child td) {
		border-bottom: none;
	}

	.md-content :global(th) {
		color: var(--tx-bright);
		font-weight: 600;
	}

	.md-content :global(hr) {
		border: none;
		border-top: 1px solid var(--bd);
		margin: 0.625rem 0;
	}

	.md-content :global(strong) {
		color: var(--tx-bright);
	}
</style>
