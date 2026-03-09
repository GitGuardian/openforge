import { html } from "hono/html";

type SubmissionRow = {
  id: string;
  gitUrl: string;
  status: string;
  createdAt: Date;
  reviewNote: string | null;
  pluginId: string | null;
};

function statusBadge(status: string) {
  const colors: Record<string, string> = {
    pending: "bg-yellow-100 text-yellow-800",
    approved: "bg-green-100 text-green-800",
    rejected: "bg-red-100 text-red-800",
  };
  const cls = colors[status] ?? "bg-gray-100 text-gray-800";
  return html`<span class="px-2 py-0.5 text-xs font-medium rounded-full ${cls}">${status}</span>`;
}

export function mySubmissionsPage(submissions: SubmissionRow[]) {
  if (submissions.length === 0) {
    return html`
      <div class="max-w-4xl mx-auto">
        <h1 class="text-2xl font-bold mb-6">My Submissions</h1>
        <p class="text-gray-500 text-center py-8">
          You have no submissions yet. <a href="/submit" class="text-blue-600 hover:text-blue-800">Submit a plugin</a> to get started.
        </p>
      </div>
    `;
  }

  return html`
    <div class="max-w-4xl mx-auto">
      <h1 class="text-2xl font-bold mb-6">My Submissions</h1>
      <table class="w-full text-sm">
        <thead>
          <tr class="border-b text-left text-gray-500">
            <th class="py-2 pr-4">Repository</th>
            <th class="py-2 pr-4">Status</th>
            <th class="py-2 pr-4">Submitted</th>
            <th class="py-2">Note</th>
          </tr>
        </thead>
        <tbody>
          ${submissions.map(
            (s) => html`
              <tr class="border-b">
                <td class="py-3 pr-4">
                  ${s.pluginId
                    ? html`<a href="/plugins/${s.gitUrl.split("/").pop()}" class="text-blue-600 hover:text-blue-800">${s.gitUrl}</a>`
                    : html`<span class="text-gray-900">${s.gitUrl}</span>`}
                </td>
                <td class="py-3 pr-4">${statusBadge(s.status)}</td>
                <td class="py-3 pr-4 text-gray-500">${new Date(s.createdAt).toLocaleDateString()}</td>
                <td class="py-3 text-gray-500">${s.reviewNote ?? ""}</td>
              </tr>
            `
          )}
        </tbody>
      </table>
    </div>
  `;
}
