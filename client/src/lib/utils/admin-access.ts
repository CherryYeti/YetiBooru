import type { BootstrapStatus } from '$lib/types/admin';

export type BootstrapLoadResult =
	| { kind: 'ok'; status: BootstrapStatus }
	| { kind: 'unauthorized' }
	| { kind: 'error'; message: string };

export async function loadBootstrapStatus(
	fallbackErrorMessage: string
): Promise<BootstrapLoadResult> {
	const bootstrapRes = await fetch('/api/users/bootstrap');
	if (bootstrapRes.status === 401) {
		return { kind: 'unauthorized' };
	}
	if (!bootstrapRes.ok) {
		return { kind: 'error', message: fallbackErrorMessage };
	}

	const status = (await bootstrapRes.json()) as BootstrapStatus;
	return { kind: 'ok', status };
}
