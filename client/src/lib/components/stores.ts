import { writable } from 'svelte/store';
import { browser } from '$app/environment';

const SEARCHKEY = 'searchQuery';
const TAGKEY = 'tagQuery';

function createSearchQuery() {
	const initial = browser ? (localStorage.getItem(SEARCHKEY) ?? '') : '';
	const { subscribe, set } = writable(initial);

	return {
		subscribe,
		set: (v: string) => {
			if (browser) localStorage.setItem(SEARCHKEY, v);
			set(v);
		},
		clear: () => {
			if (browser) localStorage.removeItem(SEARCHKEY);
			set('');
		}
	};
}

function createTagQuery() {
	const initial = browser ? (localStorage.getItem(TAGKEY) ?? '') : '';
	const { subscribe, set } = writable(initial);

	return {
		subscribe,
		set: (v: string) => {
			if (browser) localStorage.setItem(TAGKEY, v);
			set(v);
		},
		clear: () => {
			if (browser) localStorage.removeItem(TAGKEY);
			set('');
		}
	};
}

export const searchQuery = createSearchQuery();
export const tagQuery = createTagQuery();
