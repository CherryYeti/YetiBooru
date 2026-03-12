<script lang="ts">
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import { ChevronLeft, ChevronRight, Download, Tag, X } from 'lucide-svelte';
	import type { PostInterface } from '$lib/types/post';
	import { resolve } from '$app/paths';
	import { searchQuery } from '$lib/components/stores';
	import TagInput from '$lib/components/TagInput.svelte';
	import type { TagInterface } from '$lib/types/tag';

	let post: PostInterface | undefined = $state();
	let allTags: TagInterface[] = $state([]);

	let isLoading = $state(true);
	let error: string | undefined = $state();
	let notFound = $state(false);

	let isEditingTags = $state(false);
	let newTagInput = $state('');
	let editedTags: TagInterface[] = $state([]);
	let isSavingTags = $state(false);
	let tagEditError: string | undefined = $state();
	let tagEditSuccess: string | undefined = $state();
	let isDeleting = $state(false);

	let nextPostId: number | null = $state(null);
	let prevPostId: number | null = $state(null);

	const slug = $derived(page.params.slug ?? '');
	const slugNum = $derived(Number(slug));

	let value = $derived($searchQuery ?? '');

	let availableTagsForAdd = $derived(
		allTags.filter((t) => !editedTags.some((et) => et.id === t.id))
	);

	function doSearch() {
		const result = value.trim().replace(/\s+/g, ' ');
		searchQuery.set(result);
		goto(`/posts/?query=${encodeURIComponent(result)}`);
	}

	function submit(e: SubmitEvent) {
		e.preventDefault();
		doSearch();
	}

	$effect(() => {
		if (!slug) return;

		isLoading = true;
		error = undefined;
		nextPostId = null;
		prevPostId = null;

		(async () => {
			try {
				const [postRes, tagsRes] = await Promise.all([
					fetch(`/api/post/${slug}`),
					fetch('/api/tags/')
				]);
				if (postRes.status === 404) {
					notFound = true;
					return;
				}
				if (!postRes.ok) throw new Error(`HTTP error! Status: ${postRes.status}`);
				post = (await postRes.json()) as PostInterface;
				if (tagsRes.ok) {
					allTags = (await tagsRes.json()) as TagInterface[];
				}

				const [nextRes, prevRes] = await Promise.all([
					fetch(`/api/post/${slug}/next`),
					fetch(`/api/post/${slug}/prev`)
				]);
				if (nextRes.ok) {
					nextPostId = (await nextRes.json()).id;
				}
				if (prevRes.ok) {
					prevPostId = (await prevRes.json()).id;
				}
			} catch (err) {
				error = err instanceof Error ? err.message : 'An error occurred';
			} finally {
				isLoading = false;
			}
		})();
	});

	const categoryOrder = ['meta', 'copyright', 'character', 'creator', 'general'];

	function getGroupedTags(tagList: TagInterface[]) {
		const grouped = tagList.reduce(
			(acc, t) => {
				const key = t.category.label;
				const entry = acc.find((e) => e.label === key);
				if (entry) {
					entry.tags.push(t);
				} else {
					acc.push({ label: key, color: t.category.color, tags: [t] });
				}
				return acc;
			},
			[] as Array<{ label: string; color: string; tags: TagInterface[] }>
		);

		return grouped.sort((a, b) => categoryOrder.indexOf(a.label) - categoryOrder.indexOf(b.label));
	}

	function startEditTags() {
		tagEditError = undefined;
		tagEditSuccess = undefined;
		editedTags = [...(post?.tags ?? [])];
		newTagInput = '';
		isEditingTags = true;
	}

	function cancelEditTags() {
		isEditingTags = false;
		tagEditError = undefined;
		editedTags = [];
		newTagInput = '';
	}

	function removeEditTag(tagId: number) {
		editedTags = editedTags.filter((t) => t.id !== tagId);
	}

	async function applyImplications(tag: TagInterface) {
		if (tag.id < 0) return; // new/unsaved tag, skip
		try {
			const res = await fetch(`/api/tag/${encodeURIComponent(tag.label)}/implications`);
			if (!res.ok) return;
			const impliedTags = (await res.json()) as TagInterface[];
			for (const implied of impliedTags) {
				if (!editedTags.some((t) => t.id === implied.id)) {
					editedTags = [...editedTags, implied];
				}
			}
		} catch {
			/* silently ignore */
		}
	}

	async function addTagFromSelect(tag: TagInterface) {
		if (editedTags.some((t) => t.id === tag.id)) return;
		editedTags = [...editedTags, tag];
		newTagInput = '';
		await applyImplications(tag);
	}

	async function addTagFromSubmit(val: string) {
		const label = val.trim().toLowerCase();
		if (!label) return;
		if (editedTags.some((t) => t.label === label)) {
			newTagInput = '';
			return;
		}
		const found = allTags.find((t) => t.label === label);
		if (found) {
			editedTags = [...editedTags, found];
			newTagInput = '';
			await applyImplications(found);
		} else {
			editedTags = [
				...editedTags,
				{
					id: -Date.now(),
					label,
					count: 0,
					category: { label: 'general', color: 'oklch(0.7933 0.0072 247.92)' }
				}
			];
			newTagInput = '';
		}
	}

	async function saveTags() {
		if (!post) return;

		tagEditError = undefined;
		tagEditSuccess = undefined;
		isSavingTags = true;

		try {
			const labels = Array.from(new Set(editedTags.map((t) => t.label)));

			const response = await fetch(`/api/post/${post.id}/tags`, {
				method: 'PUT',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ tag_labels: labels })
			});

			if (!response.ok) {
				const data = await response.json();
				throw new Error(data.detail || `HTTP error! Status: ${response.status}`);
			}

			const updatedTags = (await response.json()) as TagInterface[];

			post = { ...post, tags: updatedTags };

			isEditingTags = false;
			tagEditSuccess = 'Tags updated successfully';
			setTimeout(() => (tagEditSuccess = undefined), 3000);
		} catch (err) {
			tagEditError = err instanceof Error ? err.message : 'An error occurred';
		} finally {
			isSavingTags = false;
		}
	}

	async function deletePost() {
		if (!post || !confirm('Are you sure you want to delete this post? This cannot be undone.'))
			return;

		isDeleting = true;
		try {
			const response = await fetch(`/api/post/${post.id}`, { method: 'DELETE' });
			if (!response.ok) {
				const data = await response.json();
				throw new Error(data.detail || `HTTP error! Status: ${response.status}`);
			}
			goto('/posts/');
		} catch (err) {
			error = err instanceof Error ? err.message : 'An error occurred';
		} finally {
			isDeleting = false;
		}
	}
</script>

{#if isLoading}
	<p>Loading...</p>
{:else if notFound}
	<div class="flex flex-col items-center justify-center gap-4 pt-16">
		<p class="text-2xl font-semibold">Post not found</p>
		<p class="text-container-text/50">The post you're looking for doesn't exist.</p>
		<a
			href={resolve('/')}
			class="rounded-lg bg-violet-500 px-4 py-2 text-white hover:bg-violet-400"
		>
			Go to Home
		</a>
	</div>
{:else if error}
	<p class="error">Error: {error}</p>
{:else if post}
	<div class="flex w-full flex-col gap-4 md:flex-row">
		<div class="order-2 px-4 md:order-1 md:w-80 md:flex-none">
			<div class="flex flex-row items-center justify-center gap-2">
				<form onsubmit={submit} class="flex w-full flex-col gap-2">
					<TagInput
						bind:value
						placeholder="Search for tags"
						{allTags}
						multiTag={true}
						onsubmit={doSearch}
					/>

					<button
						type="submit"
						class="mb-2 w-full rounded-lg bg-violet-500 px-4 py-2 hover:cursor-pointer"
					>
						Search
					</button>
				</form>
			</div>

			<div class="flex flex-row items-center justify-between gap-2">
				<button
					type="button"
					class="flex w-full items-center justify-center rounded-lg border border-container-text/15 bg-container px-4 py-2 text-center text-container-text transition-colors hover:cursor-pointer hover:bg-container-alt disabled:cursor-not-allowed disabled:opacity-50"
					onclick={() => goto(`/post/${prevPostId}`)}
					disabled={prevPostId === null}
				>
					<ChevronLeft />
				</button>

				<button
					type="button"
					class="flex w-full items-center justify-center rounded-lg border border-container-text/15 bg-container px-4 py-2 text-center text-container-text transition-colors hover:cursor-pointer hover:bg-container-alt disabled:cursor-not-allowed disabled:opacity-50"
					onclick={() => goto(`/post/${nextPostId}`)}
					disabled={nextPostId === null}
				>
					<ChevronRight />
				</button>
			</div>
			<a href={resolve(`/data/media/${slug}.${post.type === 'video' ? 'mp4' : 'png'}`)} download>
				<button
					type="button"
					class="mt-2 flex w-full items-center justify-center rounded-lg border border-container-text/15 bg-container px-4 py-2 text-center text-container-text transition-colors hover:cursor-pointer hover:bg-container-alt"
				>
					<div class="flex w-full flex-row justify-between gap-2">
						Download File
						<Download />
					</div>
				</button>
			</a>
			<button
				type="button"
				disabled={isDeleting}
				class="mt-2 flex w-full items-center justify-center rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-2 text-center text-red-400 transition-colors hover:cursor-pointer hover:bg-red-500/20 disabled:cursor-not-allowed disabled:opacity-50"
				onclick={deletePost}
			>
				<div class="flex w-full flex-row justify-between gap-2">
					{isDeleting ? 'Deleting...' : 'Delete Post'}
					<X size={20} />
				</div>
			</button>
			<div class="mt-2 grid w-full grid-cols-2 gap-2">
				<div class="rounded-lg border border-container-text/15 bg-container px-3 py-2 text-center">
					<div class="text-xl font-semibold tabular-nums">{post.score}</div>
					<div class="text-xs opacity-70">Score</div>
				</div>

				<div class="rounded-lg border border-container-text/15 bg-container px-3 py-2 text-center">
					<div class="text-xl font-semibold tabular-nums">{post.tags?.length ?? 0}</div>
					<div class="text-xs opacity-70">Tags</div>
				</div>
			</div>

			{#if tagEditSuccess}
				<p class="mt-2 rounded-lg bg-green-500/20 px-4 py-2 text-green-400">{tagEditSuccess}</p>
			{/if}
			{#if tagEditError}
				<p class="mt-2 rounded-lg bg-red-500/20 px-4 py-2 text-red-400">{tagEditError}</p>
			{/if}

			{#if isEditingTags}
				<div class="mt-3 flex flex-col gap-2">
					<span class="text-xs tracking-wide uppercase opacity-70">Add Tag</span>
					<TagInput
						bind:value={newTagInput}
						placeholder="Type to add a tag..."
						allTags={availableTagsForAdd}
						multiTag={false}
						onselect={addTagFromSelect}
						onsubmit={addTagFromSubmit}
					/>

					{#each getGroupedTags(editedTags) as { label, color, tags } (label)}
						<div class="mt-1">
							<p class="text-xs tracking-wide uppercase opacity-70" style="color:{color}">
								{label}
							</p>
							{#each tags as tag (tag.id)}
								<div
									class="flex flex-row items-center gap-1 text-lg"
									style="color:{tag.category.color}"
								>
									<button
										type="button"
										class="shrink-0 rounded p-0.5 opacity-60 transition-opacity hover:cursor-pointer hover:opacity-100"
										onclick={() => removeEditTag(tag.id)}
									>
										<X size={14} />
									</button>
									<Tag size={16} />
									<span>{tag.label}</span>
									<span class="text-sm opacity-60">{tag.count}</span>
								</div>
							{/each}
						</div>
					{/each}

					<div class="mt-1 flex gap-2">
						<button
							type="button"
							disabled={isSavingTags}
							class="flex-1 rounded-lg bg-violet-500 px-4 py-2 text-white hover:cursor-pointer hover:bg-violet-400 disabled:cursor-not-allowed disabled:opacity-50"
							onclick={saveTags}
						>
							{isSavingTags ? 'Saving...' : 'Save Tags'}
						</button>
						<button
							type="button"
							class="flex-1 rounded-lg border border-container-text/15 bg-container px-4 py-2 text-container-text transition-colors hover:cursor-pointer hover:bg-container-alt"
							onclick={cancelEditTags}
						>
							Cancel
						</button>
					</div>
				</div>
			{:else}
				<button
					type="button"
					class="mt-3 w-full rounded-lg border border-container-text/15 bg-container px-4 py-2 text-container-text transition-colors hover:cursor-pointer hover:bg-container-alt"
					onclick={startEditTags}
				>
					Edit Tags
				</button>

				{#each getGroupedTags(post?.tags ?? []) as { label, color, tags } (label)}
					<div class="mt-3">
						<p class="text-xs tracking-wide uppercase opacity-70" style="color:{color}">
							{label}
						</p>
						{#each tags as tag (tag.id)}
							<div
								class="flex flex-row items-center gap-2 text-lg"
								style="color:{tag.category.color}"
							>
								<Tag size={16} />
								<a href={`/tag/${tag.label}`} class="hover:underline">{tag.label}</a>
								<p class="text-sm opacity-60">{tag.count}</p>
							</div>
						{/each}
					</div>
				{/each}
			{/if}
		</div>

		<div class="order-1 w-full max-w-7xl min-w-0 px-4 md:order-2">
			{#if post.type === 'video'}
				<!-- svelte-ignore a11y_media_has_caption -->
				<video class="block h-auto w-full rounded-lg" src={`/data/media/${slug}.mp4`} controls
				></video>
			{:else}
				<img
					class="block h-auto w-full rounded-lg"
					src={`/data/media/${slug}.png`}
					alt="Post {slug}"
				/>
			{/if}
		</div>
	</div>
{/if}
