import { html } from "hono/html";

export function submitPage() {
  return html`
    <div class="max-w-2xl mx-auto">
      <h1 class="text-2xl font-bold mb-6">Submit a Plugin</h1>
      <p class="text-gray-600 mb-6">
        Submit a GitHub or GitLab repository containing a Claude Code plugin
        for review by our curators.
      </p>

      <form
        hx-post="/api/submissions"
        hx-target="#submit-result"
        hx-swap="innerHTML"
        class="space-y-4"
      >
        <div>
          <label
            for="gitUrl"
            class="block text-sm font-medium text-gray-700 mb-1"
            >Repository URL *</label
          >
          <input
            type="url"
            name="gitUrl"
            id="gitUrl"
            required
            placeholder="https://github.com/owner/repo"
            class="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500"
          />
          <p class="mt-1 text-sm text-gray-500">
            Must be a public GitHub or GitLab repository.
          </p>
        </div>

        <div>
          <label
            for="description"
            class="block text-sm font-medium text-gray-700 mb-1"
            >Description (optional)</label
          >
          <textarea
            name="description"
            id="description"
            rows="3"
            placeholder="Brief description of what this plugin does..."
            class="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500"
          ></textarea>
        </div>

        <button
          type="submit"
          class="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-gray-900 hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-gray-500"
        >
          Submit for Review
        </button>
      </form>

      <div id="submit-result" class="mt-4"></div>
    </div>
  `;
}

export function submitSuccess(submissionId: string) {
  return html`
    <div class="rounded-md bg-green-50 p-4">
      <p class="text-sm font-medium text-green-800">
        Submission received! Your plugin is pending review by our curators.
      </p>
    </div>
  `;
}
