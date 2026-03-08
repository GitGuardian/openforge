// forge/src/views/components/comment-section.ts
import { html, raw } from "hono/html";
import { renderMarkdown } from "../../lib/markdown";
import type { AppUser } from "../../types";

export type CommentRow = {
  id: string;
  body: string;
  parentId: string | null;
  createdAt: Date;
  updatedAt: Date;
  userId: string;
  userEmail: string;
  userDisplayName: string | null;
};

function formatDate(date: Date): string {
  return date.toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function commentBody(
  comment: CommentRow,
  user: AppUser | null,
  pluginName: string,
  isReply: boolean,
) {
  const isOwner = user?.id === comment.userId;
  const displayName =
    comment.userDisplayName ?? comment.userEmail.split("@")[0];
  const renderedBody = renderMarkdown(comment.body);

  return html`
    <div
      id="comment-${comment.id}"
      class="${isReply
        ? "ml-8 border-l-2 border-gray-200 pl-4"
        : ""} py-3"
    >
      <div class="flex items-center gap-2 text-sm text-gray-500 mb-1">
        <span class="font-medium text-gray-700">${displayName}</span>
        <span>&middot;</span>
        <time>${formatDate(comment.createdAt)}</time>
        ${comment.updatedAt > comment.createdAt
          ? html`<span class="italic">(edited)</span>`
          : ""}
      </div>
      <div class="prose prose-sm max-w-none">${raw(renderedBody)}</div>
      <div class="flex gap-3 mt-2 text-sm">
        ${!isReply
          ? html`
              <button
                onclick="this.closest('[id^=comment-]').querySelector('.reply-form').classList.toggle('hidden')"
                class="text-gray-500 hover:text-gray-700"
              >
                Reply
              </button>
            `
          : ""}
        ${isOwner
          ? html`
              <button
                hx-get="/plugins/${pluginName}/comments/${comment.id}/edit"
                hx-target="#comment-${comment.id}"
                hx-swap="outerHTML"
                class="text-gray-500 hover:text-gray-700"
              >
                Edit
              </button>
              <button
                hx-delete="/plugins/${pluginName}/comments/${comment.id}"
                hx-target="#comment-${comment.id}"
                hx-swap="delete"
                hx-confirm="Delete this comment?"
                class="text-red-500 hover:text-red-700"
              >
                Delete
              </button>
            `
          : ""}
      </div>
      ${!isReply
        ? html`
            <div class="reply-form hidden mt-3">
              <form
                hx-post="/plugins/${pluginName}/comments"
                hx-target="#comment-${comment.id} .replies"
                hx-swap="beforeend"
                hx-on::after-request="this.reset(); this.closest('.reply-form').classList.add('hidden')"
              >
                <input
                  type="hidden"
                  name="parent_id"
                  value="${comment.id}"
                />
                <textarea
                  name="body"
                  required
                  maxlength="10000"
                  rows="3"
                  placeholder="Write a reply..."
                  class="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300"
                ></textarea>
                <button
                  type="submit"
                  class="mt-2 px-4 py-1.5 bg-gray-900 text-white text-sm rounded hover:bg-gray-700"
                >
                  Reply
                </button>
              </form>
            </div>
          `
        : ""}
    </div>
  `;
}

export function commentSection(
  pluginName: string,
  allComments: CommentRow[],
  user: AppUser | null,
) {
  // Split into top-level and replies
  const topLevel = allComments
    .filter((c) => !c.parentId)
    .sort((a, b) => b.createdAt.getTime() - a.createdAt.getTime()); // newest first

  const repliesByParent = new Map<string, CommentRow[]>();
  for (const c of allComments.filter((c) => c.parentId)) {
    const existing = repliesByParent.get(c.parentId!) ?? [];
    existing.push(c);
    repliesByParent.set(c.parentId!, existing);
  }
  // Sort replies oldest first
  for (const replies of repliesByParent.values()) {
    replies.sort((a, b) => a.createdAt.getTime() - b.createdAt.getTime());
  }

  return html`
    <div id="comments-section" class="mb-8">
      <h2 class="text-lg font-semibold text-gray-900 mb-4">
        Comments (${allComments.length})
      </h2>

      ${user
        ? html`
            <form
              hx-post="/plugins/${pluginName}/comments"
              hx-target="#comments-list"
              hx-swap="afterbegin"
              hx-on::after-request="this.reset(); if(window.easyMDE) window.easyMDE.value('');"
              class="mb-6"
            >
              <textarea
                id="new-comment"
                name="body"
                required
                maxlength="10000"
                rows="4"
                placeholder="Write a comment..."
                class="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300"
              ></textarea>
              <button
                type="submit"
                class="mt-2 px-4 py-2 bg-gray-900 text-white text-sm rounded hover:bg-gray-700"
              >
                Comment
              </button>
            </form>
          `
        : html`
            <p class="text-sm text-gray-500 mb-6">
              <a
                href="/auth/login"
                class="text-blue-600 hover:text-blue-800"
                >Log in</a
              >
              to leave a comment.
            </p>
          `}

      <div id="comments-list" class="divide-y divide-gray-100">
        ${topLevel.map(
          (c) => html`
            <div>
              ${commentBody(c, user, pluginName, false)}
              <div class="replies">
                ${(repliesByParent.get(c.id) ?? []).map((r) =>
                  commentBody(r, user, pluginName, true),
                )}
              </div>
            </div>
          `,
        )}
      </div>

      ${topLevel.length === 0
        ? html`<p class="text-gray-500 text-sm">
            No comments yet. Be the first!
          </p>`
        : ""}
    </div>
  `;
}
