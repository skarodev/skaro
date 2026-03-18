<script>
	import { t } from '$lib/i18n/index.js';
	import { Search, ClipboardList, Hammer, FlaskConical, Loader2 } from 'lucide-svelte';

	let {
		phases = {},
		currentStage = 0,
		totalStages = 0,
		actionLoading = '',
		hasUnanswered = false,
		onClarify = () => {},
		onPlan = () => {},
		onImplement = () => {},
		onTests = () => {},
	} = $props();
</script>

<div class="actions-block">
	{#if phases.clarify !== 'complete' && !hasUnanswered}
		<p class="phase-hint"><strong>{$t('phase_hint.prefix')}</strong>{$t('phase_hint.clarify')}</p>
		<div class="btn-group">
			<button class="btn btn-primary" disabled={!!actionLoading} onclick={onClarify}>
				{#if actionLoading === 'clarify'}<Loader2 size={14} class="spin" />{:else}<Search size={14} />{/if}
				{$t('action.clarify')}
			</button>
		</div>

	{:else if phases.clarify === 'complete' && !hasUnanswered && phases.plan !== 'complete'}
		<p class="phase-hint"><strong>{$t('phase_hint.prefix')}</strong>{$t('phase_hint.plan')}</p>
		<div class="btn-group">
			<button class="btn btn-primary" disabled={!!actionLoading} onclick={onPlan}>
				{#if actionLoading === 'plan'}<Loader2 size={14} class="spin" />{:else}<ClipboardList size={14} />{/if}
				{$t('action.gen_plan')}
			</button>
		</div>

	{:else if phases.plan === 'complete' && (totalStages === 0 || currentStage + 1 <= totalStages)}
		{@const nextStage = currentStage + 1}
		<p class="phase-hint"><strong>{$t('phase_hint.prefix')}</strong>{$t('phase_hint.implement', { n: nextStage, total: totalStages || '?' })}</p>
		<div class="btn-group">
			<button class="btn btn-primary" disabled={!!actionLoading} onclick={onImplement}>
				{#if actionLoading === 'implement'}<Loader2 size={14} class="spin" />{:else}<Hammer size={14} />{/if}
				{$t('action.implement_stage', { n: nextStage })}
			</button>
		</div>

	{:else if phases.tests !== 'complete' && (phases.implement === 'complete' || (currentStage > 0 && currentStage >= totalStages))}
		<p class="phase-hint"><strong>{$t('phase_hint.prefix')}</strong>{$t('phase_hint.tests')}</p>
		<div class="btn-group">
			<button class="btn btn-primary" disabled={!!actionLoading} onclick={onTests}>
				{#if actionLoading === 'tests'}<Loader2 size={14} class="spin" />{:else}<FlaskConical size={14} />{/if}
				{$t('action.run_tests')}
			</button>
		</div>
	{/if}
</div>



<style>
	.actions-block {
		margin: 0.75rem 0;
	}

    .phase-hint {
        margin: 1.5rem 0 0;
        padding: 1rem .9rem;
        font-size: .9rem;
        color: var(--dm);
        background: var(--bg2);
        line-height: 1.5;
        border: .0625rem solid var(--bd);
        border-radius: var(--r);
    }
</style>
