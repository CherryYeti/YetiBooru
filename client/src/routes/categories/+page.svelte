<script lang="ts">
	import type { CategoryInterface } from '$lib/types/tag';
	import { authClient } from '$lib/auth-client';
	import { canAdmin, canModerate } from '$lib/roles';

	let session = authClient.useSession();
	let role = $derived($session?.data?.user?.role ?? 'user');
	let canManageCategories = $derived(canModerate(role));
	let canSetDefaultCategory = $derived(canAdmin(role));

	let categories: CategoryInterface[] = $state([]);
	let isLoading = $state(true);
	let error: string | undefined = $state();

	let showCreateForm = $state(false);
	let newCategoryLabel = $state('');
	let newCategoryColor = $state('oklch(0.7933 0.0072 247.92)');
	let createError: string | undefined = $state();
	let createSuccess: string | undefined = $state();
	let isCreating = $state(false);

	let editingOriginalLabel: string | undefined = $state();
	let editLabel = $state('');
	let editColor = $state('');
	let editError: string | undefined = $state();
	let editSuccess: string | undefined = $state();
	let isSavingEdit = $state(false);
	let defaultError: string | undefined = $state();
	let isSettingDefault = $state(false);

	async function loadCategories() {
		isLoading = true;
		error = undefined;
		try {
			const res = await fetch('/api/categories');
			if (!res.ok) throw new Error(`HTTP error! Status: ${res.status}`);
			categories = (await res.json()) as CategoryInterface[];
		} catch (err) {
			error = err instanceof Error ? err.message : 'An error occurred';
		} finally {
			isLoading = false;
		}
	}

	$effect(() => {
		void loadCategories();
	});

	function startEdit(category: CategoryInterface) {
		editingOriginalLabel = category.label;
		editLabel = category.label;
		editColor = category.color;
		editError = undefined;
		editSuccess = undefined;
		defaultError = undefined;
	}

	function cancelEdit() {
		editingOriginalLabel = undefined;
		editLabel = '';
		editColor = '';
		editError = undefined;
	}

	async function setDefaultCategory(label: string) {
		defaultError = undefined;
		isSettingDefault = true;
		try {
			const response = await fetch(`/api/category/${encodeURIComponent(label)}/default`, {
				method: 'PUT'
			});

			if (!response.ok) {
				const data = await response.json();
				throw new Error(data.detail || `HTTP error! Status: ${response.status}`);
			}

			const updated = (await response.json()) as CategoryInterface;
			categories = categories.map((c) => ({
				...c,
				is_default: c.id === updated.id
			}));
		} catch (err) {
			defaultError = err instanceof Error ? err.message : 'An error occurred';
		} finally {
			isSettingDefault = false;
		}
	}

	async function createCategory(e: SubmitEvent) {
		e.preventDefault();
		createError = undefined;
		createSuccess = undefined;

		const label = newCategoryLabel.trim().toLowerCase();
		const color = newCategoryColor.trim();

		if (!label) {
			createError = 'Category label cannot be empty';
			return;
		}
		if (!color) {
			createError = 'Category color cannot be empty';
			return;
		}

		isCreating = true;
		try {
			const response = await fetch('/api/categories', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ label, color })
			});

			if (!response.ok) {
				const data = await response.json();
				throw new Error(data.detail || `HTTP error! Status: ${response.status}`);
			}

			const created = (await response.json()) as CategoryInterface;
			categories = [...categories, created].sort((a, b) => (a.id ?? 0) - (b.id ?? 0));

			newCategoryLabel = '';
			showCreateForm = false;
			createSuccess = 'Category created successfully';
			setTimeout(() => (createSuccess = undefined), 3000);
		} catch (err) {
			createError = err instanceof Error ? err.message : 'An error occurred';
		} finally {
			isCreating = false;
		}
	}

	async function saveEdit(e: SubmitEvent) {
		e.preventDefault();
		if (!editingOriginalLabel) return;

		editError = undefined;
		editSuccess = undefined;

		const label = editLabel.trim().toLowerCase();
		const color = editColor.trim();

		if (!label) {
			editError = 'Category label cannot be empty';
			return;
		}
		if (!color) {
			editError = 'Category color cannot be empty';
			return;
		}

		isSavingEdit = true;
		try {
			const response = await fetch(`/api/category/${encodeURIComponent(editingOriginalLabel)}`, {
				method: 'PUT',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ label, color })
			});

			if (!response.ok) {
				const data = await response.json();
				throw new Error(data.detail || `HTTP error! Status: ${response.status}`);
			}

			const updated = (await response.json()) as CategoryInterface;
			categories = categories.map((c) =>
				c.id && updated.id
					? c.id === updated.id
						? updated
						: c
					: c.label === editingOriginalLabel
						? updated
						: c
			);

			editingOriginalLabel = undefined;
			editSuccess = 'Category updated successfully';
			setTimeout(() => (editSuccess = undefined), 3000);
		} catch (err) {
			editError = err instanceof Error ? err.message : 'An error occurred';
		} finally {
			isSavingEdit = false;
		}
	}
</script>

{#if isLoading}
	<p>Loading...</p>
{:else if error}
	<p class="error">Error: {error}</p>
{:else}
	<div class="flex flex-col items-center justify-center gap-8 pt-8">
		<div class="w-full max-w-5xl rounded-xl bg-mantle p-6">
			<div class="mb-4 flex items-center justify-between">
				{#if canManageCategories}
					<button
						type="button"
						class="rounded-lg bg-mantle px-4 py-2 text-text transition-colors hover:cursor-pointer hover:bg-crust"
						onclick={() => (showCreateForm = !showCreateForm)}
					>
						{showCreateForm ? 'Cancel' : 'Create Category'}
					</button>
				{/if}
			</div>

			{#if createSuccess}
				<p class="mb-4 rounded-lg bg-green/20 px-4 py-2 text-green">{createSuccess}</p>
			{/if}
			{#if editSuccess}
				<p class="mb-4 rounded-lg bg-green/20 px-4 py-2 text-green">{editSuccess}</p>
			{/if}
			{#if defaultError}
				<p class="mb-4 rounded-lg bg-red/20 px-4 py-2 text-red">{defaultError}</p>
			{/if}

			{#if showCreateForm}
				<form onsubmit={createCategory} class="mb-6 flex flex-col gap-3 rounded-lg bg-crust p-4">
					{#if createError}
						<p class="rounded-lg bg-red/20 px-4 py-2 text-red">{createError}</p>
					{/if}

					<div class="flex flex-col gap-1">
						<label for="new-category-label" class="text-sm text-text">Label</label>
						<input
							id="new-category-label"
							bind:value={newCategoryLabel}
							class="rounded-lg bg-mantle px-4 py-2 text-lg outline-none"
							placeholder="e.g. species"
						/>
					</div>

					<div class="flex flex-col gap-1">
						<label for="new-category-color" class="text-sm text-text">Color</label>
						<input
							id="new-category-color"
							bind:value={newCategoryColor}
							class="rounded-lg bg-mantle px-4 py-2 text-lg outline-none"
							placeholder="e.g. oklch(0.72 0.19 145)"
						/>
					</div>

					<button
						type="submit"
						disabled={isCreating}
						class="rounded-full bg-linear-to-r from-pink to-mauve px-4 py-2 font-semibold text-crust hover:cursor-pointer hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
					>
						{isCreating ? 'Creating...' : 'Create'}
					</button>
				</form>
			{/if}

			<div class="flex flex-col gap-4">
				{#if categories.length === 0}
					<p class="text-text/50">No categories found.</p>
				{:else}
					{#each categories as category (category.id ?? category.label)}
						<div class="rounded-lg bg-crust p-4">
							{#if editingOriginalLabel === category.label}
								<form onsubmit={saveEdit} class="flex flex-col gap-3">
									{#if editError}
										<p class="rounded-lg bg-red/20 px-4 py-2 text-red">{editError}</p>
									{/if}

									<div class="flex flex-col gap-1">
										<label for="edit-label-{category.label}" class="text-sm text-text">Label</label>
										<input
											id="edit-label-{category.label}"
											bind:value={editLabel}
											class="rounded-lg bg-mantle px-4 py-2 text-lg outline-none"
										/>
									</div>

									<div class="flex flex-col gap-1">
										<label for="edit-color-{category.label}" class="text-sm text-text">Color</label>
										<input
											id="edit-color-{category.label}"
											bind:value={editColor}
											class="rounded-lg bg-mantle px-4 py-2 text-lg outline-none"
										/>
									</div>

									<div class="flex gap-2">
										<button
											type="submit"
											disabled={isSavingEdit}
											class="rounded-full bg-linear-to-r from-pink to-mauve px-4 py-2 font-semibold text-crust hover:cursor-pointer hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
										>
											{isSavingEdit ? 'Saving...' : 'Save'}
										</button>
										<button
											type="button"
											class="rounded-lg bg-mantle px-4 py-2 text-text transition-colors hover:cursor-pointer hover:bg-mantle"
											onclick={cancelEdit}
										>
											Cancel
										</button>
									</div>
								</form>
							{:else}
								<div class="flex items-center justify-between gap-3">
									<div class="flex items-center gap-3">
										<p class="text-2xl font-semibold" style="color:{category.color}">
											{category.label}
										</p>
										{#if category.is_default}
											<span
												class="rounded-full border border-green-400/40 bg-green-500/15 px-2 py-0.5 text-xs text-green"
												>default</span
											>
										{/if}
									</div>
									{#if canManageCategories}
										<div class="flex gap-2">
											{#if !category.is_default && canSetDefaultCategory}
												<button
													type="button"
													disabled={isSettingDefault}
													class="rounded-lg border border-green-400/30 bg-green-500/10 px-4 py-2 text-green transition-colors hover:cursor-pointer hover:bg-green/20 disabled:cursor-not-allowed disabled:opacity-50"
													onclick={() => setDefaultCategory(category.label)}
												>
													Set Default
												</button>
											{/if}
											<button
												type="button"
												class="rounded-lg bg-mantle px-4 py-2 text-text transition-colors hover:cursor-pointer hover:bg-mantle"
												onclick={() => startEdit(category)}
											>
												Edit
											</button>
										</div>
									{/if}
								</div>
							{/if}
						</div>
					{/each}
				{/if}
			</div>
		</div>
	</div>
{/if}
