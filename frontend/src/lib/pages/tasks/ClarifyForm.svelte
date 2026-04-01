<script>
	import { t } from '$lib/i18n/index.js';
	import { Loader2, Check, Save, RefreshCw } from 'lucide-svelte';

	const LETTERS = 'ABCDEFGHIJ';

	let {
		parsedQA = [],
		clarifyAnswers = $bindable({}),
		actionLoading = '',
		draftSaving = false,
		draftSaved = false,
		onSubmit = () => {},
		onSaveDraft = () => {},
		onReClarify = () => {},
	} = $props();

	/** Track which questions have "custom" selected */
	let customMode = $state({});

	/** Determine if the current answer is one of the options */
	function isOptionSelected(num, optIndex) {
		const ans = (clarifyAnswers[num] || '').trim().toUpperCase();
		const letter = LETTERS[optIndex];
		return ans === letter;
	}

	function selectOption(num, optIndex) {
		customMode[num] = false;
		clarifyAnswers[num] = LETTERS[optIndex];
	}

	function selectCustom(num) {
		customMode[num] = true;
		// Clear if it was a letter
		const ans = (clarifyAnswers[num] || '').trim().toUpperCase();
		if (ans.length === 1 && LETTERS.includes(ans)) {
			clarifyAnswers[num] = '';
		}
	}

	function isCustom(num, options) {
		if (customMode[num]) return true;
		if (!options?.length) return true;
		const ans = (clarifyAnswers[num] || '').trim().toUpperCase();
		// If answer is not a recognized letter, it's custom
		if (!ans) return false;
		if (ans.length === 1 && LETTERS.includes(ans)) {
			const idx = LETTERS.indexOf(ans);
			return idx >= options.length;
		}
		return true;
	}
</script>

<div class="card" style="margin-top: 2rem">
	<h3>{$t('clarify.title')}</h3>
	<p class="subtitle">{$t('clarify.subtitle')}</p>
	<p class="hint">{$t('clarify.persisted_hint')}</p>

	{#each parsedQA as q}
		{@const num = q.num}
		{@const options = q.options || []}
		{@const showCustom = isCustom(num, options)}
		<div class="qa-block">
			<div class="question-label">
				<strong>{$t('clarify.question', { n: num })}</strong>
			</div>
			<div class="question-text">{q.question}</div>
			{#if q.context}
				<div class="question-context">{q.context}</div>
			{/if}

			{#if options.length > 0}
				<div class="options-list">
					{#each options as opt, idx}
						{@const letter = LETTERS[idx]}
						<label class="option-row" class:selected={isOptionSelected(num, idx)}>
							<input
								type="radio"
								name="q{num}"
								checked={isOptionSelected(num, idx)}
								onchange={() => selectOption(num, idx)}
							/>
							<span class="option-letter">{letter})</span>
							<span class="option-text">{opt}</span>
						</label>
					{/each}
					<label class="option-row" class:selected={showCustom}>
						<input
							type="radio"
							name="q{num}"
							checked={showCustom}
							onchange={() => selectCustom(num)}
						/>
						<span class="option-letter">✎</span>
						<span class="option-text">{$t('clarify.custom_answer')}</span>
					</label>
				</div>
			{/if}

			{#if options.length === 0 || showCustom}
				<textarea
					class="qa-input"
					rows="2"
					placeholder={$t('clarify.placeholder', { n: num })}
					bind:value={clarifyAnswers[num]}
				></textarea>
			{/if}
		</div>
	{/each}

	<div class="btn-group">
		<button class="btn btn-success" disabled={actionLoading === 'submit'} onclick={onSubmit}>
			{#if actionLoading === 'submit'}<Loader2 size={14} class="spin" />{/if}
			<Check size={14} /> {$t('clarify.submit')}
		</button>
		<button class="btn" disabled={draftSaving} onclick={onSaveDraft}>
			{#if draftSaving}<Loader2 size={14} class="spin" />{:else}<Save size={14} />{/if}
			{draftSaved ? $t('clarify.draft_saved') : $t('clarify.save_draft')}
		</button>
		<button class="btn" disabled={!!actionLoading} onclick={onReClarify}>
			<RefreshCw size={14} /> {$t('action.re_clarify')}
		</button>
	</div>
</div>

<style>
	.qa-block {
		margin: 1rem 0;
		padding-bottom: 1rem;
		border-bottom: 0.0625rem solid var(--bd);
	}

	.qa-block:last-of-type {
		border-bottom: none;
	}

	.question-label {
		margin-bottom: 0.25rem;
		font-size: 0.8125rem;
	}

	.question-text {
		font-size: 0.875rem;
		color: var(--tx);
		line-height: 1.5;
		margin-bottom: 0.25rem;
	}

	.question-context {
		font-size: 0.75rem;
		color: var(--tx-dim);
		font-style: italic;
		margin-bottom: 0.5rem;
	}

	/* ── Options ── */
	.options-list {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
		margin: 0.5rem 0;
	}

	.option-row {
		display: flex;
		align-items: flex-start;
		gap: 0.5rem;
		padding: 0.375rem 0.625rem;
		border-radius: var(--r);
		cursor: pointer;
		transition: background 0.1s;
		font-size: 0.875rem;
	}

	.option-row:hover {
		background: var(--sf);
	}

	.option-row.selected {
		background: color-mix(in srgb, var(--ac) 10%, transparent);
	}

	.option-row input[type="radio"] {
		margin-top: 0.1875rem;
		accent-color: var(--ac);
		flex-shrink: 0;
	}

	.option-letter {
		font-weight: 600;
		color: var(--ac);
		flex-shrink: 0;
		min-width: 1.125rem;
	}

	.option-text {
		color: var(--tx);
		line-height: 1.4;
	}

	/* ── Custom textarea ── */
	.qa-input {
		width: 100%;
		padding: 0.375rem 0.625rem;
		background: var(--bg-deep);
		border: 0.0625rem solid var(--bd);
		border-radius: var(--r);
		color: var(--tx);
		font-size: 0.875rem;
		font-family: inherit;
		resize: vertical;
		min-height: 2.5rem;
		margin-top: 0.375rem;
	}

	.qa-input:focus {
		outline: none;
		border-color: var(--ac);
		box-shadow: 0 0 0 0.0625rem var(--ac);
	}
</style>
