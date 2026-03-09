<script lang="ts">
	import { resolve } from '$app/paths';
	import { authClient } from '$lib/auth-client';
	import { goto } from '$app/navigation';

	const session = authClient.useSession();
</script>

<div class="flex w-full flex-row gap-8 p-4">
	<a
		href={resolve('/')}
		class="inline-flex items-center text-neutral-400 transition-colors hover:text-white"
	>
		Home
	</a>
	<a
		href={resolve('/posts')}
		class="inline-flex items-center text-neutral-400 transition-colors hover:text-white"
	>
		Posts
	</a>
	{#if $session?.data}
		<a
			href={resolve('/upload')}
			class="inline-flex items-center text-neutral-400 transition-colors hover:text-white"
		>
			Upload
		</a>
	{/if}
	<a
		href={resolve('/tags')}
		class="inline-flex items-center text-neutral-400 transition-colors hover:text-white"
	>
		Tags
	</a>
	<a
		href={resolve('/categories')}
		class="inline-flex items-center text-neutral-400 transition-colors hover:text-white"
	>
		Categories
	</a>

	<div class="ml-auto flex flex-row gap-4">
		{#if $session?.data}
			<span class="inline-flex items-center text-neutral-400">
				{$session.data.user.name}
			</span>
			<button
				onclick={async () => {
					await authClient.signOut();
					goto(resolve('/'));
				}}
				class="inline-flex items-center text-neutral-400 transition-colors hover:cursor-pointer hover:text-white"
			>
				Sign Out
			</button>
		{:else}
			<a
				href={resolve('/login')}
				class="inline-flex items-center text-neutral-400 transition-colors hover:cursor-pointer hover:text-white"
			>
				Log In
			</a>
			<a
				href={resolve('/signup')}
				class="inline-flex items-center text-neutral-400 transition-colors hover:cursor-pointer hover:text-white"
			>
				Sign Up
			</a>
		{/if}
	</div>
</div>
