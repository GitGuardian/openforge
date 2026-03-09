import { html } from "hono/html";

type SubmissionRow = {
  id: string;
  gitUrl: string;
  status: string;
  createdAt: Date;
  reviewNote: string | null;
  userId: string;
  pluginId: string | null;
};

type StatusFilter = "all" | "pending" | "approved" | "rejected";

function statusBadge(status: string) {
  const colors: Record<string, string> = {
    pending: "bg-yellow-100 text-yellow-800",
    approved: "bg-green-100 text-green-800",
    rejected: "bg-red-100 text-red-800",
  };
  const cls = colors[status] ?? "bg-gray-100 text-gray-800";
  return html`<span class="px-2 py-0.5 text-xs font-medium rounded-full ${cls}">${status}</span>`;
}

function filterTab(label: string, value: StatusFilter, active: StatusFilter) {
  const isActive = value === active;
  const cls = isActive
    ? "bg-gray-900 text-white"
    : "bg-white text-gray-700 hover:bg-gray-100";
  return html`<a
    href="/curator/submissions${value !== "all" ? `?status=${value}` : ""}"
    class="px-3 py-1 text-sm rounded-md ${cls}"
  >${label}</a>`;
}

export function curatorDashboardPage(
  submissions: SubmissionRow[],
  activeFilter: StatusFilter = "all",
) {
  return html`
    <div class="max-w-5xl mx-auto">
      <h1 class="text-2xl font-bold mb-6">Curator Dashboard</h1>

      <div class="flex gap-2 mb-6">
        ${filterTab("All", "all", activeFilter)}
        ${filterTab("Pending", "pending", activeFilter)}
        ${filterTab("Approved", "approved", activeFilter)}
        ${filterTab("Rejected", "rejected", activeFilter)}
      </div>

      ${submissions.length === 0
        ? html`<p class="text-gray-500 text-center py-8">No submissions found.</p>`
        : html`
            <table class="w-full text-sm">
              <thead>
                <tr class="border-b text-left text-gray-500">
                  <th class="py-2 pr-4">Repository</th>
                  <th class="py-2 pr-4">Status</th>
                  <th class="py-2 pr-4">Submitted</th>
                  <th class="py-2 pr-4">Note</th>
                  <th class="py-2">Actions</th>
                </tr>
              </thead>
              <tbody>
                ${submissions.map(
                  (s) => html`
                    <tr class="border-b">
                      <td class="py-3 pr-4">
                        <span class="text-gray-900">${s.gitUrl}</span>
                      </td>
                      <td class="py-3 pr-4">${statusBadge(s.status)}</td>
                      <td class="py-3 pr-4 text-gray-500">
                        ${new Date(s.createdAt).toLocaleDateString()}
                      </td>
                      <td class="py-3 pr-4 text-gray-500">${s.reviewNote ?? ""}</td>
                      <td class="py-3">${s.status === "pending"
                        ? html`
                          <div class="flex gap-2" id="review-${s.id}">
                            <button
                              hx-post="/api/submissions/${s.id}/review"
                              hx-vals='{"action":"approve"}'
                              hx-target="#review-${s.id}"
                              hx-swap="innerHTML"
                              class="px-2 py-1 text-xs bg-green-600 text-white rounded hover:bg-green-700"
                            >Approve</button>
                            <button
                              hx-post="/api/submissions/${s.id}/review"
                              hx-vals='{"action":"reject"}'
                              hx-target="#review-${s.id}"
                              hx-swap="innerHTML"
                              hx-prompt="Rejection reason (optional):"
                              class="px-2 py-1 text-xs bg-red-600 text-white rounded hover:bg-red-700"
                            >Reject</button>
                          </div>`
                        : html``}</td>
                    </tr>
                  `
                )}
              </tbody>
            </table>
          `}
    </div>
  `;
}
