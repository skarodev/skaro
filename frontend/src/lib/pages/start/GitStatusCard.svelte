<script>
	import { onMount } from 'svelte';
	import { t } from '$lib/i18n/index.js';
	import { api } from '$lib/api/client.js';
	import { GitBranch, FileUp, FileWarning, FilePlus, FileMinus, FileQuestion, ArrowRight } from 'lucide-svelte';

	let gitData = $state(null);
	let error = $state(false);

	onMount(async () => {
		try {
			gitData = await api.getGitStatus();
		} catch {
			error = true;
		}
	});

	let stagedCount = $derived(gitData?.files?.filter(f => f.status === 'staged').length || 0);
	let unstagedCount = $derived(gitData?.files?.filter(f => f.status !== 'staged').length || 0);
	let totalChanged = $derived(stagedCount + unstagedCount);
</script>

<div class="card git-card">
	<div class="section-head">
		<h3><GitBranch size={16} /> Git</h3>
		<a class="sec-btn" href="/git">{$t('start.open_git')} <ArrowRight size={11} /></a>
	</div>

	{#if error}
		<p class="empty-hint">{$t('start.git_unavailable')}</p>
	{:else if gitData}
		<div class="git-info">
			<div class="git-row">
				<span class="git-label">{$t('start.git_branch')}</span>
				<span class="git-val mono">{gitData.branch || '—'}</span>
			</div>
			<div class="git-row">
				<span class="git-label">{$t('start.git_staged')}</span>
				<span class="git-val mono" class:has-val={stagedCount > 0}>
					<FileUp size={13} /> {stagedCount}
				</span>
			</div>
			<div class="git-row">
				<span class="git-label">{$t('start.git_changed')}</span>
				<span class="git-val mono" class:has-warn={unstagedCount > 0}>
					<FileWarning size={13} /> {unstagedCount}
				</span>
			</div>
		</div>
	{:else}
		<p class="empty-hint">{$t('app.loading')}</p>
	{/if}
</div>

<style>
	.git-card {
		grid-column: span 4;
	}

	.git-info {
		display: flex;
		flex-direction: column;
		gap: 0.375rem;
	}

	.git-row {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 0.3125rem 0;
	}

	.git-label {
		font-size: 0.75rem;
		color: var(--tx-dim);
		text-transform: uppercase;
		letter-spacing: 0.025em;
	}

	.git-val {
		font-size: 0.8125rem;
		color: var(--tx-bright);
		display: flex;
		align-items: center;
		gap: 0.25rem;
	}

	.git-val.has-val {
		color: var(--ok);
	}

	.git-val.has-warn {
		color: var(--warn);
	}

	.mono {
		font-family: var(--font-ui);
	}
</style>
