/**
 * Escape SQL ILIKE wildcards (%, _, \) in user input.
 */
export function escapeLike(s: string): string {
  return s.replace(/\\/g, "\\\\").replace(/%/g, "\\%").replace(/_/g, "\\_");
}
