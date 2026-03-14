<script lang="ts">
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import TagInput from '$lib/components/TagInput.svelte';
	import type { TagInterface } from '$lib/types/tag';
	import { X } from 'lucide-svelte';

	type MediaKind = 'image' | 'video';
	type MediaItem = {
		file: File;
		kind: MediaKind;
		url: string;
	};

	let items: MediaItem[] = $state([]);
	let fileInput: HTMLInputElement | undefined = $state();
	let tagValue = $state('');
	let allTags: TagInterface[] = $state([]);
	let uploading = $state(false);
	let error = $state('');
	const CHUNK_SIZE = 4 * 1024 * 1024;

	$effect(() => {
		fetch('/api/tags/')
			.then((r) => (r.ok ? r.json() : []))
			.then((tags) => (allTags = tags as TagInterface[]));
	});

	function kindOf(file: File): MediaKind | null {
		if (file.type.startsWith('image/')) return 'image';
		if (file.type.startsWith('video/')) return 'video';
		return null;
	}

	function addFiles(newFiles: File[]) {
		for (const file of newFiles) {
			const kind = kindOf(file);
			if (!kind) continue;
			items = [...items, { file, kind, url: URL.createObjectURL(file) }];
		}
	}

	function removeAt(index: number) {
		const it = items[index];
		if (it) URL.revokeObjectURL(it.url);
		items = items.filter((_, i) => i !== index);
	}

	function clear() {
		for (const it of items) URL.revokeObjectURL(it.url);
		items = [];
	}

	function onDrop(e: DragEvent) {
		e.preventDefault();
		if (e.dataTransfer) addFiles([...e.dataTransfer.files]);
	}

	function onDragOver(e: DragEvent) {
		if (!e.dataTransfer) return;
		const hasMedia = [...e.dataTransfer.items].some(
			(i) => i.kind === 'file' && (i.type.startsWith('image/') || i.type.startsWith('video/'))
		);
		if (hasMedia) {
			e.preventDefault();
			e.dataTransfer.dropEffect = 'copy';
		}
	}

	function onFileInputChange(e: Event) {
		const input = e.currentTarget as HTMLInputElement;
		if (!input.files) return;
		addFiles([...input.files]);
		input.value = '';
	}

	function openPicker() {
		fileInput?.click();
	}

	async function upload() {
		if (items.length === 0) return;
		uploading = true;
		error = '';

		try {
			const tags = tagValue.trim();
			let lastId: number | null = null;

			for (const item of items) {
				let uploadId = '';

				try {
					const initForm = new FormData();
					initForm.append('content_type', item.file.type);
					initForm.append('filename', item.file.name);

					const initRes = await fetch('/api/upload/init', {
						method: 'POST',
						body: initForm
					});

					if (!initRes.ok) {
						const data = await initRes.json().catch(() => ({ detail: 'Upload init failed' }));
						throw new Error(data.detail || `Upload init failed (${initRes.status})`);
					}

					const initData = await initRes.json();
					uploadId = initData.uploadId;

					if (!uploadId) {
						throw new Error('Upload init did not return upload ID');
					}

					let chunkIndex = 0;
					for (let offset = 0; offset < item.file.size; offset += CHUNK_SIZE) {
						const blob = item.file.slice(offset, offset + CHUNK_SIZE);
						const chunkForm = new FormData();
						chunkForm.append('upload_id', uploadId);
						chunkForm.append('chunk_index', String(chunkIndex));
						chunkForm.append('chunk', blob, item.file.name);

						const chunkRes = await fetch('/api/upload/chunk', {
							method: 'POST',
							body: chunkForm
						});

						if (!chunkRes.ok) {
							const data = await chunkRes.json().catch(() => ({ detail: 'Upload chunk failed' }));
							throw new Error(data.detail || `Upload chunk failed (${chunkRes.status})`);
						}

						chunkIndex += 1;
					}

					const completeForm = new FormData();
					completeForm.append('upload_id', uploadId);
					completeForm.append('tags', tags);

					const completeRes = await fetch('/api/upload/complete', {
						method: 'POST',
						body: completeForm
					});

					if (!completeRes.ok) {
						const data = await completeRes
							.json()
							.catch(() => ({ detail: 'Upload completion failed' }));
						throw new Error(data.detail || `Upload completion failed (${completeRes.status})`);
					}

					const completeData = await completeRes.json();
					lastId = completeData.id;
				} catch (itemErr) {
					if (uploadId) {
						await fetch(`/api/upload/${uploadId}`, { method: 'DELETE' }).catch(() => undefined);
					}
					throw itemErr;
				}
			}

			clear();
			tagValue = '';

			if (lastId !== null) {
				goto(resolve(`/post/${lastId}`));
			}
		} catch (err) {
			error = err instanceof Error ? err.message : 'Upload failed';
		} finally {
			uploading = false;
		}
	}
</script>

<svelte:window
	ondrop={(e) => {
		if (e.dataTransfer && [...e.dataTransfer.items].some((i) => i.kind === 'file')) {
			e.preventDefault();
		}
	}}
	ondragover={(e) => {
		if (e.dataTransfer && [...e.dataTransfer.items].some((i) => i.kind === 'file')) {
			e.preventDefault();
			e.dataTransfer.dropEffect = 'none';
		}
	}}
/>

<div class="flex w-full flex-col items-center gap-6 px-4 py-8">
	<h1 class="text-2xl font-bold">Upload</h1>

	{#if error}
		<p class="w-full max-w-3xl rounded bg-red-900/50 p-3 text-red-300">{error}</p>
	{/if}

	<button
		type="button"
		class="w-full max-w-3xl rounded-lg border-2 border-dashed border-neutral-600 bg-container py-20 text-container-text transition-colors hover:border-neutral-400 hover:text-white focus:border-neutral-400 focus:outline-none"
		onclick={openPicker}
		ondrop={onDrop}
		ondragover={onDragOver}
	>
		Drop images/videos here, or click to browse.
	</button>

	<input
		bind:this={fileInput}
		type="file"
		class="hidden"
		multiple
		accept="image/*,video/*"
		onchange={onFileInputChange}
	/>

	{#if items.length > 0}
		<div class="flex w-full max-w-3xl flex-col gap-2">
			{#each items as it, i (it.url)}
				<div class="flex items-center gap-3 rounded-lg bg-container p-2">
					{#if it.kind === 'image'}
						<img class="h-16 w-16 rounded object-cover" src={it.url} alt={it.file.name} />
					{:else}
						<video class="h-16 w-16 rounded object-cover" src={it.url} muted playsinline></video>
					{/if}
					<span class="min-w-0 flex-1 truncate text-sm">{it.file.name}</span>
					<button
						type="button"
						class="rounded p-1 text-neutral-400 transition-colors hover:text-white"
						onclick={() => removeAt(i)}
					>
						<X size={16} />
					</button>
				</div>
			{/each}
		</div>

		<div class="flex w-full max-w-3xl flex-col gap-2">
			<span class="text-sm text-container-text">Tags (space-separated, applied to all files)</span>
			<TagInput
				bind:value={tagValue}
				placeholder="e.g. landscape sky photo"
				{allTags}
				multiTag={true}
			/>
		</div>

		<div class="flex w-full max-w-3xl flex-row justify-center gap-4">
			<button
				type="button"
				disabled={uploading}
				class="rounded-lg bg-violet-500 px-12 py-3 font-semibold text-white transition-opacity hover:opacity-90 disabled:opacity-50"
				onclick={upload}
			>
				{uploading ? 'Uploading...' : `Upload ${items.length} file${items.length > 1 ? 's' : ''}`}
			</button>
			<button
				type="button"
				disabled={uploading}
				class="rounded-lg bg-red-500/80 px-12 py-3 font-semibold text-white transition-opacity hover:opacity-90 disabled:opacity-50"
				onclick={clear}
			>
				Clear all
			</button>
		</div>
	{/if}
</div>
