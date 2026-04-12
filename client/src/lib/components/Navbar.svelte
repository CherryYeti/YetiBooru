<script lang="ts">
	import { resolve } from '$app/paths';
	import { authClient } from '$lib/auth-client';
	import { canAdmin } from '$lib/roles';
	import { goto } from '$app/navigation';

	const session = authClient.useSession();
	const role = $derived($session?.data?.user?.role ?? 'user');
	const canViewAdmin = $derived(canAdmin(role));
</script>

<div class="flex w-full flex-row gap-8 p-4">
	<a
		href={resolve('/')}
		class="inline-flex items-center text-overlay2 transition-colors hover:text-text"
	>
		Home
	</a>
	<a
		href={resolve('/posts')}
		class="inline-flex items-center text-overlay2 transition-colors hover:text-text"
	>
		Posts
	</a>
	{#if $session?.data}
		<a
			href={resolve('/upload')}
			class="inline-flex items-center text-overlay2 transition-colors hover:text-text"
		>
			Upload
		</a>
	{/if}
	<a
		href={resolve('/tags')}
		class="inline-flex items-center text-overlay2 transition-colors hover:text-text"
	>
		Tags
	</a>
	<a
		href={resolve('/categories')}
		class="inline-flex items-center text-overlay2 transition-colors hover:text-text"
	>
		Categories
	</a>
	{#if canViewAdmin}
		<a
			href="/admin/users"
			class="inline-flex items-center text-overlay2 transition-colors hover:text-text"
		>
			Admin
		</a>
	{/if}

	<div class="ml-auto flex flex-row gap-4">
		{#if $session?.data}
			<span class="inline-flex items-center text-overlay2">
				{$session.data.user.name}
			</span>
			<button
				onclick={async () => {
					await authClient.signOut();
					goto(resolve('/'));
				}}
				class="inline-flex items-center text-overlay2 transition-colors hover:cursor-pointer hover:text-text"
			>
				Sign Out
			</button>
		{:else}
			<a
				href={resolve('/login')}
				class="inline-flex items-center text-overlay2 transition-colors hover:cursor-pointer hover:text-text"
			>
				Log In
			</a>
			<a
				href={resolve('/signup')}
				class="inline-flex items-center text-overlay2 transition-colors hover:cursor-pointer hover:text-text"
			>
				Sign Up
			</a>
		{/if}
	</div>
</div>
