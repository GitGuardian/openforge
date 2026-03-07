import { marked } from "marked";
import createDOMPurify from "dompurify";
import { JSDOM } from "jsdom";

const { window } = new JSDOM("");
// eslint-disable-next-line @typescript-eslint/no-explicit-any -- jsdom Window is structurally compatible but types diverge
const DOMPurify = createDOMPurify(window as any);

marked.setOptions({
  gfm: true,
  breaks: false,
});

/**
 * Render a Markdown string to sanitized HTML.
 *
 * - GFM (tables, autolinks, strikethrough) is enabled.
 * - Output is sanitized with DOMPurify (scripts and event handlers stripped).
 * - Empty / nullish input returns an empty string.
 */
export function renderMarkdown(input: string): string {
  if (!input) {
    return "";
  }

  const raw = marked.parse(input, { async: false }) as string;
  return DOMPurify.sanitize(raw);
}
