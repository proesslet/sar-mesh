/** Join the class names that are actually set, dropping false/null/undefined. */
export function cx(...names: (string | false | null | undefined)[]): string {
  return names.filter(Boolean).join(" ");
}
