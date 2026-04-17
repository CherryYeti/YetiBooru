export function formatDateTime(
	value: string | null | undefined,
	options?: Intl.DateTimeFormatOptions,
	fallback = '-'
): string {
	if (!value) return fallback;
	const date = new Date(value);
	if (Number.isNaN(date.getTime())) return value;
	return date.toLocaleString(undefined, options);
}
