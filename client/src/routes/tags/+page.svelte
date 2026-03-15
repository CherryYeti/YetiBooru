<script lang="ts">
	import { page } from '$app/state';
	import { resolve } from '$app/paths';
	import type { TagInterface, CategoryInterface } from '$lib/types/tag';
	import { authClient } from '$lib/auth-client';

	let value = $state('');
	let tags: TagInterface[] | undefined = $state();
	let categories: CategoryInterface[] = $state([]);
	let implications: Record<number, TagInterface[]> = $state({});
	let isLoading = $state(true);
	let error: string | undefined = $state();

	let filteredTags = $derived.by(() => {
		if (!tags) return [];
		const query = value.trim().toLowerCase();
		if (!query) return tags;
		return tags.filter((tag) => tag.label.toLowerCase().includes(query));
	});

	// Create tag form state
	let showCreateForm = $state(false);
	let newTagLabel = $state('');
	let newTagCategoryId = $state(0);
	let createError: string | undefined = $state();
	let isCreating = $state(false);

	const session = authClient.useSession();

	isLoading = true;
	error = undefined;

	$effect(() => {
		const q = (page.url.searchParams.get('q') ?? '').trim();
		value = q.length > 0 ? q.replace(/\+/g, ' ') : '';

		(async () => {
			try {
				const [tagsRes, catsRes] = await Promise.all([
					fetch(`/api/tags/`),
					fetch(`/api/categories`)
				]);
				if (!tagsRes.ok) throw new Error(`HTTP error! Status: ${tagsRes.status}`);
				if (!catsRes.ok) throw new Error(`HTTP error! Status: ${catsRes.status}`);
				tags = (await tagsRes.json()) as TagInterface[];
				categories = (await catsRes.json()) as CategoryInterface[];
				if (categories.length > 0 && newTagCategoryId === 0) {
					newTagCategoryId = categories.find((c) => c.is_default)?.id ?? categories[0]?.id ?? 0;
				}

				// Fetch implications for each tag
				const implMap: Record<number, TagInterface[]> = {};
				await Promise.all(
					(tags ?? []).map(async (tag) => {
						const res = await fetch(`/api/tag/${tag.label}/implications`);
						if (res.ok) {
							implMap[tag.id] = (await res.json()) as TagInterface[];
						}
					})
				);
				implications = implMap;
			} catch (err) {
				error = err instanceof Error ? err.message : 'An error occurred';
			} finally {
				isLoading = false;
			}
		})();
	});

	async function createTag(e: SubmitEvent) {
		e.preventDefault();
		createError = undefined;

		const label = newTagLabel.trim().toLowerCase();
		if (!label) {
			createError = 'Tag label cannot be empty';
			return;
		}

		isCreating = true;
		try {
			const response = await fetch('/api/tags/', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ label, category_id: newTagCategoryId })
			});

			if (!response.ok) {
				const data = await response.json();
				throw new Error(data.detail || `HTTP error! Status: ${response.status}`);
			}

			const newTag = (await response.json()) as TagInterface;

			if (tags) {
				tags = [newTag, ...tags];
			}
			implications[newTag.id] = [];

			newTagLabel = '';
			showCreateForm = false;
		} catch (err) {
			createError = err instanceof Error ? err.message : 'An error occurred';
		} finally {
			isCreating = false;
		}
	}
</script>

{#if isLoading}
	<p>Loading...</p>
{:else if error}
	<p class="error">Error: {error}</p>
{:else if tags}
	<div class="flex flex-col items-center justify-center gap-8 pt-8">
		<div class="flex w-full max-w-5xl flex-row items-stretch justify-center gap-2">
			<input
				bind:value
				placeholder="Filter tags by name"
				class="h-11 w-full rounded-lg border border-container-text/15 bg-container px-4 py-2 text-lg outline-none"
			/>

			{#if $session?.data}
				<button
					type="button"
					class="h-11 shrink-0 rounded-lg border border-container-text/15 bg-container px-4 py-2 whitespace-nowrap text-container-text transition-colors hover:cursor-pointer hover:bg-container-alt"
					onclick={() => (showCreateForm = !showCreateForm)}
				>
					{showCreateForm ? 'Cancel' : 'Create Tag'}
				</button>
			{/if}
		</div>

		{#if showCreateForm}
			<form
				onsubmit={createTag}
				class="flex w-full max-w-xl flex-col gap-4 rounded-xl border border-container-text/15 bg-container p-6"
			>
				<h3 class="text-xl font-semibold">Create New Tag</h3>

				{#if createError}
					<p class="rounded-lg bg-red-500/20 px-4 py-2 text-red-400">{createError}</p>
				{/if}

				<div class="flex flex-col gap-1">
					<label for="new-tag-label" class="text-sm text-container-text">Tag Name</label>
					<input
						id="new-tag-label"
						bind:value={newTagLabel}
						class="rounded-lg border border-container-text/15 bg-container-alt px-4 py-2 text-lg outline-none"
						placeholder="e.g. landscape"
					/>
				</div>

				<div class="flex flex-col gap-1">
					<label for="new-tag-category" class="text-sm text-container-text">Category</label>
					<select
						id="new-tag-category"
						bind:value={newTagCategoryId}
						class="rounded-lg border border-container-text/15 bg-container-alt px-4 py-2 text-lg text-white outline-none"
					>
						{#each categories as category, i (category.label)}
							<option value={category.id ?? i + 1} style="color:{category.color}">
								{category.label}
							</option>
						{/each}
					</select>
				</div>

				<button
					type="submit"
					disabled={isCreating}
					class="rounded-lg bg-violet-500 px-4 py-2 text-white hover:cursor-pointer hover:bg-violet-400 disabled:cursor-not-allowed disabled:opacity-50"
				>
					{isCreating ? 'Creating...' : 'Create'}
				</button>
			</form>
		{/if}

		{#if filteredTags.length === 0}
			<p class="text-container-text/50">No tags found.</p>
		{:else}
			<div class="w-full max-w-5xl overflow-hidden rounded-xl border border-container-text/15">
				<table class="w-full">
					<thead>
						<tr class="bg-container text-container-text">
							<th class="border-b border-container-text/15 px-4 py-2 text-left">Name</th>
							<th class="border-b border-container-text/15 px-4 py-2 text-left">Count</th>
							<th class="border-b border-container-text/15 px-4 py-2 text-left">Category</th>
							<th class="border-b border-container-text/15 px-4 py-2 text-left">Implications</th>
						</tr>
					</thead>
					<tbody>
						{#each filteredTags as tag (tag.id)}
							<tr class="bg-container text-container-text transition-colors hover:bg-container-alt">
								<td
									class="border-b border-container-text/15 px-4 py-2"
									style="color: {tag.category.color};"
								>
									<a
										href={resolve(`/tag/${tag.label}`)}
										class="hover:cursor-pointer hover:underline"
									>
										{tag.label}
									</a>
								</td>
								<td class="border-b border-container-text/15 px-4 py-2">{tag.count}</td>
								<td class="border-b border-container-text/15 px-4 py-2">{tag.category.label}</td>
								<td class="border-b border-container-text/15 px-4 py-2">
									{#if implications[tag.id]?.length}
										{#each implications[tag.id] as impl, i (impl.id)}
											<a
												href={resolve(`/tag/${impl.label}`)}
												class="hover:underline"
												style="color:{impl.category.color}">{impl.label}</a
											>{#if i < implications[tag.id].length - 1},&nbsp;{/if}
										{/each}
									{:else}
										<span class="text-container-text/30">—</span>
									{/if}
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}
	</div>
{/if}
