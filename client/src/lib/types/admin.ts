export type UserRole = 'owner' | 'admin' | 'moderator' | 'user';

export type UserInfo = {
	id: string;
	name: string;
	email: string;
	role: UserRole;
	banned: boolean;
	ban_reason: string | null;
	ban_expires: string | null;
};

export type BootstrapStatus = {
	currentUser: UserInfo;
	ownerCount: number;
	ownerEmails: string[];
	canBootstrap: boolean;
	bootstrapRequired: boolean;
};
