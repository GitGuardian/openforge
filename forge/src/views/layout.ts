import type { HtmlEscapedString } from "hono/utils/html";
import { html } from "hono/html";

export function layout(
  title: string,
  content: HtmlEscapedString | Promise<HtmlEscapedString>,
  user?: { email: string; role?: string } | null,
  options?: { includeEasyMDE?: boolean; pendingCount?: number }
) {
  const includeEasyMDE = options?.includeEasyMDE ?? false;
  const pendingCount = options?.pendingCount ?? 0;
  const isCuratorOrAdmin = user?.role === "curator" || user?.role === "admin";
  return html`<!doctype html>
    <html lang="en">
      <head>
        <meta charset="UTF-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <title>${title} - OpenForge</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <script src="https://unpkg.com/htmx.org@2.0.4"></script>
        ${includeEasyMDE
          ? html`<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/easymde/dist/easymde.min.css" />`
          : ""}
      </head>
      <body class="bg-gray-50 min-h-screen flex flex-col">
        <nav class="bg-white border-b border-gray-200">
          <div class="max-w-6xl mx-auto flex items-center justify-between py-4 px-6">
            <a href="/" class="text-xl font-bold text-gray-900 hover:text-gray-700">
              OpenForge
            </a>
            <div class="flex items-center gap-4">
              ${user
                ? html`
                    <a
                      href="/submit"
                      class="text-sm text-gray-600 hover:text-gray-900"
                    >
                      Submit
                    </a>
                    <a
                      href="/my/submissions"
                      class="text-sm text-gray-600 hover:text-gray-900"
                    >
                      My Submissions
                    </a>
                    ${isCuratorOrAdmin
                      ? html`
                          <a
                            href="/curator/submissions"
                            class="text-sm text-gray-600 hover:text-gray-900 flex items-center gap-1"
                          >
                            Curator
                            ${pendingCount > 0
                              ? html`<span class="bg-yellow-400 text-yellow-900 text-xs font-bold px-1.5 py-0.5 rounded-full">${pendingCount}</span>`
                              : ""}
                          </a>
                        `
                      : ""}
                    <span class="text-sm text-gray-600">${user.email}</span>
                    <form method="POST" action="/auth/logout" class="inline">
                      <button
                        type="submit"
                        class="text-sm text-gray-500 hover:text-gray-700"
                      >
                        Logout
                      </button>
                    </form>
                  `
                : html`
                    <a
                      href="/auth/login"
                      class="text-sm text-gray-600 hover:text-gray-900"
                    >
                      Login
                    </a>
                    <a
                      href="/auth/signup"
                      class="text-sm bg-gray-900 text-white px-4 py-2 rounded hover:bg-gray-700"
                    >
                      Sign up
                    </a>
                  `}
            </div>
          </div>
        </nav>

        <main class="flex-1">
          <div class="max-w-6xl mx-auto py-8 px-4">${content}</div>
        </main>

        <footer class="border-t border-gray-200">
          <div class="max-w-6xl mx-auto py-4 text-center text-sm text-gray-400">
            OpenForge &middot; Apache 2.0
          </div>
        </footer>
        ${includeEasyMDE
          ? html`
              <script src="https://cdn.jsdelivr.net/npm/easymde/dist/easymde.min.js"></script>
              <script>
                document.addEventListener('DOMContentLoaded', function() {
                  var el = document.getElementById('new-comment');
                  if (el) {
                    window.easyMDE = new EasyMDE({
                      element: el,
                      spellChecker: false,
                      status: false,
                      toolbar: ['bold', 'italic', 'code', 'link', '|', 'unordered-list', 'ordered-list', '|', 'preview'],
                      minHeight: '100px',
                      placeholder: 'Write a comment...',
                    });
                  }
                  // Inject EasyMDE value into HTMX request parameters before the request is sent.
                  // HTMX collects form params before htmx:configRequest fires, so the hidden
                  // textarea (managed by EasyMDE/CodeMirror) is always empty at collection time.
                  // Only inject for the new-comment form — not for reply/edit forms.
                  document.body.addEventListener('htmx:configRequest', function(evt) {
                    if (window.easyMDE && evt.detail.elt && evt.detail.elt.querySelector && evt.detail.elt.querySelector('#new-comment')) {
                      evt.detail.parameters['body'] = window.easyMDE.value();
                    }
                  });
                });
              </script>
            `
          : ""}
      </body>
    </html>`;
}
