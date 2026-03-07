import type { HtmlEscapedString } from "hono/utils/html";
import { html } from "hono/html";

export function layout(
  title: string,
  content: HtmlEscapedString | Promise<HtmlEscapedString>,
  user?: { email: string } | null
) {
  return html`<!doctype html>
    <html lang="en">
      <head>
        <meta charset="UTF-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <title>${title} - OpenForge</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <script src="https://unpkg.com/htmx.org@2.0.4"></script>
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
      </body>
    </html>`;
}
