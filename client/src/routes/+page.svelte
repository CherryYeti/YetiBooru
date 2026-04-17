<script lang="ts">
	import { resolve } from '$app/paths';
	import { ChevronRight } from 'lucide-svelte';
	import { goto } from '$app/navigation';
	import { searchQuery } from '$lib/components/stores';
	import TagInput from '$lib/components/TagInput.svelte';
	import type { TagInterface } from '$lib/types/tag';

	let value = $derived($searchQuery ?? '');
	let allTags: TagInterface[] = $state([]);

	let postCount = $state(0);
	let totalBytes = $state(0);
	let statsLoaded = $state(false);

	$effect(() => {
		(async () => {
			try {
				const [statsRes, tagsRes] = await Promise.all([fetch('/api/stats'), fetch('/api/tags/')]);
				if (statsRes.ok) {
					const data = await statsRes.json();
					postCount = data.postCount;
					totalBytes = data.totalBytes;
				}
				if (tagsRes.ok) {
					allTags = (await tagsRes.json()) as TagInterface[];
				}
			} finally {
				statsLoaded = true;
			}
		})();
	});

	function formatBytes(bytes: number): string {
		if (bytes === 0) return '0 B';
		const units = ['B', 'KB', 'MB', 'GB', 'TB'];
		const i = Math.floor(Math.log(bytes) / Math.log(1024));
		const value = bytes / Math.pow(1024, i);
		return `${value.toFixed(value < 10 && i > 0 ? 1 : 0)} ${units[i]}`;
	}

	function submit(e: SubmitEvent) {
		e.preventDefault();
		const result = value.trim().replace(/\s+/g, ' ');
		searchQuery.set(result);
		goto(resolve(`/posts/?query=${encodeURIComponent(result)}`));
	}
</script>

<div class="flex w-full flex-col items-center gap-8">
	<h2 class="pt-16 text-7xl font-bold">YetiBooru</h2>

	<div class="flex flex-row items-center justify-center gap-2">
		<form onsubmit={submit} class="flex flex-row items-center justify-center gap-2">
			<TagInput
				bind:value
				placeholder="Search for tags"
				{allTags}
				multiTag={true}
				onsubmit={() => {
					const result = value.trim().replace(/\s+/g, ' ');
					searchQuery.set(result);
					goto(resolve(`/posts/?query=${encodeURIComponent(result)}`));
				}}
			/>

			<button
				type="submit"
				class="rounded-full bg-linear-to-r from-pink to-mauve px-4 py-2 text-crust hover:cursor-pointer hover:opacity-90"
				>Search</button
			>
		</form>
	</div>

	<div class="flex flex-col items-center gap-2">
		{#if statsLoaded}
			<p>{postCount} Posts - {formatBytes(totalBytes)}</p>
		{:else}
			<p class="opacity-50">Loading stats...</p>
		{/if}
		<a
			href={resolve('/posts')}
			class="inline-flex items-center text-overlay1 transition-colors hover:text-text"
		>
			<span>View recent posts</span>
			<ChevronRight className="ml-1 h-4 w-4" />
		</a>
	</div>
</div>
