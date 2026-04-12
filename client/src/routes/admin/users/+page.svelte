<script lang="ts">
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { onMount } from 'svelte';

	type UserRole = 'owner' | 'admin' | 'moderator' | 'user';
	type UserInfo = {
		id: string;
		name: string;
		email: string;
		role: UserRole;
		banned: boolean;
		ban_reason: string | null;
		ban_expires: string | null;
	};

	type BootstrapStatus = {
		currentUser: UserInfo;
		ownerCount: number;
		ownerEmails: string[];
		canBootstrap: boolean;
		bootstrapRequired: boolean;
	};

	const ROLE_WEIGHT: Record<UserRole, number> = {
		user: 1,
		moderator: 2,
		admin: 3,
		owner: 4
	};

	const roleOptions: Record<UserRole, UserRole[]> = {
		user: ['user'],
		moderator: ['user', 'moderator'],
		admin: ['user', 'moderator'],
		owner: ['user', 'moderator', 'admin', 'owner']
	};

	let status = $state<BootstrapStatus | null>(null);
	let users = $state<UserInfo[]>([]);
	let loading = $state(true);
	let error = $state('');
	let message = $state('');
	let busyAction = $state<{ kind: 'bootstrap' | 'role' | 'ban'; id: string } | null>(null);
	let roleDrafts = $state<Record<string, UserRole>>({});
	let banReasons = $state<Record<string, string>>({});

	function canEditUser(actorRole: UserRole, targetRole: UserRole): boolean {
		if (actorRole === 'owner') return true;
		return ROLE_WEIGHT[targetRole] < ROLE_WEIGHT[actorRole];
	}

	function canBanUser(actorRole: UserRole, targetRole: UserRole): boolean {
		if (actorRole === 'owner') return true;
		return ROLE_WEIGHT[targetRole] < ROLE_WEIGHT[actorRole];
	}

	function getRoleOptions(actorRole: UserRole, targetRole: UserRole): UserRole[] {
		if (!canEditUser(actorRole, targetRole)) return [targetRole];
		return roleOptions[actorRole] ?? ['user'];
	}

	function formatLabel(role: UserRole): string {
		return role.charAt(0).toUpperCase() + role.slice(1);
	}

	function isBusy(kind: 'bootstrap' | 'role' | 'ban', id: string): boolean {
		return busyAction?.kind === kind && busyAction?.id === id;
	}

	async function loadUsers() {
		loading = true;
		error = '';
		message = '';

		try {
			const bootstrapRes = await fetch('/api/users/bootstrap');
			if (bootstrapRes.status === 401) {
				goto(resolve('/login'));
				return;
			}
			if (!bootstrapRes.ok) {
				error = 'Unable to load account status.';
				return;
			}

			status = (await bootstrapRes.json()) as BootstrapStatus;

			if (status.currentUser.role !== 'owner' && status.currentUser.role !== 'admin') {
				return;
			}

			const usersRes = await fetch('/api/users');
			if (!usersRes.ok) {
				if (usersRes.status === 403) {
					error = 'You do not have access to the user list.';
					return;
				}
				error = 'Unable to load users.';
				return;
			}

			users = (await usersRes.json()) as UserInfo[];
			roleDrafts = Object.fromEntries(users.map((user) => [user.id, user.role]));
			banReasons = Object.fromEntries(users.map((user) => [user.id, user.ban_reason ?? '']));
		} catch (loadError) {
			error = loadError instanceof Error ? loadError.message : 'Unable to load users.';
		} finally {
			loading = false;
		}
	}

	async function claimOwner() {
		if (!status) return;
		busyAction = { kind: 'bootstrap', id: status.currentUser.id };
		error = '';
		message = '';

		try {
			const response = await fetch('/api/users/bootstrap', { method: 'POST' });
			if (!response.ok) {
				const payload = await response.json().catch(() => null);
				error = payload?.detail ?? 'Unable to claim owner access.';
				return;
			}

			message = 'Owner access granted.';
			await loadUsers();
		} finally {
			busyAction = null;
		}
	}

	async function updateRole(user: UserInfo) {
		if (!status) return;
		const nextRole = roleDrafts[user.id] ?? user.role;
		if (nextRole === user.role) return;
		busyAction = { kind: 'role', id: user.id };
		error = '';
		message = '';

		try {
			const response = await fetch(`/api/users/${user.id}/role`, {
				method: 'PUT',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ role: nextRole })
			});

			if (!response.ok) {
				const payload = await response.json().catch(() => null);
				error = payload?.detail ?? 'Unable to update the role.';
				roleDrafts[user.id] = user.role;
				return;
			}

			const updatedUser = (await response.json()) as UserInfo;
			users = users.map((entry) => (entry.id === updatedUser.id ? updatedUser : entry));
			roleDrafts[user.id] = updatedUser.role;
			message = `${updatedUser.name} updated to ${formatLabel(updatedUser.role)}.`;
		} finally {
			busyAction = null;
		}
	}

	async function updateBan(user: UserInfo, banned: boolean) {
		if (!status) return;
		busyAction = { kind: 'ban', id: user.id };
		error = '';
		message = '';

		try {
			const response = await fetch(`/api/users/${user.id}/ban`, {
				method: 'PUT',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					banned,
					reason: banned ? (banReasons[user.id] ?? '').trim() || null : null
				})
			});

			if (!response.ok) {
				const payload = await response.json().catch(() => null);
				error = payload?.detail ?? 'Unable to update the ban status.';
				return;
			}

			const updatedUser = (await response.json()) as UserInfo;
			users = users.map((entry) => (entry.id === updatedUser.id ? updatedUser : entry));
			banReasons[user.id] = updatedUser.ban_reason ?? '';
			message = banned
				? `${updatedUser.name} has been banned.`
				: `${updatedUser.name} has been unbanned.`;
		} finally {
			busyAction = null;
		}
	}

	onMount(() => {
		void loadUsers();
	});
</script>

<svelte:head>
	<title>User Management</title>
</svelte:head>

<div class="mx-auto flex w-full max-w-7xl flex-col gap-8 px-4 py-8">
	<div
		class="flex flex-col gap-4 rounded-2xl border border-overlay0 bg-surface0/90 p-6 shadow-2xl shadow-crust/50 backdrop-blur"
	>
		<div class="flex flex-col gap-2">
			<p class="text-sm tracking-[0.3em] text-overlay1 uppercase">Administration</p>
			<div class="flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
				<div>
					<h1 class="text-3xl font-semibold text-text">User management</h1>
					<p class="mt-1 max-w-2xl text-sm text-overlay1">
						Assign roles, ban accounts, and bootstrap the first owner when the site is new.
					</p>
				</div>
				{#if status}
					<div
						class="rounded-xl border border-overlay0 bg-surface1/60 px-4 py-3 text-sm text-subtext1"
					>
						<p class="font-medium text-text">Signed in as {status.currentUser.name}</p>
						<p>{formatLabel(status.currentUser.role)} · {status.currentUser.email}</p>
					</div>
				{/if}
			</div>
		</div>

		{#if error}
			<div class="rounded-xl border border-red/30 bg-red/20 px-4 py-3 text-sm text-red">
				{error}
			</div>
		{/if}

		{#if message}
			<div
				class="rounded-xl border border-green/30 bg-green/20 px-4 py-3 text-sm text-green"
			>
				{message}
			</div>
		{/if}

		{#if loading}
			<div class="rounded-xl border border-overlay0 bg-surface1/60 px-4 py-6 text-sm text-overlay1">
				Loading user records...
			</div>
		{:else if status?.bootstrapRequired && status.canBootstrap}
			<div
				class="flex flex-col gap-4 rounded-xl border border-yellow/30 bg-yellow/20 p-5 text-yellow"
			>
				<div>
					<p class="text-sm tracking-[0.25em] text-yellow uppercase">Bootstrap required</p>
					<h2 class="mt-2 text-xl font-semibold text-text">Claim the owner account</h2>
					<p class="mt-2 max-w-3xl text-sm text-yellow/90">
						No owner exists yet. This account is eligible to become the first owner, which unlocks
						full moderation and permissions management.
					</p>
				</div>
				<button
					type="button"
					onclick={claimOwner}
					disabled={isBusy('bootstrap', status.currentUser.id)}
					class="inline-flex w-fit items-center rounded-lg bg-yellow px-4 py-2 font-semibold text-crust transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
				>
					{#if isBusy('bootstrap', status.currentUser.id)}
						Claiming owner access...
					{:else}
						Claim owner access
					{/if}
				</button>
			</div>
		{:else if status?.currentUser.role === 'owner' || status?.currentUser.role === 'admin'}
		<div class="overflow-hidden rounded-2xl border border-overlay0 bg-surface1/60">
			<div class="border-b border-overlay0 px-4 py-3 text-sm text-overlay1">
					{users.length} accounts
				</div>
				<div class="overflow-x-auto">
					<table class="min-w-full text-left text-sm">
						<thead class="bg-surface0/50 text-subtext1">
							<tr>
								<th class="px-4 py-3 font-medium">User</th>
								<th class="px-4 py-3 font-medium">Role</th>
								<th class="px-4 py-3 font-medium">Ban</th>
								<th class="px-4 py-3 font-medium">Notes</th>
							</tr>
						</thead>
						<tbody class="divide-y divide-white/10">
							{#each users as user}
								{@const editable =
									canEditUser(status.currentUser.role, user.role) &&
									user.id !== status.currentUser.id}
								{@const bannable =
									canBanUser(status.currentUser.role, user.role) &&
									user.id !== status.currentUser.id}
								<tr class="align-top text-subtext1">
									<td class="px-4 py-4">
										<div class="flex flex-col gap-1">
											<div class="font-medium text-text">{user.name}</div>
											<div class="text-xs text-overlay1">{user.email}</div>
											{#if user.id === status.currentUser.id}
												<span
													class="mt-1 inline-flex w-fit rounded-full border border-green/30 bg-emerald-500/10 px-2 py-1 text-[11px] tracking-[0.2em] text-green uppercase"
													>Current user</span
												>
											{/if}
										</div>
									</td>
									<td class="px-4 py-4">
										<div class="flex flex-col gap-2">
											<select
												bind:value={roleDrafts[user.id]}
												disabled={!editable || isBusy('role', user.id)}
												class="rounded-lg border border-overlay0 bg-surface1 px-3 py-2 text-text transition outline-none focus:border-mauve/60 disabled:cursor-not-allowed disabled:opacity-60"
												onchange={() => void updateRole(user)}
											>
												{#each getRoleOptions(status.currentUser.role, user.role) as option}
													<option value={option}>{formatLabel(option)}</option>
												{/each}
											</select>
											{#if !editable}
													<p class="text-xs text-overlay1">
													Role locked by your current permissions.
												</p>
											{:else if isBusy('role', user.id)}
													<p class="text-xs text-overlay1">Saving role change...</p>
											{/if}
										</div>
									</td>
									<td class="px-4 py-4">
										{#if user.banned}
											<div class="flex flex-col gap-2">
												<p class="text-sm text-red">Banned</p>
												{#if user.ban_reason}
															<p class="max-w-xs text-xs text-overlay1">{user.ban_reason}</p>
												{/if}
												<button
													type="button"
													onclick={() => void updateBan(user, false)}
													disabled={!bannable || isBusy('ban', user.id)}
															class="inline-flex w-fit items-center rounded-lg border border-overlay0 px-3 py-2 text-text transition hover:border-overlay1 disabled:cursor-not-allowed disabled:opacity-60"
												>
													{#if isBusy('ban', user.id)}
														Updating...
													{:else}
														Unban
													{/if}
												</button>
											</div>
										{:else}
											<div class="flex flex-col gap-2">
												<textarea
													bind:value={banReasons[user.id]}
													disabled={!bannable || isBusy('ban', user.id)}
													placeholder="Ban reason"
													rows="2"
															class="rounded-lg border border-overlay0 bg-surface1 px-3 py-2 text-text transition outline-none placeholder:text-overlay1 focus:border-mauve/60 disabled:cursor-not-allowed disabled:opacity-60"
												></textarea>
												<button
													type="button"
													onclick={() => void updateBan(user, true)}
													disabled={!bannable || isBusy('ban', user.id)}
															class="inline-flex w-fit items-center rounded-lg bg-red px-3 py-2 font-semibold text-text transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
												>
													{#if isBusy('ban', user.id)}
														Updating...
													{:else}
														Ban account
													{/if}
												</button>
											</div>
										{/if}
									</td>
									<td class="px-4 py-4 text-xs text-overlay1">
										{#if user.role === 'owner'}
											Owner accounts can only be downgraded by another owner.
										{:else if user.role === 'admin' && status.currentUser.role !== 'owner'}
											Admins cannot be edited by other admins.
										{:else if user.banned}
											Banned users are removed from active sessions immediately.
										{:else}
											No restrictions.
										{/if}
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			</div>
		{:else}
			<div class="rounded-xl border border-overlay0 bg-surface1/60 px-4 py-6 text-sm text-subtext1">
				You do not have permission to manage users.
			</div>
		{/if}
	</div>
</div>
