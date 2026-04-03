<script>
	import { t } from '$lib/i18n/index.js';
	import { FolderOpen, Paperclip } from 'lucide-svelte';

	let {
		open = false,
		onAttachFromDisk = () => {},
		onAttachFromRepo = () => {},
		onClose = () => {},
	} = $props();

	let menuEl = $state(null);

	$effect(() => {
		if (open) {
			const handler = (e) => {
				if (menuEl && !menuEl.contains(e.target)) onClose();
			};
			requestAnimationFrame(() =>
				document.addEventListener('click', handler, true)
			);
			return () => document.removeEventListener('click', handler, true);
		}
	});
</script>

{#if open}
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<!-- svelte-ignore a11y_click_events_have_key_events -->
	<div class="attach-menu" bind:this={menuEl} onclick={(e) => e.stopPropagation()}>
		<button class="attach-item" onclick={() => { onAttachFromDisk(); onClose(); }}>
			<Paperclip size={14} />
			<span>{$t('attach.from_disk')}</span>
		</button>
		<button class="attach-item" onclick={() => { onAttachFromRepo(); onClose(); }}>
			<FolderOpen size={14} />
			<span>{$t('attach.from_repo')}</span>
		</button>
	</div>
{/if}

<style>
	.attach-menu {
		position: absolute;
		bottom: calc(100% + 0.375rem);
		left: 0;
		z-index: 100;
		background: var(--bg-soft);
		border: 0.0625rem solid var(--bd2);
		border-radius: var(--r);
		box-shadow: 0 -0.25rem 1rem rgba(0, 0, 0, .25);
		padding: 0.25rem;
		white-space: nowrap;
	}

	.attach-item {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		width: 100%;
		padding: 0.4375rem 0.75rem;
		border: none;
		border-radius: var(--r2);
		background: none;
		color: var(--tx);
		font-size: 0.8125rem;
		font-family: inherit;
		cursor: pointer;
		text-align: left;
		transition: background 0.1s;
		white-space: nowrap;
	}

	.attach-item:hover {
		background: var(--bg-deep);
	}
</style>
