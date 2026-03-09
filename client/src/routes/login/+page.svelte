<script lang="ts">
	import { authClient } from '$lib/auth-client';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';

	let email = $state('');
	let password = $state('');
	let error = $state('');
	let loading = $state(false);

	async function handleLogin(e: SubmitEvent) {
		e.preventDefault();
		error = '';
		loading = true;

		const { error: authError } = await authClient.signIn.email({
			email,
			password
		});

		loading = false;

		if (authError) {
			error = authError.message ?? 'Login failed';
			return;
		}

		goto(resolve('/'));
	}
</script>

<div class="flex min-h-[80vh] items-center justify-center">
	<form
		onsubmit={handleLogin}
		class="flex w-full max-w-md flex-col gap-4 rounded-lg bg-container p-8"
	>
		<h1 class="text-2xl font-bold">Log In</h1>

		{#if error}
			<p class="rounded bg-red-900/50 p-2 text-red-300">{error}</p>
		{/if}

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
				class="rounded bg-container-alt px-3 py-2 text-white outline-none focus:ring-2 focus:ring-white/25"
			/>
		</label>

		<button
			type="submit"
			disabled={loading}
			class="mt-2 rounded bg-white px-4 py-2 font-semibold text-black transition-opacity hover:opacity-90 disabled:opacity-50"
		>
			{loading ? 'Logging in...' : 'Log In'}
		</button>

		<p class="text-center text-sm text-container-text">
			Don't have an account?
			<a href={resolve('/signup')} class="text-white underline">Sign up</a>
		</p>
	</form>
</div>
