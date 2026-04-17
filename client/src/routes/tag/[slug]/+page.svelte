<script lang="ts">
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import { X } from 'lucide-svelte';
	import { authClient } from '$lib/auth-client';
	import type { CategoryInterface, TagInterface } from '$lib/types/tag';
	import { canAdmin, canModerate } from '$lib/roles';
	import TagInput from '$lib/components/TagInput.svelte';

	const slug = $derived(page.params.slug ?? '');
	let tag: TagInterface | undefined = $state();
	let categories: CategoryInterface[] | undefined = $state();
	let implications: TagInterface[] = $state([]);
	let isLoading = $state(true);
	let error: string | undefined = $state();

	let newImplicationLabel = $state('');
	let implicationError: string | undefined = $state();
	let isSavingImplications = $state(false);
	let implicationSuccess: string | undefined = $state();
	let allTags: TagInterface[] = $state([]);

	let availableTags = $derived(
		allTags.filter((t) => t.label !== slug && !implications.some((impl) => impl.label === t.label))
	);

	let selectedCategoryLabel = $state('');
	let isSavingTag = $state(false);
	let tagSaveError: string | undefined = $state();
	let tagSaveSuccess: string | undefined = $state();

	let showDeleteConfirm = $state(false);
	let isDeleting = $state(false);
	let deleteError: string | undefined = $state();

	const session = authClient.useSession();
	const role = $derived($session?.data?.user?.role ?? 'user');
	const canManageTag = $derived(canModerate(role));
	const canDeleteTag = $derived(canAdmin(role));

	$effect(() => {
		if (!slug) return;
		isLoading = true;
		error = undefined;
		(async () => {
			try {
				const [catRes, tagRes, implRes, tagsRes] = await Promise.all([
					fetch(`/api/categories`),
					fetch(`/api/tag/${slug}`),
					fetch(`/api/tag/${slug}/implications`),
					fetch(`/api/tags/`)
				]);
				if (!catRes.ok) throw new Error(`HTTP error! Status: ${catRes.status}`);
				if (!tagRes.ok) throw new Error(`HTTP error! Status: ${tagRes.status}`);
				if (!implRes.ok) throw new Error(`HTTP error! Status: ${implRes.status}`);
				if (!tagsRes.ok) throw new Error(`HTTP error! Status: ${tagsRes.status}`);

				categories = (await catRes.json()) as CategoryInterface[];
				tag = (await tagRes.json()) as TagInterface;
				selectedCategoryLabel = tag.category.label;
				implications = (await implRes.json()) as TagInterface[];
				allTags = (await tagsRes.json()) as TagInterface[];
			} catch (err) {
				error = err instanceof Error ? err.message : 'An error occurred';
			} finally {
				isLoading = false;
			}
		})();
	});

	function addImplication() {
		implicationError = undefined;
		const label = newImplicationLabel.trim().toLowerCase();
		if (!label) {
			implicationError = 'Tag name cannot be empty';
			return;
		}
		if (label === slug) {
			implicationError = 'A tag cannot imply itself';
			return;
		}
		if (implications.some((t) => t.label === label)) {
			implicationError = `"${label}" is already implied`;
			return;
		}
		const found = allTags.find((t) => t.label === label);
		if (!found) {
			implicationError = `Tag "${label}" does not exist`;
			return;
		}
		implications = [...implications, found];
		newImplicationLabel = '';
	}

	function onSelectImplication(tag: TagInterface) {
		implicationError = undefined;
		if (tag.label === slug) {
			implicationError = 'A tag cannot imply itself';
			return;
		}
		if (implications.some((t) => t.label === tag.label)) {
			implicationError = `"${tag.label}" is already implied`;
			return;
		}
		implications = [...implications, tag];
		newImplicationLabel = '';
	}

	function removeImplication(label: string) {
		implications = implications.filter((t) => t.label !== label);
	}

	async function saveImplications() {
		if (!canManageTag) return;
		implicationError = undefined;
		implicationSuccess = undefined;
		isSavingImplications = true;
		try {
			const response = await fetch(`/api/tag/${slug}/implications`, {
				method: 'PUT',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					implied_tag_labels: implications.map((t) => t.label)
				})
			});

			if (!response.ok) {
				const data = await response.json();
				throw new Error(data.detail || `HTTP error! Status: ${response.status}`);
			}

			implications = (await response.json()) as TagInterface[];
			implicationSuccess = 'Implications saved successfully';
			setTimeout(() => (implicationSuccess = undefined), 3000);
		} catch (err) {
			implicationError = err instanceof Error ? err.message : 'An error occurred';
		} finally {
			isSavingImplications = false;
		}
	}

	async function submit(e: SubmitEvent) {
		e.preventDefault();
		if (!canManageTag) return;

		if (!tag) return;

		tagSaveError = undefined;
		tagSaveSuccess = undefined;
		isSavingTag = true;

		try {
			const response = await fetch(`/api/tag/${slug}`, {
				method: 'PUT',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ category_label: selectedCategoryLabel })
			});

			if (!response.ok) {
				const data = await response.json();
				throw new Error(data.detail || `HTTP error! Status: ${response.status}`);
			}

			tag = (await response.json()) as TagInterface;
			selectedCategoryLabel = tag.category.label;
			tagSaveSuccess = 'Tag updated successfully';
			setTimeout(() => (tagSaveSuccess = undefined), 3000);
		} catch (err) {
			tagSaveError = err instanceof Error ? err.message : 'An error occurred';
		} finally {
			isSavingTag = false;
		}
	}

	async function deleteTag() {
		if (!canDeleteTag) return;
		deleteError = undefined;
		isDeleting = true;

		try {
			const response = await fetch(`/api/tag/${slug}`, {
				method: 'DELETE'
			});

			if (!response.ok) {
				const data = await response.json();
				throw new Error(data.detail || `HTTP error! Status: ${response.status}`);
			}

			goto('/tags');
		} catch (err) {
			deleteError = err instanceof Error ? err.message : 'An error occurred';
		} finally {
			isDeleting = false;
		}
	}
</script>

{#if isLoading}
	<p>Loading...</p>
{:else if error}
	<p class="error">Error: {error}</p>
{:else if tag}
	<div class="flex flex-col items-center justify-center gap-8 pt-8">
		<div class="w-full max-w-5xl rounded-xl border border-text/15 bg-surface0 p-6">
			<p class="mb-4 text-5xl" style="color:{tag.category.color}">{slug}</p>

			{#if tagSaveError}
				<p class="mb-4 rounded-lg bg-red/20 px-4 py-2 text-red">{tagSaveError}</p>
			{/if}
			{#if tagSaveSuccess}
				<p class="mb-4 rounded-lg bg-green/20 px-4 py-2 text-green">{tagSaveSuccess}</p>
			{/if}

			<form onsubmit={submit} class="flex w-full flex-col gap-4">
				<div class="flex flex-col gap-1">
					<label for="categories" class="text-sm text-text">Category</label>
					<select
						name="categories"
						id="categories"
						bind:value={selectedCategoryLabel}
						disabled={!canManageTag}
						class="rounded-lg border border-text/15 bg-surface1 px-4 py-2 text-lg text-text outline-none"
					>
						{#each categories as category (category.label)}
							<option value={category.label} style="color:{category.color}">{category.label}</option
							>
						{/each}
					</select>
				</div>

				<button
					type="submit"
					disabled={isSavingTag || !canManageTag}
					class="rounded-full bg-linear-to-r from-pink to-mauve px-4 py-2 font-semibold text-crust hover:cursor-pointer hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
				>
					{isSavingTag ? 'Saving...' : 'Save'}
				</button>
			</form>
		</div>

		<div class="w-full max-w-5xl rounded-xl border border-text/15 bg-surface0 p-6">
			<h3 class="mb-4 text-2xl font-semibold">Implications</h3>
			<p class="mb-4 text-sm text-text">
				When "{slug}" is added to a post, these tags will also be applied automatically.
			</p>

			{#if implicationError}
				<p class="mb-4 rounded-lg bg-red/20 px-4 py-2 text-red">{implicationError}</p>
			{/if}

			{#if implicationSuccess}
				<p class="mb-4 rounded-lg bg-green/20 px-4 py-2 text-green">
					{implicationSuccess}
				</p>
			{/if}

			{#if implications.length > 0}
				<div class="mb-4 flex flex-wrap gap-2">
					{#each implications as impl (impl.id)}
						<span
							class="inline-flex items-center gap-1 rounded-lg border border-text/15 bg-surface1 px-3 py-1.5"
							style="color:{impl.category.color}"
						>
							{impl.label}
							<button
								type="button"
								class="ml-1 opacity-60 transition-opacity hover:cursor-pointer hover:opacity-100"
								onclick={() => removeImplication(impl.label)}
							>
								<X size={14} />
							</button>
						</span>
					{/each}
				</div>
			{:else}
				<p class="mb-4 text-sm text-text/50 italic">No implications set.</p>
			{/if}

			<div class="flex flex-col gap-2">
				<div class="flex flex-row gap-2">
					<TagInput
						bind:value={newImplicationLabel}
						placeholder="Type a tag name..."
						allTags={availableTags}
						multiTag={false}
						onselect={onSelectImplication}
						onsubmit={() => addImplication()}
					/>

					<button
						type="button"
						disabled={!canManageTag}
						class="rounded-lg border border-text/15 bg-surface0 px-4 py-2 text-text transition-colors hover:cursor-pointer hover:bg-surface1"
						onclick={addImplication}
					>
						Add
					</button>
				</div>

				<button
					type="button"
					disabled={isSavingImplications || !canManageTag}
					class="rounded-full bg-linear-to-r from-pink to-mauve px-4 py-2 font-semibold text-crust hover:cursor-pointer hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
					onclick={saveImplications}
				>
					{isSavingImplications ? 'Saving...' : 'Save Implications'}
				</button>
			</div>
		</div>

		{#if canDeleteTag}
			<div class="w-full max-w-5xl rounded-xl border border-red-500/30 bg-surface0 p-6">
				<h3 class="mb-2 text-2xl font-semibold text-red">Danger Zone</h3>
				<p class="mb-4 text-sm text-text">
					Deleting a tag is permanent. The tag must be removed from all posts before it can be
					deleted.
				</p>

				{#if deleteError}
					<p class="mb-4 rounded-lg bg-red/20 px-4 py-2 text-red">{deleteError}</p>
				{/if}

				{#if showDeleteConfirm}
					<div class="flex flex-col gap-3 rounded-lg bg-red/10 p-4">
						<p class="text-sm text-red">
							Are you sure you want to delete <strong style="color:{tag.category.color}"
								>{slug}</strong
							>? This action cannot be undone.
						</p>
						<div class="flex gap-2">
							<button
								type="button"
								disabled={isDeleting}
								class="rounded-lg bg-red px-4 py-2 text-text hover:cursor-pointer hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
								onclick={deleteTag}
							>
								{isDeleting ? 'Deleting...' : 'Yes, Delete Tag'}
							</button>
							<button
								type="button"
								class="rounded-lg border border-text/15 bg-surface0 px-4 py-2 text-text transition-colors hover:cursor-pointer hover:bg-surface1"
								onclick={() => {
									showDeleteConfirm = false;
									deleteError = undefined;
								}}
							>
								Cancel
							</button>
						</div>
					</div>
				{:else}
					<button
						type="button"
						class="rounded-lg border border-red-500/50 bg-red/10 px-4 py-2 text-red transition-colors hover:cursor-pointer hover:bg-red/20"
						onclick={() => (showDeleteConfirm = true)}
					>
						Delete Tag
					</button>
				{/if}
			</div>
		{/if}
	</div>
{/if}
