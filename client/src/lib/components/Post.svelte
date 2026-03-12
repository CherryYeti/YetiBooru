<script lang="ts">
	import { resolve } from '$app/paths';

	let { postID, type = 'image' }: { postID: number; type?: string } = $props();
</script>

<a href={resolve(`/post/${postID}`)}
	><img
		alt="one"
		src={`/data/thumbnail/${postID}.png`}
		class="h-auto max-h-50 w-auto max-w-50 rounded-lg object-contain transition-transform hover:scale-105 hover:cursor-pointer {type ===
		'video'
			? 'border-3 border-violet-500'
			: ''}"
	/>
</a>
