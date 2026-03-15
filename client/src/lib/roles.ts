export type UserRole = 'owner' | 'admin' | 'moderator' | 'user';

const ROLE_WEIGHT: Record<UserRole, number> = {
	user: 1,
	moderator: 2,
	admin: 3,
	owner: 4
};

function normalizeRole(role: unknown): UserRole {
	if (typeof role !== 'string') return 'user';
	const normalized = role.trim().toLowerCase();
	if (normalized === 'mod') return 'moderator';
	if (
		normalized === 'owner' ||
		normalized === 'admin' ||
		normalized === 'moderator' ||
		normalized === 'user'
	) {
		return normalized;
	}
	return 'user';
}

export function hasMinRole(role: unknown, minRole: UserRole): boolean {
	return ROLE_WEIGHT[normalizeRole(role)] >= ROLE_WEIGHT[minRole];
}

export function canModerate(role: unknown): boolean {
	return hasMinRole(role, 'moderator');
}

export function canAdmin(role: unknown): boolean {
	return hasMinRole(role, 'admin');
}
