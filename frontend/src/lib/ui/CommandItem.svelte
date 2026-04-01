<script>
	import { t } from '$lib/i18n/index.js';
	import { CheckCircle, XCircle, Terminal, ChevronDown, ChevronRight } from 'lucide-svelte';

	let { cmd, expanded = false, onToggle = () => {} } = $props();
</script>

<div class="cmd-item" class:cmd-pass={cmd.success} class:cmd-fail={!cmd.success}>
	<!-- svelte-ignore a11y_click_events_have_key_events -->
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div class="cmd-header" onclick={onToggle}>
		{#if cmd.success}
			<CheckCircle size={15} class="icon-pass" />
		{:else}
			<XCircle size={15} class="icon-fail" />
		{/if}
		<Terminal size={13} />
		<span class="cmd-name">{cmd.name}</span>
		<code class="cmd-code">{cmd.command}</code>
		<span class="cmd-exit">exit {cmd.exit_code}</span>
		{#if expanded}
			<ChevronDown size={14} />
		{:else}
			<ChevronRight size={14} />
		{/if}
	</div>
	{#if expanded}
		<div class="cmd-output">
			{#if cmd.stdout}<pre class="cmd-pre">{cmd.stdout}</pre>{/if}
			{#if cmd.stderr}<pre class="cmd-pre cmd-stderr">{cmd.stderr}</pre>{/if}
			{#if !cmd.stdout && !cmd.stderr}<span class="cmd-empty">{$t('tests.no_output')}</span>{/if}
		</div>
	{/if}
</div>

<style>
	.cmd-item { background: var(--bg-deep); border-radius: var(--r2); overflow: hidden; }

	.cmd-header {
		display: flex; align-items: center; gap: 0.5rem;
		padding: 0.375rem 0.625rem; cursor: pointer;
		font-size: 0.8125rem; color: var(--tx); transition: background 0.1s;
	}
	.cmd-header:hover { background: var(--sf2); }
	.cmd-name { font-weight: 500; }

	.cmd-code {
		font-size: 0.6875rem; color: var(--dm); background: var(--bg-high);
		padding: 0.0625rem 0.375rem; border-radius: 0.1875rem;
		font-family: var(--font-mono, monospace);
	}

	.cmd-exit {
		margin-left: auto; font-size: 0.6875rem;
		color: var(--dm); font-family: var(--font-ui);
	}

	.cmd-output {
		padding: 0.5rem 0.625rem; border-top: 1px solid var(--bd);
		max-height: 20rem; overflow-y: auto;
	}

	.cmd-pre {
		font-size: 0.75rem; font-family: var(--font-mono, monospace);
		white-space: pre-wrap; word-break: break-all;
		color: var(--tx); margin: 0; line-height: 1.5;
	}

	.cmd-stderr { color: var(--rd); }
	.cmd-empty { font-size: 0.75rem; color: var(--dm); }
</style>
