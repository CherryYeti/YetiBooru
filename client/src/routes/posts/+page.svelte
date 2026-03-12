<script lang="ts">
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import Post from '$lib/components/Post.svelte';
	import TagInput from '$lib/components/TagInput.svelte';
	import type { PostInterface } from '$lib/types/post';
	import type { TagInterface } from '$lib/types/tag';
	import { searchQuery } from '$lib/components/stores';

	let posts: PostInterface[] = $state([]);
	let allTags: TagInterface[] = $state([]);
	let isLoading = $state(true);

	let value = $derived(page.url.searchParams.get('query') ?? $searchQuery ?? '');

	function doSearch() {
		const result = value.trim().replace(/\s+/g, ' ');
		searchQuery.set(result);
		goto(resolve(`/posts/?query=${encodeURIComponent(result)}`));
	}

	function submit(e: SubmitEvent) {
		e.preventDefault();
		doSearch();
	}

	$effect(() => {
		const query = page.url.searchParams.get('query') || '';

		(async () => {
			isLoading = true;
			try {
				const [postsRes, tagsRes] = await Promise.all([
					fetch(`/api/posts/?query=${encodeURIComponent(query)}`),
					fetch('/api/tags/')
				]);
				if (postsRes.ok) {
					posts = await postsRes.json();
				}
				if (tagsRes.ok) {
					allTags = (await tagsRes.json()) as TagInterface[];
				}
			} finally {
				isLoading = false;
			}
		})();
	});
</script>

<div class="flex w-full flex-col items-center gap-4 px-4">
	<div class="flex flex-row items-center justify-center gap-2">
		<form onsubmit={submit} class="flex flex-row items-center justify-center gap-2">
			<TagInput
				bind:value
				placeholder="Search for tags"
				{allTags}
				multiTag={true}
				onsubmit={doSearch}
			/>

			<button type="submit" class="rounded-lg bg-violet-500 px-4 py-2 hover:cursor-pointer">
				Search
			</button>
		</form>
	</div>

	{#if isLoading}
		<p>Loading...</p>
	{:else if posts.length === 0}
		<p class="text-container-text/50">No posts found.</p>
	{:else}
		<div class="flex flex-row flex-wrap justify-center gap-4">
			{#each posts as post (post.id)}
				<Post postID={post.id} />
			{/each}
		</div>
	{/if}
</div>
