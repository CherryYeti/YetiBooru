<script lang="ts">
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { onMount } from 'svelte';
	import { loadBootstrapStatus } from '$lib/utils/admin-access';
	import { formatDateTime } from '$lib/utils/date';

	type ReportStatus = 'open' | 'resolved' | 'dismissed' | 'deleted';
	type ReportAction = 'resolved' | 'dismissed' | 'deleted';
	type ReportInfo = {
		id: number;
		post_id: number | null;
		reporter_user_id: string;
		reporter_name: string | null;
		reason: string;
		status: ReportStatus;
		resolution_note: string | null;
		created_at: string;
		resolved_at: string | null;
		resolved_by_user_id: string | null;
		resolved_by_name: string | null;
	};
	let reports = $state<ReportInfo[]>([]);
	let loading = $state(true);
	let error = $state('');
	let message = $state('');
	let selectedStatus = $state<'open' | 'all' | 'resolved' | 'dismissed' | 'deleted'>('open');
	let noteDrafts = $state<Record<number, string>>({});
	let busyAction = $state<{ id: number; action: ReportAction } | null>(null);

	function isBusy(id: number, action: ReportAction): boolean {
		return busyAction?.id === id && busyAction?.action === action;
	}

	async function loadReports() {
		loading = true;
		error = '';
		message = '';

		try {
			const bootstrap = await loadBootstrapStatus('Unable to verify access.');
			if (bootstrap.kind === 'unauthorized') {
				goto(resolve('/login'));
				return;
			}
			if (bootstrap.kind === 'error') {
				error = bootstrap.message;
				return;
			}

			const status = bootstrap.status;
			if (status.currentUser.role === 'user') {
				error = 'You do not have permission to view moderation reports.';
				return;
			}

			const query = selectedStatus === 'open' ? '' : `?status=${selectedStatus}`;
			const response = await fetch(`/api/moderation/reports${query}`);
			if (!response.ok) {
				if (response.status === 403) {
					error = 'You do not have permission to view moderation reports.';
					return;
				}
				throw new Error('Unable to load moderation reports.');
			}

			reports = (await response.json()) as ReportInfo[];
			noteDrafts = Object.fromEntries(
				reports.map((report) => [report.id, report.resolution_note ?? ''])
			);
		} catch (loadErr) {
			error = loadErr instanceof Error ? loadErr.message : 'Unable to load moderation reports.';
		} finally {
			loading = false;
		}
	}

	async function resolveReport(reportId: number, action: ReportAction) {
		busyAction = { id: reportId, action };
		error = '';
		message = '';

		try {
			const response = await fetch(`/api/moderation/reports/${reportId}`, {
				method: 'PUT',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					action,
					note: (noteDrafts[reportId] ?? '').trim() || null
				})
			});

			if (!response.ok) {
				const payload = await response.json().catch(() => null);
				throw new Error(payload?.detail ?? 'Unable to apply moderation action.');
			}

			message =
				action === 'deleted'
					? 'Post deleted and report closed.'
					: action === 'dismissed'
						? 'Report dismissed.'
						: 'Report resolved.';
			await loadReports();
		} catch (actionError) {
			error =
				actionError instanceof Error ? actionError.message : 'Unable to apply moderation action.';
		} finally {
			busyAction = null;
		}
	}

	onMount(() => {
		void loadReports();
	});
</script>

<svelte:head>
	<title>Moderation Queue</title>
</svelte:head>

<div class="flex flex-col items-center justify-center gap-8 px-4 pt-8">
	<div class="w-full max-w-5xl rounded-xl bg-mantle p-6">
		<div class="mb-6 flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
			<div>
				<h1 class="text-3xl font-semibold text-text">Moderation queue</h1>
				<p class="mt-1 text-sm text-subtext1">
					Review reported posts and resolve, dismiss, or remove content.
				</p>
			</div>
			<div class="flex items-center gap-2">
				<label class="text-sm text-subtext1" for="report-status">Status</label>
				<select
					id="report-status"
					bind:value={selectedStatus}
					onchange={() => void loadReports()}
					class="rounded-lg bg-crust px-3 py-2 text-text outline-none focus:ring-2 focus:ring-mauve focus:outline-none"
				>
					<option value="open">Open</option>
					<option value="resolved">Resolved</option>
					<option value="dismissed">Dismissed</option>
					<option value="deleted">Deleted</option>
					<option value="all">All</option>
				</select>
			</div>
		</div>

		{#if error}
			<div class="mb-4 rounded-lg bg-red/20 px-4 py-3 text-sm text-red">{error}</div>
		{/if}
		{#if message}
			<div class="mb-4 rounded-lg bg-green/20 px-4 py-3 text-sm text-green">{message}</div>
		{/if}

		{#if loading}
			<div class="rounded-lg bg-crust px-4 py-6 text-sm text-subtext1">Loading reports...</div>
		{:else if reports.length === 0}
			<div class="rounded-lg bg-crust px-4 py-6 text-sm text-subtext1">No reports found.</div>
		{:else}
			<div class="flex flex-col gap-4">
				{#each reports as report (report.id)}
					<div class="rounded-lg bg-crust p-4">
						<div class="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
							<div class="space-y-1 text-sm text-subtext1">
								<p class="font-semibold text-text">Report #{report.id}</p>
								{#if report.post_id !== null}
									<p>
										Post:
										<a href={resolve(`/post/${report.post_id}`)} class="text-blue hover:underline">
											#{report.post_id}
										</a>
									</p>
								{:else}
									<p>Post: Deleted</p>
								{/if}
								<p>Reporter: {report.reporter_name ?? report.reporter_user_id}</p>
								<p>Created: {formatDateTime(report.created_at)}</p>
								<p>Status: <span class="font-medium text-text">{report.status}</span></p>
								<p class="whitespace-pre-wrap text-text">{report.reason}</p>
								{#if report.status !== 'open'}
									<p>Resolved by: {report.resolved_by_name ?? report.resolved_by_user_id ?? '-'}</p>
									<p>Resolved at: {formatDateTime(report.resolved_at)}</p>
									{#if report.resolution_note}
										<p class="whitespace-pre-wrap">Note: {report.resolution_note}</p>
									{/if}
								{/if}
							</div>

							{#if report.status === 'open'}
								<div class="w-full max-w-sm space-y-2">
									<textarea
										bind:value={noteDrafts[report.id]}
										rows="3"
										placeholder="Optional moderation note"
										class="w-full rounded-lg bg-surface0 px-3 py-2 text-text outline-none placeholder:text-overlay1 focus:ring-2 focus:ring-mauve focus:outline-none"
									></textarea>
									<div class="flex flex-wrap gap-2">
										<button
											type="button"
											onclick={() => void resolveReport(report.id, 'resolved')}
											disabled={isBusy(report.id, 'resolved')}
											class="rounded-full bg-linear-to-r from-green to-teal px-3 py-2 text-sm font-semibold text-crust transition hover:cursor-pointer hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
										>
											{isBusy(report.id, 'resolved') ? 'Applying...' : 'Resolve'}
										</button>
										<button
											type="button"
											onclick={() => void resolveReport(report.id, 'dismissed')}
											disabled={isBusy(report.id, 'dismissed')}
											class="rounded-full bg-surface0 px-3 py-2 text-sm text-text transition hover:cursor-pointer hover:bg-surface1 disabled:cursor-not-allowed disabled:opacity-50"
										>
											{isBusy(report.id, 'dismissed') ? 'Applying...' : 'Dismiss'}
										</button>
										<button
											type="button"
											onclick={() => void resolveReport(report.id, 'deleted')}
											disabled={isBusy(report.id, 'deleted')}
											class="rounded-full bg-linear-to-r from-red to-maroon px-3 py-2 text-sm font-semibold text-crust transition hover:cursor-pointer hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
										>
											{isBusy(report.id, 'deleted') ? 'Deleting...' : 'Delete Post'}
										</button>
									</div>
								</div>
							{/if}
						</div>
					</div>
				{/each}
			</div>
		{/if}
	</div>
</div>
