import { betterAuth } from 'better-auth';
import { admin } from 'better-auth/plugins';
import { Pool } from 'pg';
import { env } from '$env/dynamic/private';

export const auth = betterAuth({
	secret: env.BETTER_AUTH_SECRET,
	baseURL: env.BETTER_AUTH_URL,
	database: new Pool({
		user: env.DB_USER,
		password: env.DB_PASSWORD,
		host: env.DB_HOST,
		port: parseInt(env.DB_PORT || '5432'),
		database: env.DB_NAME
	}),
	emailAndPassword: {
		enabled: true
	},
	plugins: [admin()]
});
