<script>
	import { t } from '$lib/i18n/index.js';
	import { api } from '$lib/api/client.js';
	import { addLog, addError } from '$lib/stores/logStore.js';
	import { Pencil } from 'lucide-svelte';
	import MarkdownContent from '$lib/ui/MarkdownContent.svelte';
	import MdEditor from '$lib/ui/md-editor/MdEditor.svelte';

	let { slug = '', plan = '', onSave = () => {} } = $props();

	let showEditor = $state(false);

	async function savePlan(content) {
		try {
			const result = await api.saveFeaturePlan(slug, content);
			if (result.success) {
				addLog($t('feature.plan_saved'));
				showEditor = false;
				onSave();
			} else { addError(result.message, 'featurePlan'); }
		} catch (e) { addError(e.message, 'featurePlan'); }
	}
</script>

<div class="plan-actions">
	<button class="btn" onclick={() => showEditor = true}>
		<Pencil size={14} /> {$t('editor.edit')}
	</button>
</div>

{#if plan.trim()}
	<MarkdownContent content={plan} />
{:else}
	<div class="empty-hint">{$t('feature.no_plan')}</div>
{/if}

{#if showEditor}
	<MdEditor
		content={plan}
		onSave={(c) => savePlan(c)}
		onClose={() => showEditor = false}
	/>
{/if}

<style>
	.plan-actions {
		display: flex;
		gap: 0.5rem;
		margin-bottom: 0.75rem;
	}
	.empty-hint { color: var(--tx-dim); font-size: 0.8125rem; }
</style>
