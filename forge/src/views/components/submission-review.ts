import { html, raw } from "hono/html";

export function submissionReviewBanner(submission: {
  id: string;
  gitUrl: string;
  description: string | null;
}) {
  return html`
    <div class="rounded-md bg-yellow-50 border border-yellow-200 p-4 mb-6">
      <h3 class="text-sm font-medium text-yellow-800">
        This plugin is pending review
      </h3>
      <p class="mt-1 text-sm text-yellow-700">
        Submitted from: ${submission.gitUrl}
      </p>
      ${submission.description
        ? html`<p class="mt-1 text-sm text-yellow-700">
            ${submission.description}
          </p>`
        : ""}

      <div class="mt-4 flex gap-3">
        <button
          hx-post="/api/submissions/${submission.id}/review"
          hx-vals='${raw(JSON.stringify({ action: "approve" }))}'
          hx-target="#review-result"
          hx-swap="innerHTML"
          class="inline-flex items-center px-3 py-1.5 border border-transparent text-sm font-medium rounded-md text-white bg-green-600 hover:bg-green-700"
        >
          Approve
        </button>

        <button
          hx-post="/api/submissions/${submission.id}/review"
          hx-vals='${raw(JSON.stringify({ action: "reject" }))}'
          hx-target="#review-result"
          hx-swap="innerHTML"
          hx-confirm="Reject this plugin submission?"
          class="inline-flex items-center px-3 py-1.5 border border-transparent text-sm font-medium rounded-md text-white bg-red-600 hover:bg-red-700"
        >
          Reject
        </button>
      </div>

      <div id="review-result" class="mt-2"></div>
    </div>
  `;
}
