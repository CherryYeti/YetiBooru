<script lang="ts">
	import { page } from '$app/state';
	$: queryParam = page.url.searchParams.get('q');
</script>

<div class="flex justify-center pt-8">
	<div class="flex w-full max-w-7xl flex-wrap items-center justify-center gap-4 px-8">
		<label class="pb-2">
			<input
				class="h-full rounded-lg bg-container px-4 py-2 text-lg outline-none"
				placeholder="Search for tags"
				value={queryParam}
			/>
		</label>
	</div>
</div>
