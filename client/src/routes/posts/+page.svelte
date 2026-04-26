<script lang="ts">
	import { page } from '$app/state';
	import { resolve } from '$app/paths';
	import Post from '$lib/components/Post.svelte';
	import TagInput from '$lib/components/TagInput.svelte';
	import type { PostInterface } from '$lib/types/post';
	import type { TagInterface } from '$lib/types/tag';
	import { searchQuery } from '$lib/components/stores';

	let posts: PostInterface[] = $state([]);
	let allTags: TagInterface[] = $state([]);
	let isLoading = $state(true);
	let query = $state(page.url.searchParams.get('query') ?? $searchQuery ?? '');

	function doSearch() {
		const result = query.trim().replace(/\s+/g, ' ');
		query = result;
		searchQuery.set(result);
		const searchParams = result ? `query=${encodeURIComponent(result)}` : '';
		window.location.assign(
			searchParams ? `${resolve('/posts')}?${searchParams}` : `${resolve('/posts')}?`
		);
	}

	function submit(e: SubmitEvent) {
		e.preventDefault();
		doSearch();
	}

	$effect(() => {
		const queryFromUrl = page.url.searchParams.get('query') ?? '';
		query = queryFromUrl;

		const queryString = new URLSearchParams(page.url.searchParams).toString();

		(async () => {
			isLoading = true;
			try {
				const [postsRes, tagsRes] = await Promise.all([
					fetch(`/api/posts/?${queryString}`),
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

<div class="flex w-full flex-col items-center gap-6 px-4">
	<div class="flex w-full max-w-4xl flex-col gap-3">
		<form onsubmit={submit} class="flex flex-row items-center justify-center gap-2">
			<TagInput
				bind:value={query}
				placeholder="Search tags or use filters: sort:score type:image score:>10"
				{allTags}
				multiTag={true}
				onsubmit={doSearch}
			/>

			<button
				type="submit"
				class="rounded-full bg-linear-to-r from-pink to-mauve px-4 py-2 text-crust hover:cursor-pointer hover:opacity-90"
			>
				Search
			</button>
		</form>
	</div>

	<div class="flex w-full flex-col items-center gap-4">
		{#if isLoading}
			<p>Loading...</p>
		{:else if posts.length === 0}
			<p class="text-text/50">No posts found.</p>
		{:else}
			<div class="flex flex-row flex-wrap justify-center gap-4">
				{#each posts as post (post.id)}
					<Post postID={post.id} type={post.type} />
				{/each}
			</div>
		{/if}
	</div>
</div>
