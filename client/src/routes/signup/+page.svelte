<script lang="ts">
	import { authClient } from '$lib/auth-client';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';

	let name = $state('');
	let email = $state('');
	let password = $state('');
	let error = $state('');
	let loading = $state(false);

	async function handleSignUp(e: SubmitEvent) {
		e.preventDefault();
		error = '';
		loading = true;

		const { error: authError } = await authClient.signUp.email({
			name,
			email,
			password
		});

		loading = false;

		if (authError) {
			error = authError.message ?? 'Sign up failed';
			return;
		}

		goto(resolve('/'));
	}
</script>

<div class="flex min-h-[80vh] items-center justify-center">
	<form
		onsubmit={handleSignUp}
		class="flex w-full max-w-md flex-col gap-4 rounded-lg bg-container p-8"
	>
		<h1 class="text-2xl font-bold">Sign Up</h1>

		{#if error}
			<p class="rounded bg-red-900/50 p-2 text-red-300">{error}</p>
		{/if}

		<label class="flex flex-col gap-1">
			<span class="text-sm text-container-text">Name</span>
			<input
				type="text"
				bind:value={name}
				required
				class="rounded bg-container-alt px-3 py-2 text-white outline-none focus:ring-2 focus:ring-white/25"
			/>
		</label>

		<label class="flex flex-col gap-1">
			<span class="text-sm text-container-text">Email</span>
			<input
				type="email"
				bind:value={email}
				required
				class="rounded bg-container-alt px-3 py-2 text-white outline-none focus:ring-2 focus:ring-white/25"
			/>
		</label>

		<label class="flex flex-col gap-1">
			<span class="text-sm text-container-text">Password</span>
			<input
				type="password"
				bind:value={password}
				required
				minlength="8"
				class="rounded bg-container-alt px-3 py-2 text-white outline-none focus:ring-2 focus:ring-white/25"
			/>
		</label>

		<button
			type="submit"
			disabled={loading}
			class="mt-2 rounded-lg bg-violet-500 px-4 py-2 font-semibold text-white transition-opacity hover:cursor-pointer hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
		>
			{loading ? 'Creating account...' : 'Sign Up'}
		</button>

		<p class="text-center text-sm text-container-text">
			Already have an account?
			<a href={resolve('/login')} class="text-white underline">Log in</a>
		</p>
	</form>
</div>
