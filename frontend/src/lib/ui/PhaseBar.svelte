<script>
    import { t } from '$lib/i18n/index.js';
    import { MessageCircle, ClipboardList, Code, FlaskConical, Check, CircleCheckBig } from 'lucide-svelte';

    /** @type {{ phases: Record<string, string> }} */
    let { phases } = $props();

    const phaseKeys = [
        { key: 'clarify', icon: MessageCircle },
        { key: 'plan', icon: ClipboardList },
        { key: 'implement', icon: Code },
        { key: 'tests', icon: FlaskConical },
        { key: 'done', icon: CircleCheckBig },
    ];

    let allComplete = $derived(
        ['clarify', 'plan', 'implement', 'tests'].every(k => phases[k] === 'complete')
    );

    function getStatus(key) {
        if (key === 'done') return allComplete ? 'complete' : 'not_started';
        return phases[key] || 'not_started';
    }

    function statusClass(status) {
        if (status === 'complete') return 'ok';
        if (['in_progress', 'draft', 'awaiting_review'].includes(status)) return 'wip';
        return '';
    }

    function statusColor(status) {
        if (status === 'complete') return 'var(--ok)';
        if (['in_progress', 'draft', 'awaiting_review'].includes(status)) return 'var(--warn)';
        return 'var(--bg-deep)';
    }
</script>

<div class="phase-bar">
    {#each phaseKeys as phase, i}
        {@const status = getStatus(phase.key)}
        {@const cls = statusClass(status)}
        {@const nextStatus = i < phaseKeys.length - 1 ? getStatus(phaseKeys[i + 1].key) : 'not_started'}
        {@const Icon = phase.icon}
        <div class="phase-cell">
            {#if i < phaseKeys.length - 1}
                <div class="phase-line" style="background: linear-gradient(to right, {statusColor(status)}, {statusColor(nextStatus)})"></div>
            {/if}
            <div class="dot {cls}">
                {#if cls === 'ok'}
                    <Check size={13} strokeWidth={2.5} />
                {:else}
                    <Icon size={13} strokeWidth={1.5} />
                {/if}
            </div>
            <span class="phase-lbl" class:lbl-ok={cls === 'ok'} class:lbl-wip={cls === 'wip'}>
				{$t('phase.' + phase.key)}
			</span>
        </div>
    {/each}
</div>

<style>
    .phase-bar {
        display: flex;
        align-items: flex-start;
        margin: 2.5rem 0;
    }

    .phase-cell {
        flex: 1;
        display: flex;
        flex-direction: column;
        align-items: center;
        position: relative;
    }

    .phase-line {
        position: absolute;
        top: 0.6875rem;
        left: 50%;
        right: -50%;
        height: 0.125rem;
        background: var(--bg-deep);
        z-index: 0;
        transition: background .2s;
    }

    .phase-cell:last-child .phase-line {
        display: none;
    }

    .dot {
        width: 1.5rem;
        height: 1.5rem;
        border-radius: 50%;
        border: 0.125rem solid var(--bg-deep);
        flex-shrink: 0;
        position: relative;
        z-index: 1;
        display: flex;
        align-items: center;
        justify-content: center;
        color: var(--tx);
        background: var(--bg-deep);
        transition: all .2s;
    }

    .dot.ok {
        background: var(--ok);
        border-color: var(--ok);
        color: #fff;
    }

    .dot.wip {
        background: var(--warn);
        border-color: var(--warn);
        color: var(--bg-deep);
    }

    .phase-lbl {
        font-size: .7rem;
        color: var(--tx);
        margin-top: 0.375rem;
        white-space: nowrap;
        text-align: center;
        font-family: var(--font-ui);
        transition: color .2s;
    }

    .phase-lbl.lbl-ok { color: var(--ok); }
    .phase-lbl.lbl-wip { color: var(--warn); }
</style>
