import type { TagInterface } from './tag';

export interface PostInterface {
	id: number;
	score: number;
	tags?: TagInterface[];
	type: 'video' | 'image';
	media_ext: string;
	uploaded_at: string;
	uploader_name: string | null;
	media_width: number | null;
	media_height: number | null;
	source_url: string | null;
}
