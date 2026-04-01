<script>
	import { t } from '$lib/i18n/index.js';
	import {
		Heading1, Heading2, Heading3,
		Bold, Italic, Code,
		Minus, List, ListOrdered,
		Quote, SquareCheck, Link,
		Save, X,
	} from 'lucide-svelte';

	/** @type {{ onAction: (action: string) => void, onSave: () => void, onClose: () => void, saving?: boolean, splitRatio?: number }} */
	let { onAction, onSave, onClose, saving = false, splitRatio = 0.5 } = $props();

	const groups = [
		[
			{ action: 'h1', icon: Heading1, tip: 'editor.tip_h1' },
			{ action: 'h2', icon: Heading2, tip: 'editor.tip_h2' },
			{ action: 'h3', icon: Heading3, tip: 'editor.tip_h3' },
		],
		[
			{ action: 'bold', icon: Bold, tip: 'editor.tip_bold' },
			{ action: 'italic', icon: Italic, tip: 'editor.tip_italic' },
			{ action: 'code', icon: Code, tip: 'editor.tip_code' },
		],
		[
			{ action: 'hr', icon: Minus, tip: 'editor.tip_hr' },
			{ action: 'ul', icon: List, tip: 'editor.tip_ul' },
			{ action: 'ol', icon: ListOrdered, tip: 'editor.tip_ol' },
			{ action: 'quote', icon: Quote, tip: 'editor.tip_quote' },
		],
		[
			{ action: 'checkbox', icon: SquareCheck, tip: 'editor.tip_checkbox' },
			{ action: 'link', icon: Link, tip: 'editor.tip_link' },
			{ action: 'codeblock', label: '```', tip: 'editor.tip_codeblock' },
		],
	];
</script>

<div class="toolbar">
	<!-- Spacer matching preview pane width -->
	<div class="toolbar-spacer" style="flex-basis: {splitRatio * 100}%;"></div>
	<!-- Gap matching divider width -->
	<div class="toolbar-gap"></div>

	<div class="toolbar-content">
		<div class="toolbar-groups">
			{#each groups as group, gi}
				{#if gi > 0}<span class="sep"></span>{/if}
				{#each group as btn}
					<button
						type="button"
						class="tb-btn"
						title={$t(btn.tip)}
						onclick={() => onAction(btn.action)}
					>
						{#if btn.icon}
							{@const Icon = btn.icon}
							<Icon size={15} strokeWidth={2} />
						{:else}
							<span class="tb-label">{btn.label}</span>
						{/if}
					</button>
				{/each}
			{/each}
		</div>

		<div class="toolbar-actions">
			<button type="button" class="btn btn-primary btn-sm" onclick={onSave} disabled={saving}>
				<Save size={14} />
				{$t('editor.save')}
			</button>
			<button type="button" class="btn btn-sm" onclick={onClose}>
				<X size={14} />
				{$t('editor.cancel')}
			</button>
		</div>
	</div>
</div>

<style>
	.toolbar {
		display: flex;
		align-items: center;
		padding: 0.375rem 0;
		background: var(--sf);
		border-bottom: 0.0625rem solid var(--bd);
		flex-shrink: 0;
		overflow: hidden;
	}

	.toolbar-spacer {
		flex-shrink: 0;
	}

	.toolbar-gap {
		width: 0.1875rem;
		flex-shrink: 0;
	}

	.toolbar-content {
		flex: 1;
		min-width: 0;
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.5rem;
		padding: 0 0.75rem;
	}

	.toolbar-groups {
		display: flex;
		align-items: center;
		gap: 0.125rem;
		flex-wrap: wrap;
	}

	.sep {
		width: 0.0625rem;
		height: 1.25rem;
		background: var(--bd2);
		margin: 0 0.25rem;
		flex-shrink: 0;
	}

	.tb-btn {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 1.875rem;
		height: 1.75rem;
		border: none;
		border-radius: var(--r2);
		background: transparent;
		color: var(--tx);
		cursor: pointer;
		font-family: var(--font-ui);
		font-size: 0.75rem;
		transition: background 0.1s, color 0.1s;
	}

	.tb-btn:hover {
		background: var(--sf2);
		color: var(--tx-bright);
	}

	.tb-btn:active {
		background: var(--bg-high);
	}

	.tb-label {
		font-weight: 600;
		font-size: 0.6875rem;
	}

	.toolbar-actions {
		display: flex;
		align-items: center;
		gap: 0.375rem;
		flex-shrink: 0;
	}
</style>
