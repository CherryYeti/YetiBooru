<script lang="ts">
	import type { TagInterface } from '$lib/types/tag';

	let {
		value = $bindable(''),
		placeholder = 'Search for tags',
		allTags = [] as TagInterface[],
		onsubmit = undefined as ((value: string) => void) | undefined,
		onselect = undefined as ((tag: TagInterface) => void) | undefined,
		multiTag = false
	}: {
		value?: string;
		placeholder?: string;
		allTags?: TagInterface[];
		onsubmit?: ((value: string) => void) | undefined;
		onselect?: ((tag: TagInterface) => void) | undefined;
		multiTag?: boolean;
	} = $props();

	let showDropdown = $state(false);
	let inputEl: HTMLInputElement | undefined = $state();

	let currentToken = $derived.by(() => {
		if (!value) return '';
		if (multiTag) {
			const parts = value.split(/\s+/);
			return (parts[parts.length - 1] ?? '').trim().toLowerCase();
		}
		return value.trim().toLowerCase();
	});

	let filteredSuggestions = $derived(
		currentToken.length > 0 ? allTags.filter((t) => t.label.includes(currentToken)).slice(0, 8) : []
	);

	function selectSuggestion(tag: TagInterface) {
		if (onselect) {
			onselect(tag);
			return;
		}

		if (multiTag) {
			const parts = value.split(/\s+/);
			parts[parts.length - 1] = tag.label;
			value = parts.join(' ') + ' ';
		} else {
			value = tag.label;
		}

		showDropdown = false;
		inputEl?.focus();
	}

	function handleSuggestionMouseDown(event: MouseEvent, tag: TagInterface) {
		event.preventDefault();
		selectSuggestion(tag);
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter') {
			showDropdown = false;
			if (onsubmit) {
				e.preventDefault();
				onsubmit(value);
			}
		} else if (e.key === 'Escape') {
			showDropdown = false;
		}
	}

	function handleInput() {
		showDropdown = true;
	}

	function handleFocus() {
		showDropdown = true;
	}

	function handleBlur() {
		setTimeout(() => (showDropdown = false), 150);
	}
</script>

<div class="relative flex-1">
	<input
		bind:this={inputEl}
		bind:value
		class="h-full w-full rounded-lg bg-mantle px-4 py-2 text-lg text-white outline-none focus:ring-2 focus:ring-mauve focus:outline-none active:outline-none"
		{placeholder}
		oninput={handleInput}
		onfocus={handleFocus}
		onblur={handleBlur}
		onkeydown={handleKeydown}
	/>

	{#if showDropdown && filteredSuggestions.length > 0}
		<div
			class="absolute top-full right-0 left-0 z-50 mt-1 max-h-48 overflow-y-auto rounded-lg border border-text/15 bg-surface1 shadow-lg"
		>
			{#each filteredSuggestions as suggestion (suggestion.id)}
				<button
					type="button"
					class="w-full px-4 py-2 text-left transition-colors hover:cursor-pointer hover:bg-surface0"
					style="color:{suggestion.category.color}"
					onmousedown={(event) => handleSuggestionMouseDown(event, suggestion)}
				>
					{suggestion.label}
					<span class="ml-2 text-xs opacity-50">{suggestion.category.label}</span>
					<span class="ml-1 text-xs opacity-30">{suggestion.count}</span>
				</button>
			{/each}
		</div>
	{/if}
</div>
