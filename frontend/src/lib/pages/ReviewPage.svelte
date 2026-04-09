<script>
	import { onMount } from 'svelte';
	import { t } from '$lib/i18n/index.js';
	import { api } from '$lib/api/client.js';
	import { status } from '$lib/stores/statusStore.js';
	import { addLog, addError } from '$lib/stores/logStore.js';
	import { invalidate } from '$lib/api/cache.js';
	import ProjectTestsPanel from './review/ProjectTestsPanel.svelte';

	let architectureReady = $derived(!!$status?.architecture_reviewed);

	let testsResults = $state(null);
	let testsLoading = $state(false);

	onMount(() => { loadResults(); });

	async function loadResults() {
		try {
			const data = await api.getReviewResults();
			if (data.results) testsResults = data.results;
		} catch { /* no previous results */ }
	}

	async function runTests() {
		testsLoading = true;
		addLog($t('review.running_tests'));
		try {
			const result = await api.runReviewTests();
			if (result.success) {
				testsResults = result.data;
				addLog($t('review.tests_done'));
				invalidate('status');
				status.set(await api.getStatus());
			} else {
				addError(result.message || 'Review tests failed', 'reviewTests');
			}
		} catch (e) {
			addError(e.message, 'runReviewTests');
		}
		testsLoading = false;
	}
</script>

<div class="main-header">
	<h2>{$t('review.title')}</h2>
	<p>{$t('review.subtitle')}</p>
</div>

<ProjectTestsPanel
	results={testsResults}
	loading={testsLoading}
	onRunTests={runTests}
	gateDisabled={!architectureReady}
	gateReason={!architectureReady ? $t('gate.need_architecture') : ''}
/>
