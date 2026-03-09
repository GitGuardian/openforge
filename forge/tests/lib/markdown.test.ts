import { describe, expect, test } from "bun:test";
import { renderMarkdown } from "../../src/lib/markdown";

describe("renderMarkdown", () => {
  test("renders basic markdown to HTML", () => {
    const html = renderMarkdown("**bold** and *italic*");
    expect(html).toContain("<strong>bold</strong>");
    expect(html).toContain("<em>italic</em>");
  });

  test("renders GFM tables", () => {
    const md = `| A | B |\n|---|---|\n| 1 | 2 |`;
    const html = renderMarkdown(md);
    expect(html).toContain("<table>");
    expect(html).toContain("<td>1</td>");
  });

  test("renders code blocks", () => {
    const md = "```js\nconsole.log('hi');\n```";
    const html = renderMarkdown(md);
    expect(html).toContain("<code");
    expect(html).toContain("console.log");
  });

  test("renders links", () => {
    const html = renderMarkdown("[link](https://example.com)");
    expect(html).toContain('href="https://example.com"');
    expect(html).toContain(">link</a>");
  });

  test("strips script tags (XSS prevention)", () => {
    const html = renderMarkdown('<script>alert("xss")</script>');
    expect(html).not.toContain("<script");
    expect(html).not.toContain("alert");
  });

  test("strips event handlers (XSS prevention)", () => {
    const html = renderMarkdown('<img onerror="alert(1)" src="x">');
    expect(html).not.toContain("onerror");
    expect(html).not.toContain("alert");
  });

  test("returns empty string for empty input", () => {
    expect(renderMarkdown("")).toBe("");
  });

  test("returns empty string for null-ish input", () => {
    // @ts-expect-error testing runtime behavior with null
    expect(renderMarkdown(null)).toBe("");
    // @ts-expect-error testing runtime behavior with undefined
    expect(renderMarkdown(undefined)).toBe("");
  });

  test("renders headings", () => {
    const html = renderMarkdown("# Title\n## Subtitle");
    expect(html).toContain("<h1>Title</h1>");
    expect(html).toContain("<h2>Subtitle</h2>");
  });

  test("renders unordered lists", () => {
    const html = renderMarkdown("- item 1\n- item 2");
    expect(html).toContain("<li>item 1</li>");
    expect(html).toContain("<li>item 2</li>");
  });
});
