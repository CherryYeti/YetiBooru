export interface TagInterface {
	label: string;
	count: number;
	id: number;
	category: CategoryInterface;
}
export interface CategoryInterface {
	id?: number;
	label: string;
	color: string;
	is_default?: boolean;
}
