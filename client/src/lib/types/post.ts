import type { TagInterface } from './tag';

export interface PostInterface {
	id: number;
	score: number;
	tags?: TagInterface[];
	type: 'video' | 'image';
	media_ext: string;
}
