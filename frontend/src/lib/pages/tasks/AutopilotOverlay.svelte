<script>
	import { t } from '$lib/i18n/index.js';
	import { status } from '$lib/stores/statusStore.js';
	import { invalidate } from '$lib/api/cache.js';
	import { api } from '$lib/api/client.js';
	import { portal } from '$lib/utils/portal.js';
	import { llmActive, llmText } from '$lib/stores/logStore.js';
	import { fmt } from '$lib/utils/format.js';
	import {
		autopilotVisible,
		autopilotRunning,
		autopilotStopping,
		autopilotStopped,
		autopilotCurrentTask,
		autopilotCurrentPhase,
		autopilotStageInfo,
		autopilotQueue,
		autopilotCounts,
		autopilotLog,
		autopilotTaskStatus,
		autopilotError,
		autopilotElapsed,
		autopilotResult,
		autopilotProgress,
		stopAutopilot,
		closeAutopilot,
	} from '$lib/stores/autopilotStore.js';
	import {
		Rocket, Square, X, CheckCircle2, AlertTriangle,
		Loader2, Search, ClipboardList, Hammer, FlaskConical,
		Clock, Zap, ChevronDown, ChevronUp, Cpu, StopCircle,
		Eye, EyeOff,
	} from 'lucide-svelte';
	import KittIndicator from '$lib/ui/KittIndicator.svelte';

	const PHASE_ICONS = { clarify: Search, plan: ClipboardList, implement: Hammer, tests: FlaskConical };
	const PHASE_ORDER = ['clarify', 'plan', 'implement', 'tests'];

	let logExpanded = $state(true);
	let logEl = $state(null);
	let thinkingExpanded = $state(true);
	let thinkingEl = $state(null);

	// Auto-scroll log
	$effect(() => {
		// eslint-disable-next-line no-unused-expressions
		$autopilotLog.length;
		if (logEl) {
			requestAnimationFrame(() => {
				logEl.scrollTop = logEl.scrollHeight;
			});
		}
	});

	// Auto-scroll thinking
	$effect(() => {
		// eslint-disable-next-line no-unused-expressions
		$llmText;
		if (thinkingEl && thinkingExpanded) {
			requestAnimationFrame(() => {
				thinkingEl.scrollTop = thinkingEl.scrollHeight;
			});
		}
	});

	// Refresh global status when autopilot finishes
	$effect(() => {
		if ($autopilotResult || $autopilotError || $autopilotStopped) {
			refreshStatus();
		}
	});

	async function refreshStatus() {
		try {
			invalidate('status');
			status.set(await api.getStatus());
		} catch { /* non-critical */ }
	}

	function formatElapsed(seconds) {
		const m = Math.floor(seconds / 60);
		const s = seconds % 60;
		return m > 0 ? `${m}m ${s}s` : `${s}s`;
	}

	function handleClose() {
		if ($autopilotRunning) return;
		closeAutopilot();
	}

	function handleStop() {
		stopAutopilot();
	}

	// ── Model info from status ──
	let modelInfo = $derived.by(() => {
		const cfg = $status?.config;
		if (!cfg) return '';
		// During autopilot, tasks use 'coder' role
		if (cfg.roles?.coder) {
			const r = cfg.roles.coder;
			return `${r.provider} / ${r.model}`;
		}
		return `${cfg.llm_provider} / ${cfg.llm_model}`;
	});

	// ── Token count from status ──
	let totalTokens = $derived($status?.tokens?.total_tokens || 0);

	/** Phase dot class for a task. */
	function phaseDotClass(taskName, phase) {
		const taskStatus = $autopilotTaskStatus[taskName];
		if (taskStatus === 'done') return 'dot-done';
		if (taskStatus === 'error' && $autopilotError?.task === taskName && $autopilotError?.phase === phase) {
			return 'dot-error';
		}
		if (taskStatus === 'running' && $autopilotCurrentTask === taskName) {
			const currentIdx = PHASE_ORDER.indexOf($autopilotCurrentPhase);
			const phaseIdx = PHASE_ORDER.indexOf(phase);
			if (phaseIdx < currentIdx) return 'dot-done';
			if (phaseIdx === currentIdx) return 'dot-active';
		}
		return 'dot-pending';
	}

	function logTypeClass(type) {
		if (type === 'error') return 'log-error';
		if (type === 'system') return 'log-system';
		if (type === 'task') return 'log-task';
		return 'log-phase';
	}
</script>

{#if $autopilotVisible}
<div class="overlay" use:portal role="dialog" aria-modal="true" aria-label={$t('autopilot.title')}>
	<div class="mc-container">
		<!-- ── Header ── -->
		<header class="mc-header">
			<div class="mc-header-left">
				<div class="mc-logo">
					<Rocket size={20} />
					<span class="mc-title">{$t('autopilot.title')}</span>
				</div>
				{#if $autopilotStopping}
					<span class="mc-badge stopping">
						<Loader2 size={14} class="spin" />
						{$t('autopilot.stopping')}
					</span>
				{:else if $autopilotRunning}
					<span class="mc-badge running">
						<span class="pulse-dot"></span>
						{$t('autopilot.running')}
					</span>
				{:else if $autopilotResult}
					<span class="mc-badge done">
						<CheckCircle2 size={14} />
						{$t('autopilot.completed')}
					</span>
				{:else if $autopilotError}
					<span class="mc-badge error">
						<AlertTriangle size={14} />
						{$t('autopilot.error_stopped')}
					</span>
				{:else if $autopilotStopped}
					<span class="mc-badge stopped">
						<StopCircle size={14} />
						{$t('autopilot.stopped_by_user')}
					</span>
				{/if}
				{#if modelInfo}
					<span class="mc-badge model">
						<Cpu size={12} />
						{modelInfo}
					</span>
				{/if}
			</div>
			<div class="mc-header-right">
				<div class="mc-stat" title={$t('autopilot.tokens_total')}>
					<Zap size={14} />
					<span>{fmt(totalTokens)}</span>
				</div>
				<div class="mc-stat">
					<Clock size={14} />
					<span>{formatElapsed($autopilotElapsed)}</span>
				</div>
				<div class="mc-stat">
					<CheckCircle2 size={14} />
					<span>{$autopilotCounts.completed}/{$autopilotCounts.pending}</span>
				</div>
				{#if $autopilotRunning}
					<button class="mc-btn mc-btn-stop" disabled={$autopilotStopping} onclick={handleStop}>
						{#if $autopilotStopping}
							<Loader2 size={14} class="spin" /> {$t('autopilot.stopping')}
						{:else}
							<Square size={14} /> {$t('autopilot.stop')}
						{/if}
					</button>
				{:else}
					<button class="mc-btn mc-btn-close" onclick={handleClose}>
						<X size={14} /> {$t('autopilot.close')}
					</button>
				{/if}
			</div>
		</header>

		<!-- ── Main content ── -->
		<div class="mc-body">
			<!-- Left: Task list -->
			<aside class="mc-sidebar">
				<div class="mc-sidebar-title">{$t('autopilot.queue')}</div>
				<div class="mc-task-list">
					{#each $autopilotQueue as task (task.name)}
						{@const taskSt = $autopilotTaskStatus[task.name] || 'pending'}
						{@const isCurrent = $autopilotCurrentTask === task.name && $autopilotRunning}
						<div
							class="mc-task-item"
							class:mc-task-current={isCurrent}
							class:mc-task-done={taskSt === 'done'}
							class:mc-task-error={taskSt === 'error'}
						>
							<div class="mc-task-status-icon">
								{#if taskSt === 'done'}
									<CheckCircle2 size={16} />
								{:else if taskSt === 'error'}
									<AlertTriangle size={16} />
								{:else if isCurrent}
									<Loader2 size={16} class="spin" />
								{:else}
									<span class="mc-task-dot"></span>
								{/if}
							</div>
							<div class="mc-task-info">
								<span class="mc-task-name">{task.name}</span>
								<!-- Phase dots -->
								<div class="mc-phase-dots">
									{#each PHASE_ORDER as phase}
										<span
											class="mc-dot {phaseDotClass(task.name, phase)}"
											title={phase}
										></span>
									{/each}
								</div>
							</div>
						</div>
					{/each}
					{#if $autopilotQueue.length === 0 && !$autopilotRunning}
						<div class="mc-empty">{$t('autopilot.no_tasks')}</div>
					{/if}
				</div>
			</aside>

			<!-- Center: current task focus -->
			<main class="mc-main">
				<!-- Progress bar -->
				<div class="mc-progress-wrap">
					<div class="mc-progress-track">
						<div
							class="mc-progress-fill"
							class:mc-progress-complete={$autopilotProgress >= 100 && !$autopilotRunning}
							style="width: {$autopilotProgress}%"
						></div>
					</div>
					<span class="mc-progress-label">{$autopilotProgress}%</span>
				</div>

				<!-- Current task card -->
				{#if $autopilotRunning && $autopilotCurrentTask}
					<div class="mc-focus-card">
						<div class="mc-focus-header">
							<h3>{$autopilotCurrentTask}</h3>
							<span class="mc-focus-phase">
								{#if PHASE_ICONS[$autopilotCurrentPhase]}
									{@const PhaseIcon = PHASE_ICONS[$autopilotCurrentPhase]}
									<PhaseIcon size={16} />
								{/if}
								{$t(`phase.${$autopilotCurrentPhase}`) || $autopilotCurrentPhase}
								{#if $autopilotCurrentPhase === 'implement' && $autopilotStageInfo.total_stages > 0}
									<span class="mc-stage-badge">
										{$autopilotStageInfo.stage}/{$autopilotStageInfo.total_stages}
									</span>
								{/if}
							</span>
						</div>

						<!-- Phase pipeline viz -->
						<div class="mc-pipeline">
							{#each PHASE_ORDER as phase, i}
								{@const currentIdx = PHASE_ORDER.indexOf($autopilotCurrentPhase)}
								{@const isActive = i === currentIdx}
								{@const isDone = i < currentIdx}
								<div
									class="mc-pipe-step"
									class:mc-pipe-active={isActive}
									class:mc-pipe-done={isDone}
								>
									<div class="mc-pipe-icon">
										{#if isDone}
											<CheckCircle2 size={18} />
										{:else if isActive}
											<Loader2 size={18} class="spin" />
										{:else}
											{@const PipeIcon = PHASE_ICONS[phase]}
											<PipeIcon size={18} />
										{/if}
									</div>
									<span class="mc-pipe-label">{$t(`phase.${phase}`)}</span>
								</div>
								{#if i < PHASE_ORDER.length - 1}
									<div class="mc-pipe-connector" class:mc-pipe-connector-done={isDone}></div>
								{/if}
							{/each}
						</div>

						<!-- Implement stage progress -->
						{#if $autopilotCurrentPhase === 'implement' && $autopilotStageInfo.total_stages > 0}
							<div class="mc-stages-progress">
								{#each Array($autopilotStageInfo.total_stages) as _, idx}
									<div
										class="mc-stage-cell"
										class:mc-stage-done={idx + 1 < $autopilotStageInfo.stage}
										class:mc-stage-active={idx + 1 === $autopilotStageInfo.stage}
									>
										{idx + 1}
									</div>
								{/each}
							</div>
						{/if}

						<div class="mc-focus-spinner">
							<KittIndicator cells={16} speed={1100} />
							<span>
								{#if $autopilotCurrentPhase === 'clarify'}
									{$t('autopilot.auto_clarifying')}
								{:else if $autopilotCurrentPhase === 'plan'}
									{$t('autopilot.planning')}
								{:else if $autopilotCurrentPhase === 'implement'}
									{$t('autopilot.implementing')}
								{:else if $autopilotCurrentPhase === 'tests'}
									{$t('autopilot.testing')}
								{:else}
									{$t('autopilot.processing')}
								{/if}
							</span>
						</div>
					</div>

					<!-- LLM Thinking block -->
					{#if $llmActive && $llmText}
						<div class="mc-thinking">
							<button class="mc-thinking-header" onclick={() => thinkingExpanded = !thinkingExpanded}>
								<span class="mc-thinking-title">
									<KittIndicator cells={10} speed={1000} />
									{$t('autopilot.llm_thinking')}
								</span>
								{#if thinkingExpanded}
									<EyeOff size={14} />
								{:else}
									<Eye size={14} />
								{/if}
							</button>
							{#if thinkingExpanded}
								<div class="mc-thinking-body" bind:this={thinkingEl}>
									<pre>{$llmText}</pre>
								</div>
							{/if}
						</div>
					{/if}

				{:else if $autopilotResult}
					<!-- Completion card -->
					<div class="mc-result-card mc-result-success">
						<CheckCircle2 size={48} />
						<h3>{$t('autopilot.all_done')}</h3>
						<p>
							{$t('autopilot.summary', {
								completed: $autopilotResult.completed,
								total: $autopilotResult.total,
								time: formatElapsed(Math.round($autopilotResult.elapsed)),
							})}
						</p>
					</div>

				{:else if $autopilotError}
					<!-- Error card -->
					<div class="mc-result-card mc-result-error">
						<AlertTriangle size={48} />
						<h3>{$t('autopilot.error_title')}</h3>
						{#if $autopilotError.task}
							<p class="mc-error-task">
								{$t('autopilot.error_at', { task: $autopilotError.task, phase: $autopilotError.phase })}
							</p>
						{/if}
						<p class="mc-error-message">{$autopilotError.message}</p>
					</div>

				{:else if $autopilotStopped}
					<!-- Stopped by user card -->
					<div class="mc-result-card mc-result-stopped">
						<StopCircle size={48} />
						<h3>{$t('autopilot.stopped_title')}</h3>
						<p>{$t('autopilot.stopped_desc')}</p>
					</div>

				{:else if !$autopilotRunning}
					<div class="mc-result-card mc-result-idle">
						<Rocket size={48} />
						<h3>{$t('autopilot.ready')}</h3>
					</div>
				{/if}
			</main>

			<!-- Right: Event log -->
			<aside class="mc-log">
				<button class="mc-log-header" onclick={() => logExpanded = !logExpanded}>
					<span>{$t('autopilot.event_log')}</span>
					<span class="mc-log-count">{$autopilotLog.length}</span>
					{#if logExpanded}
						<ChevronDown size={14} />
					{:else}
						<ChevronUp size={14} />
					{/if}
				</button>
				{#if logExpanded}
					<div class="mc-log-body" bind:this={logEl}>
						{#each $autopilotLog as entry}
							<div class="mc-log-entry {logTypeClass(entry.type)}">
								<span class="mc-log-time">{entry.time}</span>
								{#if entry.task}
									<span class="mc-log-tag">{entry.task}</span>
								{/if}
								<span class="mc-log-msg">{entry.message}</span>
							</div>
						{/each}
						{#if $autopilotLog.length === 0}
							<div class="mc-log-empty">{$t('autopilot.no_events')}</div>
						{/if}
					</div>
				{/if}
			</aside>
		</div>
	</div>
</div>
{/if}

<style>
	/* ── Overlay ── */
	.overlay {
		position: fixed;
		inset: 0;
		z-index: 9999;
		background: rgba(0, 0, 0, 0.85);
		backdrop-filter: blur(8px);
		display: flex;
		align-items: center;
		justify-content: center;
		animation: fadeIn 0.3s ease;
	}

	@keyframes fadeIn {
		from { opacity: 0; }
		to { opacity: 1; }
	}

	.mc-container {
		width: 96vw;
		height: 92vh;
		max-width: 1600px;
		background: var(--bg-deep);
		border: 1px solid var(--bd);
		border-radius: 0.75rem;
		display: flex;
		flex-direction: column;
		overflow: hidden;
		box-shadow: 0 0 80px rgba(88, 157, 246, 0.08), 0 0 2px rgba(88, 157, 246, 0.3);
	}

	/* ── Header ── */
	.mc-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 0.75rem 1.25rem;
		background: var(--bg-high);
		border-bottom: 1px solid var(--bd);
		flex-shrink: 0;
	}

	.mc-header-left, .mc-header-right {
		display: flex;
		align-items: center;
		gap: 1rem;
	}

	.mc-logo {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		color: var(--ac);
	}

	.mc-title {
		font-family: var(--font-ui);
		font-size: 1rem;
		font-weight: 600;
		color: var(--tx-bright);
		letter-spacing: 0.04em;
		text-transform: uppercase;
	}

	.mc-badge {
		display: inline-flex;
		align-items: center;
		gap: 0.375rem;
		padding: 0.25rem 0.625rem;
		border-radius: 1rem;
		font-size: 0.75rem;
		font-family: var(--font-ui);
		font-weight: 500;
	}

	.mc-badge.running {
		background: rgba(88, 157, 246, 0.15);
		color: var(--ac);
	}

	.mc-badge.done {
		background: rgba(106, 135, 89, 0.2);
		color: var(--gn-bright);
	}

	.mc-badge.error {
		background: rgba(244, 71, 71, 0.15);
		color: var(--rd);
	}

	.mc-badge.stopping {
		background: rgba(255, 198, 109, 0.15);
		color: var(--yl);
	}

	.mc-badge.stopped {
		background: rgba(255, 198, 109, 0.12);
		color: var(--yl-dim);
	}

	.mc-badge.model {
		background: rgba(152, 118, 170, 0.12);
		color: var(--purple);
		font-family: var(--font-ui);
		font-size: 0.6875rem;
	}

	.pulse-dot {
		width: 8px;
		height: 8px;
		border-radius: 50%;
		background: var(--ac);
		animation: pulse 1.5s ease-in-out infinite;
	}

	@keyframes pulse {
		0%, 100% { opacity: 1; transform: scale(1); }
		50% { opacity: 0.4; transform: scale(0.75); }
	}

	.mc-stat {
		display: flex;
		align-items: center;
		gap: 0.375rem;
		font-family: var(--font-ui);
		font-size: 0.8125rem;
		color: var(--dm);
	}

	.mc-btn {
		display: inline-flex;
		align-items: center;
		gap: 0.375rem;
		padding: 0.375rem 0.875rem;
		border: 1px solid var(--bd);
		border-radius: var(--r);
		background: none;
		color: var(--tx-bright);
		font-family: var(--font-ui);
		font-size: 0.8125rem;
		cursor: pointer;
		transition: all 0.15s;
	}

	.mc-btn-stop {
		border-color: var(--rd-dim);
		color: var(--rd);
	}

	.mc-btn-stop:hover {
		background: rgba(244, 71, 71, 0.1);
	}

	.mc-btn-stop:disabled {
		opacity: 0.5;
		cursor: not-allowed;
		border-color: var(--dm2);
		color: var(--yl);
	}

	.mc-btn-stop:disabled:hover {
		background: none;
	}

	.mc-btn-close:hover {
		background: var(--sf);
	}

	/* ── Body layout ── */
	.mc-body {
		flex: 1;
		display: grid;
		grid-template-columns: 260px 1fr 300px;
		min-height: 0;
		overflow: hidden;
	}

	/* ── Sidebar (task list) ── */
	.mc-sidebar {
		border-right: 1px solid var(--bd);
		display: flex;
		flex-direction: column;
		overflow: hidden;
	}

	.mc-sidebar-title {
		padding: 0.75rem 1rem;
		font-size: 0.6875rem;
		font-family: var(--font-ui);
		text-transform: uppercase;
		letter-spacing: 0.08em;
		color: var(--dm);
		border-bottom: 1px solid var(--bd);
		flex-shrink: 0;
	}

	.mc-task-list {
		flex: 1;
		overflow-y: auto;
		padding: 0.5rem;
	}

	.mc-task-item {
		display: flex;
		align-items: center;
		gap: 0.625rem;
		padding: 0.5rem 0.625rem;
		border-radius: var(--r2);
		transition: background 0.15s;
		margin-bottom: 2px;
	}

	.mc-task-current {
		background: rgba(88, 157, 246, 0.1);
		box-shadow: inset 3px 0 0 var(--ac);
	}

	.mc-task-done {
		opacity: 0.5;
	}

	.mc-task-error {
		background: rgba(244, 71, 71, 0.08);
	}

	.mc-task-status-icon {
		flex-shrink: 0;
		display: flex;
		align-items: center;
		color: var(--dm);
	}

	.mc-task-done .mc-task-status-icon {
		color: var(--gn-bright);
	}

	.mc-task-error .mc-task-status-icon {
		color: var(--rd);
	}

	.mc-task-current .mc-task-status-icon {
		color: var(--ac);
	}

	.mc-task-dot {
		width: 8px;
		height: 8px;
		border-radius: 50%;
		background: var(--dm2);
	}

	.mc-task-info {
		min-width: 0;
	}

	.mc-task-name {
		display: block;
		font-size: 0.8125rem;
		color: var(--tx-bright);
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.mc-phase-dots {
		display: flex;
		gap: 4px;
		margin-top: 4px;
	}

	.mc-dot {
		width: 6px;
		height: 6px;
		border-radius: 50%;
		transition: all 0.3s;
	}

	.dot-pending { background: var(--dm2); }
	.dot-active { background: var(--ac); animation: pulse 1.5s infinite; }
	.dot-done { background: var(--gn-bright); }
	.dot-error { background: var(--rd); }

	.mc-empty {
		padding: 2rem 1rem;
		text-align: center;
		color: var(--dm);
		font-size: 0.8125rem;
	}

	/* ── Main content ── */
	.mc-main {
		padding: 1.5rem;
		display: flex;
		flex-direction: column;
		gap: 1.25rem;
		overflow-y: auto;
	}

	/* Progress bar */
	.mc-progress-wrap {
		display: flex;
		align-items: center;
		gap: 0.75rem;
	}

	.mc-progress-track {
		flex: 1;
		height: 6px;
		background: var(--sf);
		border-radius: 3px;
		overflow: hidden;
	}

	.mc-progress-fill {
		height: 100%;
		background: var(--ac);
		border-radius: 3px;
		transition: width 0.6s ease;
		position: relative;
	}

	.mc-progress-fill::after {
		content: '';
		position: absolute;
		top: 0;
		right: 0;
		width: 30px;
		height: 100%;
		background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.3));
		animation: shimmer 1.5s infinite;
	}

	.mc-progress-complete {
		background: var(--gn-bright);
	}

	.mc-progress-complete::after {
		display: none;
	}

	@keyframes shimmer {
		from { transform: translateX(-100%); }
		to { transform: translateX(100%); }
	}

	.mc-progress-label {
		font-family: var(--font-ui);
		font-size: 0.875rem;
		font-weight: 600;
		color: var(--ac);
		min-width: 3rem;
		text-align: right;
	}

	/* Focus card */
	.mc-focus-card {
		background: var(--bg);
		border: 1px solid var(--bd);
		border-radius: 0.75rem;
		padding: 1.5rem;
		animation: slideUp 0.3s ease;
	}

	@keyframes slideUp {
		from { opacity: 0; transform: translateY(8px); }
		to { opacity: 1; transform: translateY(0); }
	}

	.mc-focus-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 1.25rem;
	}

	.mc-focus-header h3 {
		font-size: 1.125rem;
		color: var(--tx-bright);
		margin: 0;
	}

	.mc-focus-phase {
		display: flex;
		align-items: center;
		gap: 0.375rem;
		font-family: var(--font-ui);
		font-size: 0.8125rem;
		color: var(--ac);
		padding: 0.25rem 0.75rem;
		background: rgba(88, 157, 246, 0.1);
		border-radius: 1rem;
	}

	.mc-stage-badge {
		padding: 0.125rem 0.375rem;
		background: rgba(88, 157, 246, 0.2);
		border-radius: 0.25rem;
		font-size: 0.75rem;
	}

	/* Pipeline */
	.mc-pipeline {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 0;
		margin-bottom: 1.25rem;
	}

	.mc-pipe-step {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.375rem;
		opacity: 0.4;
		transition: all 0.3s;
	}

	.mc-pipe-active {
		opacity: 1;
	}

	.mc-pipe-done {
		opacity: 0.7;
	}

	.mc-pipe-icon {
		width: 40px;
		height: 40px;
		display: flex;
		align-items: center;
		justify-content: center;
		border-radius: 50%;
		border: 2px solid var(--dm2);
		color: var(--dm);
		transition: all 0.3s;
	}

	.mc-pipe-active .mc-pipe-icon {
		border-color: var(--ac);
		color: var(--ac);
		box-shadow: 0 0 12px rgba(88, 157, 246, 0.3);
	}

	.mc-pipe-done .mc-pipe-icon {
		border-color: var(--gn-bright);
		color: var(--gn-bright);
		background: rgba(106, 135, 89, 0.1);
	}

	.mc-pipe-label {
		font-size: 0.6875rem;
		font-family: var(--font-ui);
		color: var(--dm);
		text-transform: uppercase;
		letter-spacing: 0.05em;
	}

	.mc-pipe-active .mc-pipe-label {
		color: var(--ac);
	}

	.mc-pipe-done .mc-pipe-label {
		color: var(--gn-bright);
	}

	.mc-pipe-connector {
		width: 40px;
		height: 2px;
		background: var(--dm2);
		margin: 0 4px;
		margin-bottom: 1.25rem;
		transition: background 0.3s;
	}

	.mc-pipe-connector-done {
		background: var(--gn-bright);
	}

	/* Stage cells */
	.mc-stages-progress {
		display: flex;
		gap: 4px;
		justify-content: center;
		flex-wrap: wrap;
		margin-bottom: 1rem;
	}

	.mc-stage-cell {
		width: 32px;
		height: 28px;
		display: flex;
		align-items: center;
		justify-content: center;
		border-radius: var(--r2);
		background: var(--sf);
		font-size: 0.75rem;
		font-family: var(--font-ui);
		color: var(--dm);
		transition: all 0.3s;
	}

	.mc-stage-done {
		background: rgba(106, 135, 89, 0.25);
		color: var(--gn-bright);
	}

	.mc-stage-active {
		background: rgba(88, 157, 246, 0.2);
		color: var(--ac);
		box-shadow: 0 0 8px rgba(88, 157, 246, 0.2);
		animation: pulse 1.5s infinite;
	}

	.mc-focus-spinner {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		justify-content: center;
		color: var(--dm);
		font-size: 0.875rem;
	}

	/* Result cards */
	.mc-result-card {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		text-align: center;
		padding: 3rem 2rem;
		border-radius: 0.75rem;
		background: var(--bg);
		border: 1px solid var(--bd);
		flex: 1;
		animation: slideUp 0.4s ease;
	}

	.mc-result-card h3 {
		font-size: 1.5rem;
		margin: 1rem 0 0.5rem;
		color: var(--tx-bright);
	}

	.mc-result-card p {
		color: var(--dm);
		max-width: 400px;
	}

	.mc-result-success {
		color: var(--gn-bright);
		border-color: rgba(106, 135, 89, 0.3);
	}

	.mc-result-success h3 {
		color: var(--gn-bright);
	}

	.mc-result-error {
		color: var(--rd);
		border-color: rgba(244, 71, 71, 0.3);
	}

	.mc-result-error h3 {
		color: var(--rd);
	}

	.mc-error-task {
		font-family: var(--font-ui);
		font-size: 0.875rem;
		color: var(--tx-bright);
	}

	.mc-error-message {
		background: rgba(244, 71, 71, 0.08);
		padding: 0.75rem 1rem;
		border-radius: var(--r);
		font-family: var(--font-ui);
		font-size: 0.8125rem;
		color: var(--rd);
		max-width: 500px;
		word-break: break-word;
		margin-top: 0.5rem;
	}

	.mc-result-idle {
		color: var(--ac);
	}

	/* ── Log panel ── */
	.mc-log {
		border-left: 1px solid var(--bd);
		display: flex;
		flex-direction: column;
		overflow: hidden;
	}

	.mc-log-header {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.75rem 1rem;
		font-size: 0.6875rem;
		font-family: var(--font-ui);
		text-transform: uppercase;
		letter-spacing: 0.08em;
		color: var(--dm);
		border-bottom: 1px solid var(--bd);
		flex-shrink: 0;
		background: none;
		border-top: none;
		border-left: none;
		border-right: none;
		cursor: pointer;
		width: 100%;
		text-align: left;
	}

	.mc-log-header:hover {
		color: var(--tx-bright);
	}

	.mc-log-count {
		margin-left: auto;
		padding: 0 0.375rem;
		background: var(--sf);
		border-radius: 0.25rem;
		font-size: 0.6875rem;
		min-width: 1.25rem;
		text-align: center;
	}

	.mc-log-body {
		flex: 1;
		overflow-y: auto;
		padding: 0.5rem;
		font-family: var(--font-ui);
		font-size: 0.75rem;
	}

	.mc-log-entry {
		display: flex;
		gap: 0.5rem;
		padding: 0.25rem 0.375rem;
		border-radius: 2px;
		line-height: 1.4;
		align-items: baseline;
	}

	.mc-log-entry:hover {
		background: var(--sf);
	}

	.mc-log-time {
		color: var(--dm2);
		flex-shrink: 0;
		font-size: 0.6875rem;
	}

	.mc-log-tag {
		color: var(--ac);
		flex-shrink: 0;
		max-width: 80px;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.mc-log-msg {
		color: var(--tx);
		word-break: break-word;
	}

	.log-error .mc-log-msg { color: var(--rd); }
	.log-system .mc-log-msg { color: var(--dm); font-style: italic; }
	.log-task .mc-log-tag { color: var(--yl); }

	.mc-log-empty {
		padding: 2rem 1rem;
		text-align: center;
		color: var(--dm2);
	}

	/* ── Thinking block ── */
	.mc-thinking {
		background: var(--bg);
		border: 1px solid var(--bd);
		border-radius: 0.5rem;
		overflow: hidden;
		animation: slideUp 0.2s ease;
	}

	.mc-thinking-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		width: 100%;
		padding: 0.5rem 0.75rem;
		background: none;
		border: none;
		color: var(--dm);
		cursor: pointer;
		font-family: var(--font-ui);
		font-size: 0.75rem;
	}

	.mc-thinking-header:hover {
		color: var(--tx-bright);
	}

	.mc-thinking-title {
		display: flex;
		align-items: center;
		gap: 0.375rem;
		color: var(--ac);
	}

	.mc-thinking-body {
		max-height: 200px;
		overflow-y: auto;
		padding: 0 0.75rem 0.625rem;
		border-top: 1px solid var(--bd);
	}

	.mc-thinking-body pre {
		font-family: var(--font-ui);
		font-size: 0.75rem;
		line-height: 1.6;
		color: #7ec8e3;
		white-space: pre-wrap;
		word-break: break-word;
		margin: 0;
		padding-top: 0.5rem;
		text-shadow: 0 0 8px rgba(88, 157, 246, 0.25);
		background:
			repeating-linear-gradient(
				0deg,
				transparent,
				transparent 1.2em,
				rgba(88, 157, 246, 0.03) 1.2em,
				rgba(88, 157, 246, 0.03) 2.4em
			);
		background-size: 100% 2.4em;
	}

	:global([data-theme="light"]) .mc-thinking-body pre {
		color: #1a6e8e;
		text-shadow: none;
		background:
			repeating-linear-gradient(
				0deg,
				transparent,
				transparent 1.2em,
				rgba(74, 120, 194, 0.06) 1.2em,
				rgba(74, 120, 194, 0.06) 2.4em
			);
	}

	/* ── Stopped card ── */
	.mc-result-stopped {
		color: var(--yl);
		border-color: rgba(255, 198, 109, 0.2);
	}

	.mc-result-stopped h3 {
		color: var(--yl);
	}

	/* ── Responsive ── */
	@media (max-width: 1200px) {
		.mc-body {
			grid-template-columns: 200px 1fr 240px;
		}
	}

	@media (max-width: 900px) {
		.mc-body {
			grid-template-columns: 1fr;
			grid-template-rows: auto 1fr auto;
		}
		.mc-sidebar, .mc-log {
			border: none;
			border-bottom: 1px solid var(--bd);
			max-height: 200px;
		}
	}
</style>
